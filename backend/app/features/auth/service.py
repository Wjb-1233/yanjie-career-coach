import hashlib
import secrets
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import RefreshToken, User
from app.features.auth.schemas import AuthResponse, UserView


def refresh_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def register(
    session: AsyncSession, email: str, password: str, display_name: str
) -> tuple[AuthResponse, str]:
    normalized = email.lower().strip()
    exists = await session.scalar(select(User.id).where(User.email == normalized))
    if exists:
        raise AppError(409, "EMAIL_EXISTS", "该邮箱已注册")
    user = User(email=normalized, password_hash=hash_password(password), display_name=display_name)
    session.add(user)
    await session.flush()
    return await issue_tokens(session, user)


async def login(session: AsyncSession, email: str, password: str) -> tuple[AuthResponse, str]:
    user = await session.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash) or not user.active:
        raise AppError(401, "BAD_CREDENTIALS", "邮箱或密码不正确")
    return await issue_tokens(session, user)


async def demo_login(session: AsyncSession, role: str) -> tuple[AuthResponse, str]:
    demo_ids = {"STUDENT": "demo-student", "ADMIN": "demo-admin"}
    user = await session.get(User, demo_ids[role])
    if user is None or not user.active or user.role != role:
        raise AppError(404, "DEMO_ACCOUNT_MISSING", "演示账号不可用，请联系项目维护者")
    return await issue_tokens(session, user)


async def prune_refresh_tokens(session: AsyncSession, user_id: str | None = None) -> int:
    """删除已过期或已撤销的刷新令牌，避免 token 表无限增长。"""
    now = datetime.now(timezone.utc)
    statement = delete(RefreshToken).where(
        or_(RefreshToken.revoked.is_(True), RefreshToken.expires_at < now)
    )
    if user_id is not None:
        statement = statement.where(RefreshToken.user_id == user_id)
    result = await session.execute(statement)
    return result.rowcount or 0

async def cap_user_tokens(session: AsyncSession, user_id: str, keep: int = 5) -> int:
    """同一个用户只保留最近若干条有效刷新令牌，避免长期累积。"""
    rows = (
        await session.scalars(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .order_by(RefreshToken.created_at.desc())
        )
    ).all()
    removed = 0
    for stale in rows[keep:]:
        await session.delete(stale)
        removed += 1
    return removed

async def issue_tokens(session: AsyncSession, user: User) -> tuple[AuthResponse, str]:
    access_token, expires_in = create_access_token(user)
    raw_refresh = secrets.token_urlsafe(48)
    await prune_refresh_tokens(session, user.id)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash(raw_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
        )
    )
    await session.flush()
    await cap_user_tokens(session, user.id)
    await session.commit()
    return (
        AuthResponse(
            access_token=access_token,
            expires_in=expires_in,
            user=UserView.from_orm_user(user),
        ),
        raw_refresh,
    )


async def rotate_refresh(session: AsyncSession, raw_token: str) -> tuple[AuthResponse, str]:
    stored = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == refresh_hash(raw_token), RefreshToken.revoked.is_(False)
        )
    )
    if stored is None:
        raise AppError(401, "REFRESH_INVALID", "登录状态已过期，请重新登录")
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        stored.revoked = True
        await session.commit()
        raise AppError(401, "REFRESH_EXPIRED", "登录状态已过期，请重新登录")
    stored.revoked = True
    user = await session.get(User, stored.user_id)
    if user is None or not user.active:
        raise AppError(401, "USER_INVALID", "用户不存在或已停用")
    return await issue_tokens(session, user)


async def revoke_refresh(session: AsyncSession, raw_token: str | None) -> None:
    if raw_token:
        await session.execute(
            delete(RefreshToken).where(RefreshToken.token_hash == refresh_hash(raw_token))
        )
        await session.commit()


PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


async def change_password(
    session: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AppError(422, "PASSWORD_MISMATCH", "当前密码不正确")
    if current_password == new_password:
        raise AppError(422, "PASSWORD_UNCHANGED", "新密码不能和当前密码相同")
    if not PASSWORD_PATTERN.match(new_password):
        raise AppError(422, "PASSWORD_TOO_WEAK", "新密码至少 8 位，且同时包含字母和数字")
    user.password_hash = hash_password(new_password)
    await session.commit()


ALLOWED_AVATAR_PREFIXES = (
    "data:image/png;base64,",
    "data:image/jpeg;base64,",
    "data:image/webp;base64,",
)


async def set_avatar(session: AsyncSession, user: User, data_url: str) -> str | None:
    if data_url == "":
        user.avatar = None
        await session.commit()
        return None
    if not any(data_url.startswith(prefix) for prefix in ALLOWED_AVATAR_PREFIXES):
        raise AppError(422, "AVATAR_FORMAT", "只支持 PNG / JPEG / WebP 图片")
    if len(data_url) > 300000:
        raise AppError(422, "AVATAR_TOO_LARGE", "图片太大，请控制在 200KB 以内")
    user.avatar = data_url
    await session.commit()
    return data_url


async def account_stats(session: AsyncSession, user_id: str) -> dict:
    from app.db.models import Evaluation, TrainingSession

    sessions = await session.scalar(
        select(func.count()).select_from(TrainingSession).where(
            TrainingSession.user_id == user_id,
            TrainingSession.status == "FINISHED",
        )
    )
    average = await session.scalar(
        select(func.avg(Evaluation.overall_score)).where(Evaluation.user_id == user_id)
    )
    last = await session.scalar(
        select(func.max(Evaluation.created_at)).where(Evaluation.user_id == user_id)
    )
    return {
        "finishedSessions": sessions or 0,
        "averageScore": round(float(average), 1) if average is not None else None,
        "lastEvaluatedAt": last.isoformat() if last else None,
    }


async def create_password_request(session: AsyncSession, email: str) -> None:
    """学员忘记密码时提交申请；无论邮箱是否存在都返回成功，避免泄露账号。"""
    from app.db.models import PasswordResetRequest

    user = await session.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or user.role == "ADMIN" or not user.active:
        return
    pending = await session.scalar(
        select(PasswordResetRequest).where(
            PasswordResetRequest.user_id == user.id,
            PasswordResetRequest.status == "PENDING",
        )
    )
    if pending is not None:
        return
    session.add(PasswordResetRequest(user_id=user.id, status="PENDING"))
    await session.commit()

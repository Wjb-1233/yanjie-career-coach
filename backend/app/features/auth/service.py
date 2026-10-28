import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
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


async def issue_tokens(session: AsyncSession, user: User) -> tuple[AuthResponse, str]:
    access_token, expires_in = create_access_token(user)
    raw_refresh = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash(raw_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
        )
    )
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


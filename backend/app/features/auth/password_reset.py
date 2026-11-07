"""忘记密码：邮件链接重置，SMTP 未配置时回退为管理员工单。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_password
from app.db.models import PasswordResetToken, RefreshToken, User
from app.features.auth.service import PASSWORD_PATTERN, create_password_request
from app.infrastructure import mailer

RESET_TTL_MINUTES = 30


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def request_reset(session: AsyncSession, email: str) -> None:
    """无论邮箱是否存在都返回成功，避免账号枚举。"""
    normalized = email.lower().strip()
    user = await session.scalar(select(User).where(User.email == normalized))
    if user is None or not user.active or user.role == "ADMIN":
        return

    if not mailer.smtp_configured():
        # 没有邮件服务：沿用管理员工单，至少让用户有路可走
        await create_password_request(session, normalized)
        return

    token = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    await session.commit()

    link = f"{settings.app_public_url.rstrip('/')}/reset-password?token={token}"
    sent = await mailer.send_password_reset(user.email, link, settings.password_reset_minutes)
    if not sent:
        # 发送失败不能把用户晾着，退回工单
        await create_password_request(session, normalized)


async def confirm_reset(session: AsyncSession, token: str, new_password: str) -> None:
    if not PASSWORD_PATTERN.match(new_password):
        raise AppError(422, "PASSWORD_TOO_WEAK", "新密码至少 8 位，且同时包含字母和数字")

    row = await session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(token)))
    now = datetime.now(timezone.utc)
    # SQLite 会丢掉时区，比较前补上
    expires_aware = row.expires_at if row and row.expires_at.tzinfo else (
        row.expires_at.replace(tzinfo=timezone.utc) if row else None
    )
    if row is None or row.used_at is not None or expires_aware is None or expires_aware < now:
        raise AppError(422, "RESET_TOKEN_INVALID", "链接无效或已过期，请重新申请")

    user = await session.get(User, row.user_id)
    if user is None or not user.active:
        raise AppError(422, "RESET_TOKEN_INVALID", "链接无效或已过期，请重新申请")

    user.password_hash = hash_password(new_password)
    row.used_at = now
    # 重置密码后让所有旧登录态失效
    await session.execute(
        RefreshToken.__table__.update()
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await session.commit()

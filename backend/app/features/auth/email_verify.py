"""邮箱验证：注册后发链接，未验证时限制开始训练。

令牌用短期 JWT（用途字段 typ=verify），不需要额外表；验证成功写回 users.email_verified。
"""

from __future__ import annotations

import logging

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.db.models import User
from app.infrastructure import mailer

logger = logging.getLogger(__name__)


def _sign(user: User) -> str:
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": user.id,
        "typ": "verify",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.email_verification_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def send_verification(user: User) -> bool:
    if not mailer.smtp_configured():
        return False
    link = f"{settings.app_public_url.rstrip('/')}/verify-email?token={_sign(user)}"
    try:
        await mailer.send_email(
            user.email,
            "言阶 · 验证邮箱",
            f"你好，\n\n请打开下面的链接验证邮箱，完成后再开始训练：\n\n{link}\n\n"
            f"链接 {settings.email_verification_hours} 小时内有效。\n\n— 言阶",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("mail.verify_failed error_type=%s", type(exc).__name__)
        return False


async def confirm(session: AsyncSession, token: str) -> None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iss", "aud", "iat"]},
        )
    except Exception as exc:  # noqa: BLE001
        raise AppError(422, "VERIFY_TOKEN_INVALID", "链接无效或已过期，请重新发送验证邮件") from exc

    if payload.get("typ") != "verify":
        raise AppError(422, "VERIFY_TOKEN_INVALID", "链接无效或已过期，请重新发送验证邮件")

    user = await session.get(User, str(payload.get("sub")))
    if user is None or not user.active:
        raise AppError(422, "VERIFY_TOKEN_INVALID", "链接无效或已过期，请重新发送验证邮件")

    user.email_verified = True
    await session.commit()


def require_verified(user: User) -> None:
    if settings.require_email_verification and not user.email_verified:
        raise AppError(403, "EMAIL_NOT_VERIFIED", "请先验证邮箱，验证后即可开始训练")

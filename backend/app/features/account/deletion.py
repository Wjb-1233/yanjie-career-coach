"""注销账号：删除个人数据与媒体文件，操作不可恢复。"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import verify_password
from app.db.models import TrainingSession, User
from app.features.recordings import storage

logger = logging.getLogger(__name__)

# 演示账号不允许注销，避免演示环境被清空
DEMO_EMAILS = {"student@example.com", "admin@example.com"}


async def delete_account(session: AsyncSession, user: User, password: str) -> None:
    if user.email in DEMO_EMAILS:
        raise AppError(403, "DEMO_ACCOUNT_PROTECTED", "演示账号不能注销")
    if not verify_password(password, user.password_hash):
        raise AppError(403, "PASSWORD_INVALID", "密码不正确，未注销")

    sessions = (
        await session.scalars(
            select(TrainingSession).where(TrainingSession.user_id == user.id)
        )
    ).all()

    # 先删文件再删库：库删了之后就找不到这些文件了
    for item in sessions:
        storage.remove(item.recording_path)
        for segment in (item.delivery or {}).get("segments") or []:
            name = segment.get("file")
            if name:
                storage.remove(name)

    await session.delete(user)
    await session.commit()
    logger.info("account.deleted sessions=%s", len(sessions))

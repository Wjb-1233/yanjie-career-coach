"""录制文件的保留策略：过期清理与孤儿文件回收。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import TrainingSession
from app.features.recordings import storage

logger = logging.getLogger(__name__)


async def purge_expired(session: AsyncSession, *, days: int | None = None) -> dict:
    """删除超过保留期的录制，并回收没有被任何会话引用的文件。"""
    keep_days = days if days is not None else settings.recording_retention_days
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=keep_days)

    rows = (
        await session.scalars(
            select(TrainingSession).where(
                TrainingSession.recording_path.is_not(None),
                TrainingSession.started_at < cutoff,
            )
        )
    ).all()

    removed = 0
    freed = 0
    for row in rows:
        path = settings.recording_dir_path / row.recording_path
        if path.exists():
            freed += path.stat().st_size
            path.unlink(missing_ok=True)
        row.recording_path = None
        removed += 1
    if removed:
        await session.commit()

    # 空库保护：一个训练会话都没有时，无法判断哪些文件是孤儿，直接跳过
    if (await session.scalar(select(func.count()).select_from(TrainingSession))) == 0:
        return {
            "removed": removed,
            "orphans": 0,
            "freedBytes": freed,
            "retentionDays": keep_days,
            "skipped": "no_sessions",
        }

    # 孤儿文件：目录里有、但没有任何会话引用
    referenced = set(
        (await session.scalars(select(TrainingSession.recording_path).where(TrainingSession.recording_path.is_not(None)))).all()
    )
    orphans = 0
    directory = settings.recording_dir_path
    if directory.exists():
        for path in directory.iterdir():
            if path.is_file() and path.name not in referenced:
                freed += path.stat().st_size
                path.unlink(missing_ok=True)
                orphans += 1

    result = {
        "removed": removed,
        "orphans": orphans,
        "freedBytes": freed,
        "retentionDays": keep_days,
    }
    if removed or orphans:
        logger.info(
            "recordings.cleaned removed=%s orphans=%s freed_mb=%.1f",
            removed,
            orphans,
            freed / 1024 / 1024,
        )
    return result


async def usage() -> dict:
    """当前录制占用情况（后台面板用）。"""
    directory = settings.recording_dir_path
    files = [path for path in directory.iterdir() if path.is_file()] if directory.exists() else []
    total = sum(path.stat().st_size for path in files)
    return {
        "count": len(files),
        "totalBytes": total,
        "totalMb": round(total / 1024 / 1024, 1),
        "retentionDays": settings.recording_retention_days,
    }

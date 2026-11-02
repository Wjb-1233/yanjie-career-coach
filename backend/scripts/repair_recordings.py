"""清理数据库里指向已丢失文件的 recording_path。"""

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.base import session_factory
from app.db.models import TrainingSession


async def main() -> None:
    cleared = 0
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(TrainingSession).where(TrainingSession.recording_path.is_not(None))
            )
        ).all()
        for row in rows:
            if not (settings.recording_dir_path / row.recording_path).is_file():
                row.recording_path = None
                cleared += 1
        await session.commit()
    print(f"cleared={cleared}, checked={len(rows)}")


asyncio.run(main())

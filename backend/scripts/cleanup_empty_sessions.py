"""清理"啥也没干"的空训练会话（0 轮对话、无评分）。"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Evaluation, TrainingSession


async def main() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    async with session_factory() as session:
        rows = (await session.scalars(select(TrainingSession))).all()
        targets = []
        for training in rows:
            if training.current_round > 0:
                continue
            if training.status == "FINISHED":
                continue
            started = training.started_at
            if started is not None and started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started is not None and started > cutoff:
                continue
            has_evaluation = await session.scalar(
                select(Evaluation.id).where(Evaluation.session_id == training.id)
            )
            if has_evaluation:
                continue
            targets.append(training)
        for training in targets:
            await session.delete(training)
        await session.commit()
        print(f"removed={len(targets)} remaining={len(rows) - len(targets)}")


asyncio.run(main())

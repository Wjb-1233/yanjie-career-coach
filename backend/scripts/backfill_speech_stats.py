import asyncio

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Evaluation, Message
from app.features.evaluations.service import speech_statistics


async def main() -> None:
    async with session_factory() as session:
        rows = (await session.scalars(select(Evaluation))).all()
        filled = 0
        for evaluation in rows:
            if evaluation.speech_stats:
                continue
            messages = (
                await session.scalars(
                    select(Message).where(Message.session_id == evaluation.session_id)
                )
            ).all()
            if not messages:
                continue
            evaluation.speech_stats = speech_statistics(messages)
            filled += 1
        await session.commit()
        print(f"backfilled={filled} total={len(rows)}")


asyncio.run(main())

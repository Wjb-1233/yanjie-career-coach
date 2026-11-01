import asyncio

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Scene
from app.features.scenes.taxonomy import normalize_bank

KEEP = 2


async def main() -> None:
    async with session_factory() as session:
        scenes = (await session.scalars(select(Scene))).all()
        trimmed = 0
        for scene in scenes:
            bank = normalize_bank(scene.question_bank)
            if len(bank) <= KEEP:
                continue
            scene.question_bank = [
                {"text": item["text"], "dimension": None, "difficulty": None}
                for item in bank[:KEEP]
            ]
            trimmed += 1
        await session.commit()
        counts = {len(normalize_bank(item.question_bank)) for item in scenes}
        print(f"trimmed={trimmed} bank_sizes={sorted(counts)}")


asyncio.run(main())

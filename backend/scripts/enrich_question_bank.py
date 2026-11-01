import asyncio

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Scene
from app.features.scenes.taxonomy import DIMENSION_LABELS, normalize_bank

DIFFICULTY_KEYS = ["入门", "中级", "进阶"]


async def main() -> None:
    async with session_factory() as session:
        scenes = (await session.scalars(select(Scene))).all()
        touched = 0
        for scene in scenes:
            bank = normalize_bank(scene.question_bank)
            if not bank:
                continue
            changed = False
            for index, item in enumerate(bank):
                if not item["dimension"]:
                    item["dimension"] = DIMENSION_LABELS[index % len(DIMENSION_LABELS)]
                    changed = True
                if not item["difficulty"]:
                    item["difficulty"] = DIFFICULTY_KEYS[min(index, 2)]
                    changed = True
            if changed:
                scene.question_bank = bank
                touched += 1
        await session.commit()
        print(f"enriched={touched} scenes={len(scenes)}")


asyncio.run(main())

"""清洗历史话术数据：旧维度名与异常风格值。"""

import asyncio

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Script
from app.features.scripts.service import LEGACY_DIMENSIONS, normalize_dimension

VALID_STYLES = {"正式", "亲和", "简洁"}


async def main() -> None:
    changed_dimension = 0
    changed_style = 0
    async with session_factory() as session:
        for row in (await session.scalars(select(Script))).all():
            original_dimension = row.dimension
            row.dimension = normalize_dimension(row.dimension)
            if row.dimension != original_dimension:
                changed_dimension += 1
            if row.style not in VALID_STYLES:
                row.style = "正式"
                changed_style += 1
        await session.commit()
    print(f"维度修正 {changed_dimension} 条，风格归正 {changed_style} 条")
    print("旧维度映射:", LEGACY_DIMENSIONS)


asyncio.run(main())

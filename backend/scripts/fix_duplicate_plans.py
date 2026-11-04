"""修数据漂移：同一学员多份「进行中」计划。

计划生成时会自动把旧计划标记为 SUPERSEDED，但早期数据没有走这条路径，
库里留下了多份 ACTIVE。这里按创建时间保留最新一份，其余标记为已被替代。

用法：
    python scripts/fix_duplicate_plans.py --dry-run
    python scripts/fix_duplicate_plans.py
"""

import argparse
import asyncio
from collections import defaultdict

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import TrainingPlan


async def main(dry_run: bool) -> None:
    async with session_factory() as session:
        plans = list(
            (
                await session.scalars(
                    select(TrainingPlan)
                    .where(TrainingPlan.status == "ACTIVE")
                    .order_by(TrainingPlan.created_at.desc())
                )
            ).all()
        )
        by_user: dict[str, list[TrainingPlan]] = defaultdict(list)
        for plan in plans:
            by_user[plan.user_id].append(plan)

        changed = 0
        for user_id, items in by_user.items():
            if len(items) <= 1:
                continue
            for plan in items[1:]:
                print(f"  学员 {user_id[:8]}：{plan.id[:8]} → SUPERSEDED（{plan.title[:24]}）")
                if not dry_run:
                    plan.status = "SUPERSEDED"
                changed += 1

        if not dry_run:
            await session.commit()

        print(
            f"{'预演' if dry_run else '完成'}：{len(by_user)} 位学员，"
            f"{changed} 份重复计划{'将' if dry_run else '已'}标记为已被替代"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(main(parser.parse_args().dry_run))

"""把历史数据里的旧维度名称统一成新叫法（微课、计划标题、评分摘要）。

用法：PYTHONPATH=. .venv/Scripts/python.exe scripts/modernize_legacy_text.py
"""

import asyncio
import copy

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db.base import session_factory
from app.db.models import Evaluation, TrainingPlan
from app.core.legacy_text import modernize


def _contains_legacy(value) -> bool:
    text = str(value)
    return "感染力" in text or "impact" in text


async def main() -> None:
    plans = 0
    evaluations = 0
    async with session_factory() as session:
        for plan in (await session.scalars(select(TrainingPlan))).all():
            tasks = copy.deepcopy(plan.tasks or [])
            changed = False
            for task in tasks:
                for key in ("task", "lesson"):
                    if key in task and _contains_legacy(task[key]):
                        task[key] = modernize(task[key])
                        changed = True
            if _contains_legacy(plan.title):
                plan.title = modernize(plan.title)
                changed = True
            if changed:
                plan.tasks = tasks
                flag_modified(plan, "tasks")
                plans += 1

        for evaluation in (await session.scalars(select(Evaluation))).all():
            changed = False
            if _contains_legacy(evaluation.summary):
                evaluation.summary = modernize(evaluation.summary)
                changed = True
            if evaluation.suggestions and _contains_legacy(evaluation.suggestions):
                evaluation.suggestions = modernize(evaluation.suggestions)
                changed = True
            if changed:
                evaluations += 1

        await session.commit()

    print(f"plans updated={plans}, evaluations updated={evaluations}")


asyncio.run(main())

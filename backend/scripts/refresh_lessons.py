"""重新生成残留旧维度文案的微课，并清掉对应的旧视频缓存。

用法：PYTHONPATH=. .venv/Scripts/python.exe scripts/refresh_lessons.py
"""

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.base import session_factory
from app.db.models import TrainingPlan
from app.features.plans.service import personalized_lesson

STALE_MARKERS = ("感染力",)
VIDEO_SUFFIXES = (".mp4",)


def _is_stale(lesson: dict | None) -> bool:
    if not lesson:
        return False
    text = " ".join(
        str(lesson.get(key, "")) for key in ("title", "intro", "focus")
    ) + " ".join(str(step.get("title", "")) for step in lesson.get("steps", []))
    return any(marker in text for marker in STALE_MARKERS)


async def main() -> None:
    refreshed = 0
    async with session_factory() as session:
        plans = (await session.scalars(select(TrainingPlan))).all()
        for plan in plans:
            for task in plan.tasks or []:
                lesson = task.get("lesson")
                if not _is_stale(lesson):
                    continue
                key = task.get("key", "course")
                await personalized_lesson(session, plan.user_id, plan.id, key, force=True)
                refreshed += 1
                print(f"refreshed plan={plan.id[:8]} task={key}")

    removed = 0
    for path in settings.lesson_video_dir_path.glob("*.mp4"):
        if any(marker in path.name for marker in STALE_MARKERS):
            path.unlink()
            removed += 1
    print(f"lessons refreshed={refreshed}, stale videos removed={removed}")


asyncio.run(main())

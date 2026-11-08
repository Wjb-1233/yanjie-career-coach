import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.plans.schemas import CompleteTaskRequest, PracticeRequest
from app.features.evaluations.service import regenerate_training_plan
from app.features.plans.service import (
    personalized_lesson,
    complete_course_task,
    complete_lesson_step,
    complete_training_task,
    get_training_plan,
    list_training_plans,
    submit_lesson_practice,
)

router = APIRouter(prefix="/training-plans", tags=["训练计划"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


class RegeneratePlanRequest(BaseModel):
    dimension: str = Field(min_length=2, max_length=10)


@router.post("/regenerate", status_code=201)
async def regenerate(body: RegeneratePlanRequest, user: CurrentUser, session: DbSession) -> dict:
    plan_id = await regenerate_training_plan(session, user.id, body.dimension)
    return ok({"id": plan_id})


class LessonRequest(BaseModel):
    task_key: str = Field(default="course", min_length=1, max_length=40)
    force: bool = False
    engine: str = Field(default="auto", pattern="^(auto|python|remotion)$")


@router.post("/{plan_id}/lesson")
async def lesson(plan_id: str, body: LessonRequest, user: CurrentUser, session: DbSession) -> dict:
    result = await personalized_lesson(session, user.id, plan_id, body.task_key, force=body.force)
    return ok(result)


@router.post("/{plan_id}/lesson/video")
async def lesson_video(plan_id: str, body: LessonRequest, user: CurrentUser, session: DbSession) -> dict:
    """把当前微课渲染成 mp4；同一份内容 + 同一引擎只渲染一次。"""
    from app.features.lessons.video import lesson_key, render_video_with_fallback

    result = await personalized_lesson(session, user.id, plan_id, body.task_key, force=body.force)
    lesson = ((result or {}).get("lesson") or {})
    if not lesson.get("steps"):
        raise AppError(422, "LESSON_EMPTY", "这门微课还没有可渲染的内容")

    engine = body.engine
    if engine == "auto":
        engine = settings.lesson_video_engine if settings.lesson_video_engine in {"python", "remotion"} else "python"

    key = f"{lesson_key(lesson)}-{engine}"
    target = settings.lesson_video_dir_path / f"{key}.mp4"
    if not target.exists():
        from app.features.plans.service import get_training_plan

        plan = await get_training_plan(session, user.id, plan_id)
        engine, target, key = await asyncio.to_thread(
            render_video_with_fallback, engine, lesson, target, key, plan.focus_dimension
        )
    chapters: list[dict] = []
    sidecar = target.with_suffix(".json")
    if sidecar.is_file():
        try:
            chapters = json.loads(sidecar.read_text(encoding="utf-8")).get("chapters", [])
        except Exception:  # noqa: BLE001
            chapters = []
    return ok(
        {"url": f"/media/lessons/{key}.mp4", "key": key, "engine": engine, "chapters": chapters}
    )


@router.get("/{plan_id}/lesson/video")
async def lesson_video_state(
    plan_id: str,
    user: CurrentUser,
    session: DbSession,
    task_key: str = "course",
    engine: str = "auto",
) -> dict:
    """只查询是否已有缓存的视频与小节，不触发渲染。"""
    import json as _json

    from app.features.lessons.video import lesson_key

    result = await personalized_lesson(session, user.id, plan_id, task_key)
    lesson = ((result or {}).get("lesson") or {})
    if not lesson.get("steps"):
        return ok({"url": None, "chapters": []})

    resolved = settings.lesson_video_engine if engine == "auto" and settings.lesson_video_engine in {"python", "remotion"} else engine
    key = f"{lesson_key(lesson)}-{resolved}"
    target = settings.lesson_video_dir_path / f"{key}.mp4"
    if not target.exists():
        return ok({"url": None, "chapters": []})

    chapters: list[dict] = []
    sidecar = target.with_suffix(".json")
    if sidecar.is_file():
        try:
            chapters = _json.loads(sidecar.read_text(encoding="utf-8")).get("chapters", [])
        except Exception:  # noqa: BLE001
            chapters = []
    return ok({"url": f"/media/lessons/{key}.mp4", "key": key, "chapters": chapters})


@router.get("")
async def list_all(user: CurrentUser, session: DbSession) -> dict:
    plans = await list_training_plans(session, user.id)
    return ok([item.model_dump(by_alias=True) for item in plans])


@router.get("/{plan_id}")
async def get_one(plan_id: str, user: CurrentUser, session: DbSession) -> dict:
    plan = await get_training_plan(session, user.id, plan_id)
    return ok(plan.model_dump(by_alias=True))


@router.post("/{plan_id}/tasks/{task_key}/complete")
async def complete_task(
    plan_id: str,
    task_key: str,
    body: CompleteTaskRequest,
    user: CurrentUser,
    session: DbSession,
) -> dict:
    plan = await complete_training_task(session, user.id, plan_id, task_key, body.evidence)
    return ok(plan.model_dump(by_alias=True))


@router.post("/{plan_id}/tasks/{task_key}/course/complete")
async def complete_course(plan_id: str, task_key: str, user: CurrentUser, session: DbSession) -> dict:
    plan = await complete_course_task(session, user.id, plan_id, task_key)
    return ok(plan.model_dump(by_alias=True))


@router.post("/{plan_id}/tasks/{task_key}/steps/{step_index}/complete")
async def complete_step(
    plan_id: str, task_key: str, step_index: int, user: CurrentUser, session: DbSession
) -> dict:
    plan = await complete_lesson_step(session, user.id, plan_id, task_key, step_index)
    return ok(plan.model_dump(by_alias=True))


@router.post("/{plan_id}/tasks/{task_key}/practice")
async def submit_practice(
    plan_id: str,
    task_key: str,
    body: PracticeRequest,
    user: CurrentUser,
    session: DbSession,
) -> dict:
    plan = await submit_lesson_practice(session, user.id, plan_id, task_key, body.answer)
    return ok(plan.model_dump(by_alias=True))

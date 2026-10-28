from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.plans.schemas import CompleteTaskRequest, PracticeRequest
from app.features.plans.service import (
    complete_lesson_step,
    complete_training_task,
    get_training_plan,
    list_training_plans,
    submit_lesson_practice,
)

router = APIRouter(prefix="/training-plans", tags=["训练计划"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


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

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.questionbank import service
from app.features.questionbank.schemas import QuestionBankStatePatch

router = APIRouter(prefix="/question-bank", tags=["题库"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_questions(
    user: CurrentUser,
    session: DbSession,
    dimension: str | None = None,
    scene_id: Annotated[str | None, Query(alias="sceneId")] = None,
    favorite: bool | None = None,
    mastered: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    result = await service.list_questions(
        session, user.id, dimension, scene_id, favorite, mastered, page, size
    )
    return ok(result.model_dump(by_alias=True))


@router.get("/summary")
async def question_bank_summary(user: CurrentUser, session: DbSession) -> dict:
    result = await service.summary(session, user.id)
    return ok(result.model_dump(by_alias=True))


@router.patch("/{question_id}/state")
async def update_state(
    question_id: str, body: QuestionBankStatePatch, user: CurrentUser, session: DbSession
) -> dict:
    if body.favorite is None and body.mastered is None:
        raise AppError(422, "VALIDATION_ERROR", "至少提供一个字段：favorite 或 mastered")
    return ok(await service.set_state(session, user.id, question_id, body.favorite, body.mastered))

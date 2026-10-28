from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.evaluations.service import evaluate_session, get_evaluation

router = APIRouter(prefix="/evaluations", tags=["智能评分"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.post("/{session_id}", status_code=201)
async def evaluate(session_id: str, user: CurrentUser, session: DbSession) -> dict:
    result = await evaluate_session(session, user.id, session_id)
    return ok(result.model_dump(by_alias=True))


@router.get("/{session_id}")
async def get_one(session_id: str, user: CurrentUser, session: DbSession) -> dict:
    result = await get_evaluation(session, user.id, session_id)
    return ok(result.model_dump(by_alias=True))


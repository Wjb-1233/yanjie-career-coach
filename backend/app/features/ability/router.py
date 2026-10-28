from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.ability.schemas import AbilityAttemptInput
from app.features.ability.service import current_practice, submit_attempt

router = APIRouter(prefix="/ability", tags=["能力提升"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("/current")
async def current(user: CurrentUser, session: DbSession) -> dict:
    result = await current_practice(session, user.id)
    return ok(result.model_dump(by_alias=True) if result else None)


@router.post("/attempts", status_code=201)
async def create_attempt(payload: AbilityAttemptInput, user: CurrentUser, session: DbSession) -> dict:
    result = await submit_attempt(session, user.id, payload)
    return ok(result.model_dump(by_alias=True))

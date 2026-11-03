"""故事库接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.stories import service
from app.features.stories.schemas import ExtractRequest, StoryPayload, StoryUpdate, StoryView

router = APIRouter(prefix="/stories", tags=["故事库"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_stories(user: CurrentUser, session: DbSession) -> dict:
    rows = await service.list_stories(session, user.id)
    return ok([StoryView.model_validate(row).model_dump(by_alias=True) for row in rows])


@router.post("", status_code=201)
async def create_story(body: StoryPayload, user: CurrentUser, session: DbSession) -> dict:
    story = await service.create_story(session, user.id, body.model_dump())
    return ok(StoryView.model_validate(story).model_dump(by_alias=True))


@router.patch("/{story_id}")
async def update_story(story_id: str, body: StoryUpdate, user: CurrentUser, session: DbSession) -> dict:
    story = await service.update_story(session, user.id, story_id, body.model_dump(exclude_none=True))
    return ok(StoryView.model_validate(story).model_dump(by_alias=True))


@router.delete("/{story_id}", status_code=204)
async def delete_story(story_id: str, user: CurrentUser, session: DbSession) -> None:
    await service.delete_story(session, user.id, story_id)


@router.post("/extract", status_code=201)
async def extract_stories(body: ExtractRequest, user: CurrentUser, session: DbSession) -> dict:
    stories = await service.extract_from_session(session, user.id, body.session_id)
    return ok([StoryView.model_validate(story).model_dump(by_alias=True) for story in stories])


@router.post("/{story_id}/use")
async def mark_used(story_id: str, user: CurrentUser, session: DbSession) -> dict:
    story = await service.mark_used(session, user.id, story_id)
    return ok(StoryView.model_validate(story).model_dump(by_alias=True))

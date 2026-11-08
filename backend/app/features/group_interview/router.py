"""群面接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import GroupInterview
from app.features.group_interview import service

router = APIRouter(prefix="/group-interviews", tags=["群面"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


class CreateGroupRequest(BaseModel):
    topicId: str


class GroupMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=600)


def _view(row: GroupInterview) -> dict:
    return {
        "id": row.id,
        "topicId": row.topic_id,
        "topicTitle": row.topic_title,
        "topicPrompt": row.topic_prompt,
        "status": row.status,
        "turns": row.turns or [],
        "result": row.result,
        "createdAt": row.created_at.isoformat(),
        "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
    }


@router.get("/topics")
async def topics(user: CurrentUser) -> dict:
    return ok(service.list_topics())


@router.post("", status_code=201)
async def create(body: CreateGroupRequest, user: CurrentUser, session: DbSession) -> dict:
    row = await service.create_group(session, user.id, body.topicId)
    return ok(_view(row))


@router.get("")
async def history(user: CurrentUser, session: DbSession, limit: int = 10) -> dict:
    rows = (
        await session.scalars(
            select(GroupInterview)
            .where(GroupInterview.user_id == user.id)
            .order_by(GroupInterview.created_at.desc())
            .limit(max(1, min(limit, 30)))
        )
    ).all()
    return ok(
        [
            {
                "id": row.id,
                "topicTitle": row.topic_title,
                "status": row.status,
                "score": (row.result or {}).get("score"),
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ]
    )


@router.get("/{group_id}")
async def detail(group_id: str, user: CurrentUser, session: DbSession) -> dict:
    row = await session.get(GroupInterview, group_id)
    if row is None or row.user_id != user.id:
        from app.core.errors import not_found

        raise not_found("群面记录")
    return ok(_view(row))


@router.post("/{group_id}/messages")
async def send(group_id: str, body: GroupMessageRequest, user: CurrentUser, session: DbSession) -> dict:
    row = await service.append_user_message(session, user.id, group_id, body.content)
    return ok(_view(row))


@router.post("/{group_id}/finish")
async def finish(group_id: str, user: CurrentUser, session: DbSession) -> dict:
    row = await service.finish_group(session, user.id, group_id)
    return ok(_view(row))

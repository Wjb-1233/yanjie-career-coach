"""我的场景接口：/my-scenes。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.infrastructure.rate_limit import limit_model_user
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.scenes import mine
from app.features.scenes import draft
from app.features.scenes.schemas import JdDraftRequest, MyScenePayload

router = APIRouter(prefix="/my-scenes", tags=["我的场景"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_my_scenes(user: CurrentUser, session: DbSession) -> dict:
    scenes = await mine.list_my_scenes(session, user.id)
    usage = await mine.scene_usage(session, user.id)
    return ok(
        {
            "items": [item.model_copy(update={"mine": True}).model_dump(by_alias=True) for item in scenes],
            "count": usage["count"],
            "limit": usage["limit"],
        }
    )


@router.post("", status_code=201)
async def create_my_scene(body: MyScenePayload, user: CurrentUser, session: DbSession) -> dict:
    scene = await mine.create_scene(session, user.id, body)
    return ok(scene.model_copy(update={"mine": True}).model_dump(by_alias=True))


@router.patch("/{scene_id}")
async def update_my_scene(
    scene_id: str, body: MyScenePayload, user: CurrentUser, session: DbSession
) -> dict:
    scene = await mine.update_scene(session, user.id, scene_id, body)
    return ok(scene.model_copy(update={"mine": True}).model_dump(by_alias=True))


@router.delete("/{scene_id}", status_code=204)
async def delete_my_scene(scene_id: str, user: CurrentUser, session: DbSession) -> None:
    await mine.delete_scene(session, user.id, scene_id)


@router.post("/draft-from-jd")
async def draft_scene(body: JdDraftRequest, user: CurrentUser) -> dict:
    """P1：粘贴 JD 起草场景，返回表单结构，由用户确认后才保存。"""
    await limit_model_user(user.id)
    result = await draft.draft_from_jd(
        body.jd,
        body.position,
        body.category or "自定义",
        body.difficulty or "中级",
    )
    return ok(result)

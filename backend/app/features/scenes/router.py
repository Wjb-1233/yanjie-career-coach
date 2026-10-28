from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.features.scenes import service
from app.features.scenes.schemas import SceneView

router = APIRouter(prefix="/scenes", tags=["场景库"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_scenes(
    user: CurrentUser,
    session: DbSession,
    category: str | None = None,
    industry: str | None = None,
    position: str | None = None,
    difficulty: str | None = None,
    q: str | None = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    scenes = await service.list_scenes(session, user.id, category, industry, position, difficulty, q, page, size)
    return ok([item.model_dump(by_alias=True) for item in scenes])


@router.get("/favorites")
async def favorite_scenes(user: CurrentUser, session: DbSession) -> dict:
    scenes = await service.list_favorites(session, user.id)
    return ok([item.model_dump(by_alias=True) for item in scenes])


@router.get("/{scene_id}")
async def get_scene(scene_id: str, session: DbSession, user: CurrentUser) -> dict:
    scene = await service.get_scene(session, scene_id)
    return ok(SceneView.model_validate(scene).model_dump(by_alias=True))


@router.post("/{scene_id}/favorite")
async def favorite(scene_id: str, user: CurrentUser, session: DbSession) -> dict:
    return ok({"favorite": await service.toggle_favorite(session, user.id, scene_id)})


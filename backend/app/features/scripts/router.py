from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import Script
from app.features.scripts.schemas import GenerateScriptsRequest, ScriptVersion
from app.features.scripts.service import generate
from app.infrastructure.rate_limit import limit_model_user

router = APIRouter(prefix="/scripts", tags=["话术生成"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.post("/generate", status_code=201)
async def generate_scripts(body: GenerateScriptsRequest, user: CurrentUser, session: DbSession) -> dict:
    await limit_model_user(user.id)
    result = await generate(session, user.id, body)
    return ok(result.model_dump(by_alias=True))


@router.get("")
async def history(user: CurrentUser, session: DbSession) -> dict:
    scripts = (
        await session.scalars(
            select(Script).where(Script.user_id == user.id).order_by(Script.created_at.desc()).limit(50)
        )
    ).all()
    return ok([ScriptVersion.model_validate(item).model_dump(by_alias=True) for item in scripts])


@router.get("/favorites")
async def favorite_scripts(user: CurrentUser, session: DbSession) -> dict:
    scripts = (
        await session.scalars(
            select(Script).where(Script.user_id == user.id, Script.favorite.is_(True))
            .order_by(Script.created_at.desc())
        )
    ).all()
    return ok([ScriptVersion.model_validate(item).model_dump(by_alias=True) for item in scripts])


@router.post("/{script_id}/favorite")
async def favorite(script_id: str, user: CurrentUser, session: DbSession) -> dict:
    script = await session.get(Script, script_id)
    if script is None or script.user_id != user.id:
        from app.core.errors import not_found

        raise not_found("话术版本")
    script.favorite = not script.favorite
    await session.commit()
    return ok({"favorite": script.favorite})


@router.delete("/{script_id}", status_code=204)
async def delete_version(script_id: str, user: CurrentUser, session: DbSession) -> Response:
    script = await session.get(Script, script_id)
    if script is None or script.user_id != user.id:
        raise not_found("话术版本")
    await session.delete(script)
    await session.commit()
    return Response(status_code=204)


"""编程笔试接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import CodingSubmission
from app.features.coding import service

router = APIRouter(prefix="/coding", tags=["编程笔试"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


class RunRequest(BaseModel):
    language: str = Field(default="python", pattern="^(python|javascript)$")
    code: str = Field(min_length=1, max_length=20000)


@router.get("/problems")
async def problems(user: CurrentUser) -> dict:
    return ok(service.list_problems())


@router.post("/problems/{problem_id}/run")
async def run(problem_id: str, body: RunRequest, user: CurrentUser, session: DbSession) -> dict:
    return ok(await service.judge(session, user.id, problem_id, body.language, body.code))


@router.get("/submissions")
async def submissions(user: CurrentUser, session: DbSession, limit: int = 10) -> dict:
    rows = (
        await session.scalars(
            select(CodingSubmission)
            .where(CodingSubmission.user_id == user.id)
            .order_by(CodingSubmission.created_at.desc())
            .limit(max(1, min(limit, 30)))
        )
    ).all()
    return ok(
        [
            {
                "id": row.id,
                "problemId": row.problem_id,
                "language": row.language,
                "passed": row.passed,
                "total": row.total,
                "durationMs": row.duration_ms,
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ]
    )

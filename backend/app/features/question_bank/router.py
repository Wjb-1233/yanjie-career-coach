"""题库：把各场景的题目聚合成可筛选、可收藏、可标记掌握度的练习清单。"""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import QuestionBankState, Scene
from app.features.scenes.taxonomy import normalize_bank

router = APIRouter(prefix="/question-bank", tags=["题库"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


def question_id(scene_id: str, text: str) -> str:
    return hashlib.sha1(f"{scene_id}:{text}".encode("utf-8")).hexdigest()[:16]


def _item(scene: Scene, question: dict) -> dict:
    return {
        "id": question_id(scene.id, question["text"]),
        "text": question["text"],
        "dimension": question.get("dimension"),
        "difficulty": question.get("difficulty") or scene.difficulty,
        "sceneId": scene.id,
        "sceneTitle": scene.title,
        "category": scene.category,
        "industry": scene.industry,
        "position": scene.position,
    }


@router.get("")
async def list_questions(
    user: CurrentUser,
    session: DbSession,
    industry: str | None = None,
    position: str | None = None,
    category: str | None = None,
    difficulty: str | None = None,
    query: str = "",
    favorite: bool = False,
    state: str = Query(default="all", pattern="^(all|mastered|unmastered)$"),
    page: int = 1,
    size: int = 20,
) -> dict:
    scenes = (await session.scalars(select(Scene).where(Scene.active.is_(True)))).all()
    rows = (
        await session.scalars(select(QuestionBankState).where(QuestionBankState.user_id == user.id))
    ).all()
    states = {row.question_id: row for row in rows}

    items: list[dict] = []
    for scene in scenes:
        for question in normalize_bank(scene.question_bank):
            item = _item(scene, question)
            state_row = states.get(item["id"])
            item["favorite"] = bool(state_row and state_row.favorite)
            item["mastered"] = bool(state_row and state_row.mastered)
            items.append(item)

    facets = {
        "industries": sorted({item["industry"] for item in items if item["industry"]}),
        "positions": sorted({item["position"] for item in items if item["position"]}),
        "categories": sorted({item["category"] for item in items if item["category"]}),
        "difficulties": sorted({item["difficulty"] for item in items if item["difficulty"]}),
    }
    counts = {
        "total": len(items),
        "favorite": sum(1 for item in items if item["favorite"]),
        "mastered": sum(1 for item in items if item["mastered"]),
    }

    needle = query.strip().lower()
    filtered = [
        item
        for item in items
        if (not industry or item["industry"] == industry)
        and (not position or item["position"] == position)
        and (not category or item["category"] == category)
        and (not difficulty or item["difficulty"] == difficulty)
        and (not favorite or item["favorite"])
        and (state == "all" or (state == "mastered") == item["mastered"])
        and (
            not needle
            or needle in item["text"].lower()
            or needle in item["sceneTitle"].lower()
            or needle in (item["dimension"] or "").lower()
        )
    ]

    size = max(1, min(size, 50))
    page = max(1, min(page, 500))
    start = (page - 1) * size
    return ok(
        {
            "items": filtered[start : start + size],
            "total": len(filtered),
            "page": page,
            "size": size,
            "facets": facets,
            "counts": counts,
        }
    )


class StateRequest(BaseModel):
    favorite: bool | None = None
    mastered: bool | None = None


@router.put("/{id}")
async def set_state(id: str, body: StateRequest, user: CurrentUser, session: DbSession) -> dict:
    scenes = (await session.scalars(select(Scene).where(Scene.active.is_(True)))).all()
    exists = any(
        question_id(scene.id, question["text"]) == id
        for scene in scenes
        for question in normalize_bank(scene.question_bank)
    )
    if not exists:
        from app.core.errors import AppError

        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在")

    row = await session.get(QuestionBankState, {"user_id": user.id, "question_id": id})
    if row is None:
        row = QuestionBankState(user_id=user.id, question_id=id)
        session.add(row)
    if body.favorite is not None:
        row.favorite = body.favorite
    if body.mastered is not None:
        row.mastered = body.mastered
    await session.commit()
    return ok({"id": id, "favorite": bool(row.favorite), "mastered": bool(row.mastered)})

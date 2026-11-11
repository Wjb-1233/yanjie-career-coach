"""题库刷题：把 content/question-banks.json 与场景元信息合成可练习的题目清单。

题目 id 规则：json 里的题没有 id，用「场景 id + 题序」的确定性摘要
（q + sha1(sceneId#index) 前 16 位）。question_bank_states.question_id 是
String(32)，而最长的场景 id 本身就有 32 字符，直接拼 "-q3" 会超长，故用摘要。
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.db.models import QuestionBankState, Scene
from app.features.questionbank.schemas import (
    DimensionStat,
    QuestionBankItem,
    QuestionBankPage,
    QuestionBankSummary,
    SceneStat,
)

# 与本文件相对的仓库根：backend/app/features/questionbank/service.py → 上四级
_BANK_FILE = Path(__file__).resolve().parents[4] / "content" / "question-banks.json"

UNCATEGORIZED = "未分类"
# json 里有少量场景不在 seed 里（如历史 UUID 场景），按前缀兜底标题，避免列表出现空标题
FALLBACK_SCENES = {
    "scene-foundation-": ("基础表达训练", "基础能力提升"),
    "scene-general-": ("通用面试问题", "综合行业"),
    "scene-stage-": ("分段专项训练", "分段训练"),
    "scene-jd-": ("岗位专项训练", "岗位专项"),
}
UNKNOWN_SCENE = ("综合题库", "综合")


def question_id(scene_id: str, index: int) -> str:
    """场景 id + 题序的确定性 id，长度 17，稳定且不随进程/顺序变化。"""
    digest = hashlib.sha1((scene_id + "#" + str(index)).encode("utf-8")).hexdigest()
    return "q" + digest[:16]


def _load_questions() -> list[dict]:
    if not _BANK_FILE.is_file():
        return []
    bank = json.loads(_BANK_FILE.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for scene_id, questions in bank.items():
        for index, question in enumerate(questions, start=1):
            text = str(question.get("text") or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "id": question_id(scene_id, index),
                    "scene_id": scene_id,
                    "text": text,
                    "dimension": question.get("dimension") or None,
                }
            )
    return rows


QUESTIONS: list[dict] = _load_questions()
QUESTION_IDS = {row["id"] for row in QUESTIONS}
SCENE_IDS = sorted({row["scene_id"] for row in QUESTIONS})


def _rate(mastered: int, total: int) -> float:
    return round(mastered / total * 100, 1) if total else 0.0


async def _scene_labels(session: AsyncSession) -> dict[str, tuple[str, str]]:
    """一次查出全部相关场景，避免逐题查库（N+1）。"""
    if not SCENE_IDS:
        return {}
    rows = (
        await session.execute(
            select(Scene.id, Scene.title, Scene.category).where(Scene.id.in_(SCENE_IDS))
        )
    ).all()
    return {row.id: (row.title, row.category) for row in rows}


def _label(labels: dict[str, tuple[str, str]], scene_id: str) -> tuple[str, str]:
    if scene_id in labels:
        return labels[scene_id]
    for prefix, fallback in FALLBACK_SCENES.items():
        if scene_id.startswith(prefix):
            return fallback
    return UNKNOWN_SCENE


async def _states(session: AsyncSession, user_id: str) -> dict[str, QuestionBankState]:
    """当前用户的全部标记（题库总量有限，一次取完即可）。"""
    rows = (
        await session.scalars(select(QuestionBankState).where(QuestionBankState.user_id == user_id))
    ).all()
    return {row.question_id: row for row in rows}


def _flags(state: QuestionBankState | None) -> tuple[bool, bool]:
    if state is None:
        return False, False
    return bool(state.favorite), bool(state.mastered)


async def list_questions(
    session: AsyncSession,
    user_id: str,
    dimension: str | None = None,
    scene_id: str | None = None,
    favorite: bool | None = None,
    mastered: bool | None = None,
    page: int = 1,
    size: int = 20,
) -> QuestionBankPage:
    states = await _states(session, user_id)
    labels = await _scene_labels(session)
    items: list[QuestionBankItem] = []
    for row in QUESTIONS:
        is_favorite, is_mastered = _flags(states.get(row["id"]))
        if dimension and row["dimension"] != dimension:
            continue
        if scene_id and row["scene_id"] != scene_id:
            continue
        if favorite is not None and is_favorite != favorite:
            continue
        if mastered is not None and is_mastered != mastered:
            continue
        title, category = _label(labels, row["scene_id"])
        items.append(
            QuestionBankItem(
                id=row["id"],
                scene_id=row["scene_id"],
                scene_title=title,
                category=category,
                text=row["text"],
                dimension=row["dimension"],
                favorite=is_favorite,
                mastered=is_mastered,
            )
        )
    start = (page - 1) * size
    return QuestionBankPage(items=items[start : start + size], total=len(items), page=page, size=size)


async def summary(session: AsyncSession, user_id: str) -> QuestionBankSummary:
    states = await _states(session, user_id)
    labels = await _scene_labels(session)
    mastered_total = 0
    favorite_total = 0
    by_dimension: OrderedDict[str, list[int]] = OrderedDict()
    by_scene: OrderedDict[str, dict] = OrderedDict()
    for row in QUESTIONS:
        is_favorite, is_mastered = _flags(states.get(row["id"]))
        mastered_total += int(is_mastered)
        favorite_total += int(is_favorite)
        dimension = row["dimension"] or UNCATEGORIZED
        bucket = by_dimension.setdefault(dimension, [0, 0])
        bucket[0] += 1
        bucket[1] += int(is_mastered)
        title, category = _label(labels, row["scene_id"])
        scene = by_scene.setdefault(
            row["scene_id"],
            {"scene_id": row["scene_id"], "scene_title": title, "category": category, "total": 0, "mastered": 0},
        )
        scene["total"] += 1
        scene["mastered"] += int(is_mastered)
    total = len(QUESTIONS)
    return QuestionBankSummary(
        total=total,
        mastered=mastered_total,
        favorite=favorite_total,
        rate=_rate(mastered_total, total),
        dimensions=[
            DimensionStat(dimension=key, total=value[0], mastered=value[1], rate=_rate(value[1], value[0]))
            for key, value in by_dimension.items()
        ],
        scenes=[
            SceneStat(
                scene_id=value["scene_id"],
                scene_title=value["scene_title"],
                category=value["category"],
                total=value["total"],
                mastered=value["mastered"],
                rate=_rate(value["mastered"], value["total"]),
            )
            for value in by_scene.values()
        ],
    )


async def set_state(
    session: AsyncSession,
    user_id: str,
    target_id: str,
    favorite: bool | None,
    mastered: bool | None,
) -> dict:
    """upsert 自己的标记；未传的字段保持原值。"""
    if target_id not in QUESTION_IDS:
        raise not_found("题目")
    state = await session.get(QuestionBankState, (user_id, target_id))
    if state is None:
        state = QuestionBankState(
            user_id=user_id,
            question_id=target_id,
            favorite=bool(favorite),
            mastered=bool(mastered),
        )
        session.add(state)
    else:
        if favorite is not None:
            state.favorite = favorite
        if mastered is not None:
            state.mastered = mastered
    await session.commit()
    return {"questionId": target_id, "favorite": bool(state.favorite), "mastered": bool(state.mastered)}

"""STAR 故事库：把讲过的项目经历沉淀成可复用的结构化故事。

- 手动创建或从某次训练自动提取
- 记录使用次数，便于判断哪个故事讲得最熟
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.db.models import Message, Story, TrainingSession
from app.infrastructure.llm import llm_gateway

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """你是面试教练。从候选人的回答里提炼 STAR 故事（情境/任务/行动/结果）。
要求：
1. 只提炼有具体事实的段落，不要编造数字或经历；
2. 每个故事必须有 situation（背景）、task（任务）、action（做法）、result（结果）；
3. 若某段缺少结果，result 写「（未说明结果）」，不要虚构；
4. 最多提炼 3 个，去重后输出。

只输出 JSON：{"stories":[{"title":"不超过 16 字","situation":"...","task":"...","action":"...","result":"...","tags":["项目","协作"]}]}"""

MAX_STORIES = 30


def _clean(text: object, limit: int) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def normalize_story(raw: dict) -> dict | None:
    title = _clean(raw.get("title"), 30)
    situation = _clean(raw.get("situation"), 200)
    task = _clean(raw.get("task"), 200)
    action = _clean(raw.get("action"), 400)
    result = _clean(raw.get("result"), 200)
    if not title or not action:
        return None
    return {
        "title": title,
        "situation": situation,
        "task": task,
        "action": action,
        "result": result or "（未说明结果）",
        "tags": [_clean(tag, 10) for tag in (raw.get("tags") or [])][:3],
    }


def fallback_stories(messages: list[Message]) -> list[dict]:
    """模型不可用时：挑出最长且含数字的两段回答，按固定结构存放。"""
    worth = [
        message.content.strip()
        for message in messages
        if len(message.content.strip()) >= 40
    ]
    worth.sort(key=lambda text: (bool(re.search(r"\d", text)), len(text)), reverse=True)
    stories = []
    for text in worth[:2]:
        title = text[:16] + ("…" if len(text) > 16 else "")
        stories.append(
            {
                "title": title,
                "situation": "（从训练记录自动记录，建议补充背景）",
                "task": "（待补充）",
                "action": text[:400],
                "result": "（未说明结果）",
                "tags": ["自动提取"],
            }
        )
    return stories


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


async def list_stories(session: AsyncSession, user_id: str) -> list[Story]:
    return list(
        (
            await session.scalars(
                select(Story).where(Story.user_id == user_id).order_by(Story.updated_at.desc())
            )
        ).all()
    )


async def create_story(session: AsyncSession, user_id: str, payload: dict) -> Story:
    normalized = normalize_story(payload)
    if normalized is None:
        raise AppError(422, "STORY_INVALID", "故事需要标题与行动描述")
    total = await session.scalar(select(func.count()).select_from(Story).where(Story.user_id == user_id))
    if (total or 0) >= MAX_STORIES:
        raise AppError(422, "STORY_LIMIT", f"故事最多保留 {MAX_STORIES} 个，请先删除不常用的")
    story = Story(user_id=user_id, **normalized)
    session.add(story)
    await session.commit()
    await session.refresh(story)
    return story


async def update_story(session: AsyncSession, user_id: str, story_id: str, payload: dict) -> Story:
    story = await session.get(Story, story_id)
    if story is None or story.user_id != user_id:
        raise not_found("故事")
    merged = {
        "title": payload.get("title", story.title),
        "situation": payload.get("situation", story.situation),
        "task": payload.get("task", story.task),
        "action": payload.get("action", story.action),
        "result": payload.get("result", story.result),
        "tags": payload.get("tags", story.tags),
    }
    normalized = normalize_story(merged)
    if normalized is None:
        raise AppError(422, "STORY_INVALID", "故事需要标题与行动描述")
    for key, value in normalized.items():
        setattr(story, key, value)
    await session.commit()
    await session.refresh(story)
    return story


async def delete_story(session: AsyncSession, user_id: str, story_id: str) -> None:
    story = await session.get(Story, story_id)
    if story is None or story.user_id != user_id:
        raise not_found("故事")
    await session.delete(story)
    await session.commit()


async def extract_from_session(session: AsyncSession, user_id: str, session_id: str) -> list[Story]:
    """从一次训练里提取故事并入库（按标题去重）。"""
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")

    messages = list(
        (
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id, Message.speaker == "USER")
                .order_by(Message.round_no)
            )
        ).all()
    )
    if not messages:
        raise AppError(422, "STORY_NO_CONTENT", "这次训练还没有你的回答")

    candidates: list[dict] = []
    try:
        raw = await llm_gateway.complete_json(
            EXTRACT_PROMPT,
            json.dumps(
                {"answers": [message.content[:400] for message in messages[-10:]]},
                ensure_ascii=False,
            ),
            temperature=0.2,
        )
        for item in raw.get("stories") or []:
            normalized = normalize_story(item)
            if normalized:
                candidates.append(normalized)
    except Exception as exc:  # noqa: BLE001
        logger.warning("story.extract_degraded error_type=%s", type(exc).__name__)
        candidates = fallback_stories(messages)

    if not candidates:
        raise AppError(422, "STORY_NO_CONTENT", "没有提炼出可用的故事，回答可能缺少具体事实")

    existing = await list_stories(session, user_id)
    created: list[Story] = []
    for candidate in candidates:
        duplicate = any(_similar(candidate["title"], story.title) > 0.75 for story in existing)
        if duplicate:
            continue
        story = Story(user_id=user_id, source_session_id=session_id, **candidate)
        session.add(story)
        created.append(story)
    await session.commit()
    for story in created:
        await session.refresh(story)
    if not created:
        raise AppError(409, "STORY_DUPLICATE", "这些经历已经收录，无需重复添加")
    return created


async def mark_used(session: AsyncSession, user_id: str, story_id: str) -> Story:
    story = await session.get(Story, story_id)
    if story is None or story.user_id != user_id:
        raise not_found("故事")
    story.usage_count = (story.usage_count or 0) + 1
    await session.commit()
    await session.refresh(story)
    return story

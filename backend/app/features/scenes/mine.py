"""我的场景：学员自建私有场景的创建、编辑、删除与查询。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.db.models import Scene, TrainingSession
from app.features.scenes.schemas import SceneView
from app.features.scenes.service import _with_competency

CATEGORIES = {
    "HR 初面",
    "技术一面",
    "技术二面/复面",
    "交叉面/总监面",
    "HRBP/HR 终面",
    "大老板/高管终面",
    "基础能力提升",
    "自定义",
}
DIFFICULTIES = {"入门", "中级", "进阶"}
DIMENSIONS = {"内容与逻辑", "贴合问题", "信息完整", "表达干净"}
MAX_SCENES = 50
# 只保留汉字、字母与数字，标点全部忽略后再比相似度
PUNCT = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]")


def _similar(left: str, right: str) -> float:
    a, b = PUNCT.sub("", left), PUNCT.sub("", right)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _clean_questions(raw: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for item in raw:
        text = str(item.get("text") or "").strip()
        if len(text) < 2 or len(text) > 120:
            raise AppError(422, "QUESTION_INVALID", "每道问题需要在 2–120 字之间")
        if any(_similar(text, existing["text"]) > 0.85 for existing in cleaned):
            continue
        dimension = item.get("dimension") or None
        difficulty = item.get("difficulty") or None
        if dimension and dimension not in DIMENSIONS:
            dimension = None
        if difficulty and difficulty not in DIFFICULTIES:
            difficulty = None
        cleaned.append({"text": text, "dimension": dimension, "difficulty": difficulty})
    if len(cleaned) < 2:
        raise AppError(422, "QUESTIONS_TOO_FEW", "一场面试至少要有两个不同的问题")
    if len(cleaned) > 8:
        raise AppError(422, "QUESTIONS_TOO_MANY", "最多 8 个问题，太多会让单场训练过长")
    return cleaned


def _payload_fields(body) -> dict:
    category = body.category if body.category in CATEGORIES else "自定义"
    difficulty = body.difficulty if body.difficulty in DIFFICULTIES else "中级"
    background = (body.background or "").strip()
    goal = (body.goal or "").strip()
    if len(background) < 20:
        background = f"你正在应聘{body.position}（{body.industry}），这场是{category}。"
    if len(goal) < 10:
        goal = f"围绕{body.position}的核心要求做一次完整表达。"
    questions = _clean_questions(body.questions)
    return {
        "category": category,
        "title": body.title.strip(),
        "industry": body.industry.strip(),
        "position": body.position.strip(),
        "role_name": body.role_name.strip(),
        "difficulty": difficulty,
        "background": background[:500],
        "goal": goal[:300],
        "opening_line": (body.opening_line or "").strip()[:200],
        "question_bank": questions,
        "competency": (body.competency or "").strip()[:30] or None,
        "tags": [item.strip()[:20] for item in (body.tags or []) if item.strip()][:6],
    }


async def create_scene(session: AsyncSession, user_id: str, body) -> SceneView:
    existing = (
        await session.scalars(
            select(Scene).where(Scene.owner_id == user_id, Scene.active.is_(True))
        )
    ).all()
    if len(existing) >= MAX_SCENES:
        raise AppError(422, "SCENE_LIMIT", f"自建场景最多 {MAX_SCENES} 个，请先删除不再使用的")
    if any(item.title == body.title.strip() for item in existing):
        raise AppError(422, "SCENE_TITLE_DUPLICATE", "你已经有一个同名场景了，换个标题或直接编辑它")

    fields = _payload_fields(body)
    opening = fields.pop("opening_line") or f"你好，我是{fields['role_name']}，今天这场是{fields['category']}。"
    scene = Scene(
        owner_id=user_id,
        visibility="private",
        source="user",
        active=True,
        opening_line=opening,
        **fields,
    )
    session.add(scene)
    await session.commit()
    return SceneView.model_validate(_with_competency(scene))


async def list_my_scenes(session: AsyncSession, user_id: str) -> list[SceneView]:
    scenes = (
        await session.scalars(
            select(Scene)
            .where(Scene.owner_id == user_id, Scene.active.is_(True))
            .order_by(Scene.created_at.desc())
        )
    ).all()
    return [SceneView.model_validate(_with_competency(scene)) for scene in scenes]


async def _own_scene(session: AsyncSession, user_id: str, scene_id: str) -> Scene:
    scene = await session.get(Scene, scene_id)
    if scene is None or scene.owner_id != user_id or not scene.active:
        raise not_found("场景")
    return scene


async def update_scene(session: AsyncSession, user_id: str, scene_id: str, body) -> SceneView:
    scene = await _own_scene(session, user_id, scene_id)
    fields = _payload_fields(body)
    for key, value in fields.items():
        setattr(scene, key, value)
    if not scene.opening_line:
        scene.opening_line = f"你好，我是{scene.role_name}，今天这场是{scene.category}。"
    await session.commit()
    return SceneView.model_validate(_with_competency(scene))


async def delete_scene(session: AsyncSession, user_id: str, scene_id: str) -> None:
    scene = await _own_scene(session, user_id, scene_id)
    used = await session.scalar(
        select(TrainingSession.id).where(TrainingSession.scene_id == scene_id).limit(1)
    )
    # 已有训练记录时软删除，保留历史与会话外键
    scene.active = False
    await session.commit()
    return None


async def scene_usage(session: AsyncSession, user_id: str) -> dict:
    rows = (
        await session.scalars(
            select(Scene).where(Scene.owner_id == user_id, Scene.active.is_(True))
        )
    ).all()
    return {"count": len(rows), "limit": MAX_SCENES}

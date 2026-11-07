"""把一个场景复制成「我的场景」，用户可再改。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.db.models import Scene
from app.features.scenes.mine import MAX_SCENES
from app.features.scenes.schemas import SceneView
from app.features.scenes.service import _with_competency


def _bank_of(scene: Scene) -> list[dict]:
    bank = scene.question_bank or []
    questions: list[dict] = []
    for item in bank:
        if isinstance(item, str):
            questions.append({"text": item[:120], "dimension": None, "difficulty": None})
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if text:
                questions.append(
                    {
                        "text": text[:120],
                        "dimension": item.get("dimension"),
                        "difficulty": item.get("difficulty"),
                    }
                )
    return questions[:8] or [
        {"text": "请先做一个自我介绍", "dimension": "表达干净", "difficulty": None},
        {"text": "说说你在这个岗位方向上最有把握的一件事", "dimension": "贴合问题", "difficulty": None},
    ]


async def copy_scene(session: AsyncSession, user_id: str, scene_id: str) -> SceneView:
    source = await session.get(Scene, scene_id)
    if source is None or not source.active:
        raise not_found("场景")
    if source.owner_id is not None and source.owner_id != user_id:
        raise not_found("场景")

    owned = (
        await session.scalars(
            select(Scene).where(Scene.owner_id == user_id, Scene.active.is_(True))
        )
    ).all()
    if len(owned) >= MAX_SCENES:
        raise AppError(422, "SCENE_LIMIT", f"自建场景最多 {MAX_SCENES} 个，请先删除不再使用的")

    title = f"{source.title}（我的版本）"[:60]
    if any(item.title == title for item in owned):
        title = f"{source.title}（我的版本 {len(owned) + 1}）"[:60]

    scene = Scene(
        owner_id=user_id,
        visibility="private",
        source="copy",
        active=True,
        category=source.category,
        title=title,
        industry=source.industry,
        position=source.position,
        role_name=source.role_name,
        difficulty=source.difficulty,
        background=source.background,
        goal=source.goal,
        opening_line=source.opening_line,
        question_bank=_bank_of(source),
        competency=source.competency,
        tags=list(source.tags or [])[:6],
    )
    session.add(scene)
    await session.commit()
    return SceneView.model_validate(_with_competency(scene))

"""能力建模与个性化排程。

- Elo：每次评分后更新「学员 × 维度」能力值，场景难度由难度标签与历史得分估计
- 复习：错题带 due 日期，按 1/3/7 天递增
- 推荐：按能力值挑选难度匹配的场景，与到期错题、最弱维度微课一起组成计划
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation, MistakeState, Scene, SkillState, TrainingSession

DIMENSIONS = ["logic", "relevance", "correctness", "concision"]
DIFFICULTY_BASE = {"入门": 920.0, "中级": 1000.0, "进阶": 1080.0}
K_FACTOR = 24.0
INTERVALS = [1, 3, 7, 15]


def scene_rating(scene: Scene, average: float | None) -> float:
    base = DIFFICULTY_BASE.get(scene.difficulty, 1000.0)
    if average is None:
        return base
    if average >= 4:
        return base + 40
    if average <= 2.5:
        return base - 40
    return base


async def scene_average(session: AsyncSession, scene_id: str) -> float | None:
    value = await session.scalar(
        select(func.avg(Evaluation.overall_score))
        .join(TrainingSession, TrainingSession.id == Evaluation.session_id)
        .where(TrainingSession.scene_id == scene_id)
    )
    return round((value or 0) / 20, 2) if value else None


async def _skill(session: AsyncSession, user_id: str, dimension: str) -> SkillState:
    state = await session.scalar(
        select(SkillState).where(SkillState.user_id == user_id, SkillState.dimension == dimension)
    )
    if state is None:
        state = SkillState(user_id=user_id, dimension=dimension, rating=1000.0, attempts=0)
        session.add(state)
        await session.flush()
    return state


async def update_skills(
    session: AsyncSession,
    user_id: str,
    scene: Scene | None,
    scores: dict[str, int],
) -> dict[str, float]:
    """按 Elo 更新四个维度的能力值，返回更新后的分值。"""
    average = await scene_average(session, scene.id) if scene else None
    difficulty = scene_rating(scene, average) if scene else 1000.0
    updated: dict[str, float] = {}
    for dimension in DIMENSIONS:
        score = int(scores.get(dimension, 3))
        state = await _skill(session, user_id, dimension)
        expected = 1 / (1 + 10 ** ((difficulty - state.rating) / 400))
        actual = max(0.0, min(1.0, (score - 1) / 4))
        state.rating = round(state.rating + K_FACTOR * (actual - expected), 2)
        state.attempts += 1
        state.updated_at = datetime.now(timezone.utc)
        updated[dimension] = state.rating
    await session.flush()
    return updated


async def skill_snapshot(session: AsyncSession, user_id: str) -> dict[str, float]:
    rows = (await session.scalars(select(SkillState).where(SkillState.user_id == user_id))).all()
    return {row.dimension: row.rating for row in rows}


async def next_due(session: AsyncSession, user_id: str) -> list[dict]:
    """到期该复习的错题（含场景与维度）。"""
    now = datetime.now(timezone.utc)
    rows = (
        await session.scalars(
            select(MistakeState)
            .where(
                MistakeState.user_id == user_id,
                MistakeState.due_at.is_not(None),
                MistakeState.due_at <= now,
            )
            .order_by(MistakeState.due_at)
            .limit(5)
        )
    ).all()
    return [
        {
            "sessionId": row.session_id,
            "roundNo": row.round_no,
            "dimension": row.dimension,
            "dueAt": row.due_at,
            "review": row.status == "RESOLVED",
        }
        for row in rows
    ]


def schedule_review(state: MistakeState, now: datetime | None = None) -> None:
    """标记复习成功：间隔按 1/3/7/15 天递增。"""
    now = now or datetime.now(timezone.utc)
    streak = int(state.streak or 0)
    index = min(len(INTERVALS) - 1, max(0, streak))
    state.streak = min(len(INTERVALS) - 1, streak + 1)
    state.due_at = now + timedelta(days=INTERVALS[index])


async def target_dimensions(session: AsyncSession, user_id: str, limit: int = 2) -> list[str]:
    """能力值最低的一到两个维度。"""
    ratings = await skill_snapshot(session, user_id)
    if not ratings:
        return []
    ordered = sorted(ratings.items(), key=lambda item: item[1])
    return [dimension for dimension, _ in ordered[:limit]]


async def recommend_scenes(
    session: AsyncSession, user_id: str, limit: int = 2
) -> list[tuple[Scene, str]]:
    """按「最弱维度匹配度 × 难度接近度」挑场景，返回 (场景, 针对维度)。"""
    from app.features.plans.scene_fit import affinity

    ratings = await skill_snapshot(session, user_id)
    targets = await target_dimensions(session, user_id, limit=2)
    weakest = min(ratings.values()) if ratings else 1000.0
    recent = (
        await session.scalars(
            select(TrainingSession.scene_id)
            .where(TrainingSession.user_id == user_id)
            .order_by(TrainingSession.started_at.desc())
            .limit(3)
        )
    ).all()
    scenes = (
        await session.scalars(
            select(Scene).where(
                Scene.active.is_(True),
                or_(Scene.visibility == 'public', Scene.owner_id == user_id),
            )
        )
    ).all()
    if scenes and all(scene.scene_fit is None for scene in scenes):
        from app.features.plans.scene_fit import refresh_scene_fit

        await refresh_scene_fit(session)
        scenes = (
            await session.scalars(
                select(Scene).where(
                    Scene.active.is_(True),
                    or_(Scene.visibility == 'public', Scene.owner_id == user_id),
                )
            )
        ).all()
    scored: list[tuple[float, Scene, str]] = []
    for scene in scenes:
        if scene.id in recent:
            continue
        average = await scene_average(session, scene.id)
        gap = abs(scene_rating(scene, average) - weakest)
        difficulty_fit = max(0.0, 1 - gap / 300)
        match = affinity(scene, targets) if targets else 0.5
        dimension = max(
            targets or ["logic"],
            key=lambda item: (scene.scene_fit or {}).get(item, 0.25),
        )
        scored.append((0.55 * match + 0.45 * difficulty_fit, scene, dimension))
    scored.sort(key=lambda item: item[0], reverse=True)
    # 两场尽量针对不同维度
    picked: list[tuple[Scene, str]] = []
    used: set[str] = set()
    for _, scene, dimension in scored:
        if dimension in used and len(picked) < len(targets):
            continue
        picked.append((scene, dimension))
        used.add(dimension)
        if len(picked) >= limit:
            break
    if len(picked) < limit:
        for _, scene, dimension in scored:
            if all(scene.id != item[0].id for item in picked):
                picked.append((scene, dimension))
            if len(picked) >= limit:
                break
    # 最弱维度排最前
    order = {dimension: index for index, dimension in enumerate(targets)}
    picked.sort(key=lambda item: order.get(item[1], 99))
    return picked[:limit]

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import Evaluation, TrainingPlan, TrainingSession

router = APIRouter(prefix="/dashboard", tags=["成长看板"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def dashboard(user: CurrentUser, session: DbSession) -> dict:
    evaluations = (
        await session.scalars(
            select(Evaluation)
            .where(Evaluation.user_id == user.id)
            .order_by(Evaluation.created_at.desc())
            .limit(20)
        )
    ).all()
    plans = (
        await session.scalars(
            select(TrainingPlan)
            .where(TrainingPlan.user_id == user.id, TrainingPlan.status == "ACTIVE")
            .order_by(TrainingPlan.created_at.desc())
            .limit(3)
        )
    ).all()
    sessions_count = await session.scalar(
        select(func.count()).select_from(TrainingSession).where(
            TrainingSession.user_id == user.id,
            TrainingSession.status == "FINISHED",
        )
    )
    latest = evaluations[0] if evaluations else None
    dimensions = (
        {
            "logic": latest.logic_score,
            "appropriateness": latest.appropriateness_score,
            "impact": latest.impact_score,
            "relevance": latest.relevance_score,
            "concision": latest.concision_score,
        }
        if latest
        else {"logic": 0, "appropriateness": 0, "impact": 0, "relevance": 0, "concision": 0}
    )
    score_keys = ("logic", "appropriateness", "impact", "relevance", "concision")
    dimension_labels = {
        "logic": "逻辑性",
        "appropriateness": "得体性",
        "impact": "感染力",
        "relevance": "针对性",
        "concision": "简洁度",
    }
    dimension_averages = {
        key: round(sum(getattr(item, f"{key}_score") for item in evaluations) / len(evaluations), 2)
        for key in score_keys
    } if evaluations else {}
    weaknesses = [
        {"dimension": dimension_labels[key], "averageScore": value, "sampleCount": len(evaluations)}
        for key, value in sorted(dimension_averages.items(), key=lambda pair: pair[1])[:2]
    ]
    tag_counts: dict[str, int] = {}
    for evaluation in evaluations:
        for tag in evaluation.style_tags or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    style_tags = [
        f"{tag} ×{count}"
        for tag, count in sorted(tag_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:3]
    ] or ["等待首次训练"]
    trends = [
        {
            "date": item.created_at.date().isoformat(),
            "score": item.overall_score,
            "dimensions": {
                "logic": item.logic_score,
                "appropriateness": item.appropriateness_score,
                "impact": item.impact_score,
                "relevance": item.relevance_score,
                "concision": item.concision_score,
            },
        }
        for item in reversed(evaluations)
    ]
    return ok(
        {
            "trainingCount": sessions_count or 0,
            "latestScore": latest.overall_score if latest else 0,
            "dimensions": dimensions,
            "styleTags": style_tags,
            "weaknesses": weaknesses,
            "trends": trends,
            "plans": [
                {
                    "id": plan.id,
                    "title": plan.title,
                    "focusDimension": plan.focus_dimension,
                    "tasks": plan.tasks,
                }
                for plan in plans
            ],
        }
    )


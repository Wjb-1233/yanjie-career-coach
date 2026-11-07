"""个人数据导出：给学员一份可带走的 JSON（合规与信任）。

包含：账号资料、训练会话与逐轮原文、评分与证据、训练计划、话术、故事。
不包含：他人数据、内部管理字段、模型提示词。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Evaluation,
    EvaluationEvidence,
    Message,
    Scene,
    Script,
    Story,
    TrainingPlan,
    TrainingSession,
    User,
)

SCHEMA_VERSION = 1


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def export_user_data(session: AsyncSession, user: User) -> dict:
    sessions = (
        await session.scalars(
            select(TrainingSession)
            .where(TrainingSession.user_id == user.id)
            .order_by(TrainingSession.started_at)
        )
    ).all()
    scene_ids = {item.scene_id for item in sessions}
    scenes = {}
    if scene_ids:
        rows = (await session.scalars(select(Scene).where(Scene.id.in_(scene_ids)))).all()
        scenes = {row.id: row for row in rows}

    evaluation_rows = (
        await session.scalars(select(Evaluation).where(Evaluation.user_id == user.id))
    ).all()
    evaluations = {row.session_id: row for row in evaluation_rows}

    evidence_rows = (
        await session.scalars(
            select(EvaluationEvidence).where(
                EvaluationEvidence.evaluation_id.in_([row.id for row in evaluation_rows] or [""])
            )
        )
    ).all()
    evidence_by_eval: dict[str, list[EvaluationEvidence]] = {}
    for row in evidence_rows:
        evidence_by_eval.setdefault(row.evaluation_id, []).append(row)

    messages = (
        await session.scalars(
            select(Message)
            .where(Message.session_id.in_([item.id for item in sessions] or [""]))
            .order_by(Message.round_no, Message.created_at)
        )
    ).all()
    messages_by_session: dict[str, list[Message]] = {}
    for row in messages:
        messages_by_session.setdefault(row.session_id, []).append(row)

    payload_sessions = []
    for item in sessions:
        evaluation = evaluations.get(item.id)
        payload_sessions.append(
            {
                "id": item.id,
                "sceneTitle": scenes[item.scene_id].title if item.scene_id in scenes else None,
                "channel": item.channel,
                "status": item.status,
                "startedAt": _iso(item.started_at),
                "finishedAt": _iso(item.finished_at),
                "durationSeconds": item.duration_seconds,
                "rounds": [
                    {"round": row.round_no, "speaker": row.speaker, "content": row.content, "at": _iso(row.created_at)}
                    for row in messages_by_session.get(item.id, [])
                ],
                "evaluation": (
                    {
                        "overallScore": evaluation.overall_score,
                        "scores": {
                            "logic": evaluation.logic_score,
                            "relevance": evaluation.relevance_score,
                            "correctness": evaluation.correctness_score,
                            "concision": evaluation.concision_score,
                        },
                        "summary": evaluation.summary,
                        "suggestions": evaluation.suggestions,
                        "degraded": evaluation.degraded,
                        "evidence": [
                            {
                                "round": evidence.round_no,
                                "dimension": evidence.dimension,
                                "quote": evidence.quote,
                                "reason": evidence.reason,
                            }
                            for evidence in evidence_by_eval.get(evaluation.id, [])
                        ],
                    }
                    if evaluation
                    else None
                ),
            }
        )

    plans = (
        await session.scalars(
            select(TrainingPlan)
            .where(TrainingPlan.user_id == user.id)
            .order_by(TrainingPlan.sequence)
        )
    ).all()
    scripts = (
        await session.scalars(
            select(Script).where(Script.user_id == user.id).order_by(Script.created_at)
        )
    ).all()
    stories = (
        await session.scalars(
            select(Story).where(Story.user_id == user.id).order_by(Story.created_at)
        )
    ).all()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "account": {
            "id": user.id,
            "email": user.email,
            "displayName": user.display_name,
            "bio": user.bio,
            "createdAt": _iso(user.created_at),
        },
        "sessions": payload_sessions,
        "plans": [
            {
                "id": plan.id,
                "sequence": plan.sequence,
                "status": plan.status,
                "createdAt": _iso(plan.created_at),
                "tasks": plan.tasks,
            }
            for plan in plans
        ],
        "scripts": [
            {
                "id": item.id,
                "sceneId": item.scene_id,
                "style": item.style,
                "original": item.original,
                "content": item.content,
                "createdAt": _iso(item.created_at),
            }
            for item in scripts
        ],
        "stories": [
            {
                "id": item.id,
                "title": item.title,
                "situation": item.situation,
                "task": item.task,
                "action": item.action,
                "result": item.result,
                "tags": item.tags,
                "createdAt": _iso(item.created_at),
            }
            for item in stories
        ],
    }

"""把一次语音对练的转写文本落成一个训练会话，接上现有评分链路。"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.db.models import Message, Scene, TrainingSession


async def create_voice_session(
    session: AsyncSession,
    user_id: str,
    scene_id: str,
    turns: list[dict],
    duration_seconds: int | None = None,
    delivery: dict | None = None,
    engine: str = "doubao",
) -> str:
    scene = await session.get(Scene, scene_id)
    if scene is None:
        raise not_found("场景")
    if not turns:
        raise AppError(422, "VOICE_SESSION_EMPTY", "这次通话没有可评分的对话内容")

    cleaned: list[tuple[str, str]] = []
    for turn in turns:
        question = str(turn.get("question", "")).strip()
        answer = str(turn.get("answer", "")).strip()
        if not answer:
            continue
        cleaned.append((question or "请继续。", answer))
    if not cleaned:
        raise AppError(422, "VOICE_SESSION_EMPTY", "这次通话没有可评分的回答")

    now = datetime.now(timezone.utc)
    training = TrainingSession(
        user_id=user_id,
        scene_id=scene.id,
        status="ACTIVE",
        stage="CLOSING",
        current_round=len(cleaned),
        covered_count=len(cleaned),
        channel="VOICE",
        duration_seconds=duration_seconds,
        delivery={**(delivery or {}), "engine": engine},
        started_at=now,
    )
    session.add(training)
    await session.flush()

    for index, (question, answer) in enumerate(cleaned, start=1):
        session.add(
            Message(
                session_id=training.id,
                round_no=index,
                speaker="AI",
                content=question,
            )
        )
        session.add(
            Message(
                session_id=training.id,
                round_no=index,
                speaker="USER",
                content=answer,
            )
        )

    await session.commit()
    return training.id


async def latest_scene_title(session: AsyncSession, scene_id: str) -> str:
    title = await session.scalar(select(Scene.title).where(Scene.id == scene_id))
    return title or "语音对练"

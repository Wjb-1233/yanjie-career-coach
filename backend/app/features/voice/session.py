"""把一次语音对练的转写文本落成一个训练会话，接上现有评分链路。"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from difflib import SequenceMatcher

from app.db.models import Message, Scene, TrainingSession
from app.features.scenes.service import get_scene
from app.features.scenes.taxonomy import normalize_bank


# 录像降级时占位作答：评分链路需要至少两轮，画面指标仍在，只是没有文字可评
DEGRADED_ANSWER = "（这段录像里没有识别到作答内容，以下评分只依据画面表现与题目）"
DEGRADED_FALLBACK_QUESTIONS = ("请做一个简单的自我介绍。", "请介绍一个你最近完成的项目。")


def _degraded_turns(questions: list[str]) -> list[tuple[str, str]]:
    """转写为空时用题目占位，保证至少两轮，会话与报告都还能建起来。"""
    pool = [str(item).strip() for item in questions if str(item).strip()]
    for extra in DEGRADED_FALLBACK_QUESTIONS:
        if len(pool) >= 2:
            break
        pool.append(extra)
    return [(question, DEGRADED_ANSWER) for question in pool]


def _coverage(scene: Scene, questions: list[str]) -> int:
    """按文本相似度判断必问题是否真的被问到，而不是直接按轮次算。"""
    bank = normalize_bank(scene.question_bank)
    if not bank or not questions:
        return 0
    covered = 0
    for item in bank:
        target = str(item.get("text", "")).strip()
        if not target:
            continue
        best = max(
            (SequenceMatcher(None, target, question).ratio() for question in questions),
            default=0.0,
        )
        if best >= 0.55:
            covered += 1
    return covered


async def create_voice_session(
    session: AsyncSession,
    user_id: str,
    scene_id: str,
    turns: list[dict],
    duration_seconds: int | None = None,
    delivery: dict | None = None,
    engine: str = "doubao",
    channel: str = "VOICE",
    recording_path: str | None = None,
    degraded_reason: str | None = None,
) -> str:
    scene = await get_scene(session, scene_id, user_id)
    if not turns and not degraded_reason:
        raise AppError(422, "VOICE_SESSION_EMPTY", "这次通话没有可评分的对话内容")

    cleaned: list[tuple[str, str]] = []
    for turn in turns:
        question = str(turn.get("question", "")).strip()
        answer = str(turn.get("answer", "")).strip()
        if not answer:
            continue
        cleaned.append((question or "请继续。", answer))
    if not cleaned:
        if not degraded_reason:
            raise AppError(422, "VOICE_SESSION_EMPTY", "这次通话没有可评分的回答")
        # 录像降级：没有文字作答也留一份可回放、可评分的会话，别让整段录像白录
        marks = [
            str(item.get("text", ""))
            for item in (delivery or {}).get("marks") or []
            if isinstance(item, dict)
        ]
        cleaned = _degraded_turns(marks)
        delivery = {**(delivery or {}), "transcriptReason": degraded_reason}

    now = datetime.now(timezone.utc)
    training = TrainingSession(
        user_id=user_id,
        scene_id=scene.id,
        status="ACTIVE",
        stage="CLOSING",
        current_round=len(cleaned),
        covered_count=_coverage(scene, [question for question, _ in cleaned]),
        question_plan=normalize_bank(scene.question_bank),
        channel=channel,
        duration_seconds=duration_seconds,
        delivery={**(delivery or {}), "engine": engine},
        recording_path=recording_path,
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

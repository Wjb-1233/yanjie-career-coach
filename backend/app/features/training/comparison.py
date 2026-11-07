"""同题横向对比：同一道题在不同场次里的回答并排看。"""

from __future__ import annotations

from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.db.models import Evaluation, Message, TrainingSession

SIMILARITY = 0.55
PUNCT = re.compile(r"[\s，。！？、；：""''（）()《》〈〉…—·.!?;:'\"()\[\]{}-]")


def _normalize(text: str) -> str:
    # 题目里可能带「（考察：信息完整）」这样的后缀，比对前去掉
    cleaned = re.sub(r"（考察：[^）]*）", "", text or "")
    return PUNCT.sub("", cleaned)


def _similar(left: str, right: str) -> float:
    a, b = _normalize(left), _normalize(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


async def same_question_attempts(
    session: AsyncSession,
    user_id: str,
    session_id: str,
    round_no: int,
    limit: int = 5,
) -> list[dict]:
    current = await session.get(TrainingSession, session_id)
    if current is None or current.user_id != user_id:
        raise not_found("训练会话")

    current_messages = (
        await session.scalars(
            select(Message).where(Message.session_id == session_id).order_by(Message.round_no, Message.created_at)
        )
    ).all()
    question = ""
    for index, message in enumerate(current_messages):
        if message.speaker == "AI" and message.round_no == round_no:
            question = message.content
            break
    if not question:
        raise not_found("这一轮的题目")

    candidates = (
        await session.scalars(
            select(TrainingSession)
            .where(
                TrainingSession.user_id == user_id,
                TrainingSession.scene_id == current.scene_id,
                TrainingSession.status == "FINISHED",
            )
            .order_by(TrainingSession.started_at.desc())
            .limit(40)
        )
    ).all()

    attempts: list[dict] = []
    for item in candidates:
        if item.id == session_id:
            continue  # 当前这次不算「历史作答」
        messages = (
            await session.scalars(
                select(Message).where(Message.session_id == item.id).order_by(Message.round_no, Message.created_at)
            )
        ).all()
        for index, message in enumerate(messages):
            if message.speaker != "AI":
                continue
            if _similar(question, message.content) < SIMILARITY:
                continue
            answer = next(
                (later.content for later in messages[index + 1:] if later.speaker == "USER"),
                "",
            )
            if not answer.strip():
                continue
            evaluation = await session.scalar(select(Evaluation).where(Evaluation.session_id == item.id))
            attempts.append(
                {
                    "sessionId": item.id,
                    "startedAt": item.started_at.isoformat(),
                    "isCurrent": item.id == session_id,
                    "question": message.content,
                    "answer": answer,
                    "roundNo": message.round_no,
                    "overallScore": evaluation.overall_score if evaluation else None,
                    "scores": {
                        "logic": evaluation.logic_score,
                        "relevance": evaluation.relevance_score,
                        "correctness": evaluation.correctness_score,
                        "concision": evaluation.concision_score,
                    }
                    if evaluation
                    else None,
                    "channel": item.channel,
                }
            )
            break
        if len(attempts) >= limit:
            break

    attempts.sort(key=lambda item: item["startedAt"], reverse=True)
    return attempts

"""教练查看链接：带过期签名的只读访问 + 时间点批注。

链接本身是 HMAC 令牌，不需要登录；只能读取一次会话的报告摘要，
可以追加时间点批注，不能修改评分或访问其他会话。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.errors import AppError, not_found
from app.core.responses import ok
from app.core.schemas import ApiModel
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import Evaluation, Scene, TrainingSession
from app.features.recordings import storage

router = APIRouter(prefix="/share", tags=["教练查看"])
DbSession = Annotated[AsyncSession, Depends(get_session)]

DEFAULT_TTL_SECONDS = 7 * 24 * 3600
MAX_ANNOTATIONS = 50


def _secret() -> bytes:
    return (settings.jwt_secret or "career-coach-share").encode("utf-8")


def issue_token(session_id: str, ttl: int = DEFAULT_TTL_SECONDS) -> tuple[str, int]:
    expires = int(time.time()) + ttl
    payload = json.dumps({"sid": session_id, "exp": expires}, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{signature}", expires


def read_token(token: str) -> str:
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        raise not_found("链接")
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature, expected):
        raise not_found("链接")
    padded = body + "=" * (-len(body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:  # noqa: BLE001
        raise not_found("链接")
    if int(payload.get("exp") or 0) < int(time.time()):
        raise AppError(410, "SHARE_EXPIRED", "这个链接已过期，请让学员重新生成")
    return str(payload.get("sid"))


class AnnotationRequest(ApiModel):
    at_ms: int = Field(default=0, ge=0, le=3_600_000)
    comment: str = Field(min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=40)


@router.post("/training-sessions/{session_id}")
async def create_share_link(
    session_id: str, user: CurrentUser, session: DbSession
) -> dict:
    """学员本人生成教练查看链接（默认 7 天）。"""
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user.id:
        raise not_found("训练会话")
    token, expires = issue_token(session_id)
    return ok({"url": f"/share/{token}", "expiresAt": expires})


@router.get("/{token}")
async def read_shared(token: str, session: DbSession) -> dict:
    """教练打开链接：返回摘要、转写和批注，不含其他个人信息。"""
    session_id = read_token(token)
    training = await session.get(TrainingSession, session_id)
    if training is None:
        raise not_found("训练会话")
    scene = await session.get(Scene, training.scene_id)
    evaluation = await session.scalar(select_evaluation(session_id))
    delivery = training.delivery or {}
    return ok(
        {
            "sceneTitle": scene.title if scene else "历史场景",
            "channel": training.channel,
            "startedAt": training.started_at.isoformat(),
            "overallScore": evaluation.overall_score if evaluation else None,
            "scores": {
                "logic": evaluation.logic_score,
                "relevance": evaluation.relevance_score,
                "correctness": evaluation.correctness_score,
                "concision": evaluation.concision_score,
            }
            if evaluation
            else None,
            "summary": evaluation.summary if evaluation else None,
            "recordingUrl": storage.signed_url(training.recording_path),
            "transcript": delivery.get("transcript") or [],
            "annotations": delivery.get("annotations") or [],
            "expiresIn": 0,
        }
    )


@router.post("/{token}/annotations")
async def add_annotation(
    token: str, body: AnnotationRequest, session: DbSession
) -> dict:
    """教练在某个时间点留一条批注。"""
    session_id = read_token(token)
    training = await session.get(TrainingSession, session_id)
    if training is None:
        raise not_found("训练会话")
    delivery = dict(training.delivery or {})
    annotations = list(delivery.get("annotations") or [])
    if len(annotations) >= MAX_ANNOTATIONS:
        raise AppError(422, "ANNOTATION_LIMIT", "这条链接的批注数量已达上限")
    annotations.append(
        {
            "atMs": body.at_ms,
            "comment": body.comment.strip(),
            "author": (body.author or "教练").strip()[:40],
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    delivery["annotations"] = annotations
    training.delivery = delivery
    flag_modified(training, "delivery")
    await session.commit()
    return ok({"annotations": annotations})


def select_evaluation(session_id: str):
    from sqlalchemy import select

    return select(Evaluation).where(Evaluation.session_id == session_id)

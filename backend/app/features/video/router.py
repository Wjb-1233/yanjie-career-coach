"""视频面试：上传一段录像，拆出每道题的作答，并分析镜头表现。"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.models import Scene
from app.features.evaluations.delivery import analyze
from app.features.video.metrics import analyze_video
from app.features.voice.session import create_voice_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video-interviews", tags=["video-interviews"])

MAX_BYTES = 200 * 1024 * 1024


def _split_turns(questions: list[dict], words: list[dict]) -> list[dict]:
    """按题目时间窗把逐词转写切成每一轮的问答。"""
    turns: list[dict] = []
    for item in questions:
        text = str(item.get("text") or "").strip()
        start = float(item.get("start") or 0)
        end = float(item.get("end") or 0)
        if not text or end <= start:
            continue
        answer = "".join(
            word["text"] for word in words if start <= float(word["start"]) < end
        ).strip()
        if answer:
            turns.append({"question": text, "answer": answer})
    return turns


@router.post("", status_code=201)
async def create_video_interview(
    scene_id: Annotated[str, Form(alias="sceneId")],
    questions: Annotated[str, Form()],
    video: Annotated[UploadFile, File()],
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    duration_seconds: Annotated[float | None, Form(alias="durationSeconds")] = None,
):
    scene = await session.get(Scene, scene_id)
    if scene is None:
        raise AppError(404, "SCENE_NOT_FOUND", "场景不存在")

    import json

    try:
        parsed = json.loads(questions)
    except json.JSONDecodeError as exc:
        raise AppError(422, "QUESTIONS_INVALID", "题目时间轴格式不正确") from exc
    if not isinstance(parsed, list) or not parsed:
        raise AppError(422, "QUESTIONS_INVALID", "至少需要一道题")

    suffix = Path(video.filename or "answer.webm").suffix or ".webm"
    work = Path(tempfile.mkdtemp())
    target = work / f"answer{suffix}"
    size = 0
    with target.open("wb") as handle:
        while chunk := await video.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                shutil.rmtree(work, ignore_errors=True)
                raise AppError(413, "VIDEO_TOO_LARGE", "录像超过 200MB，请缩短时长")
            handle.write(chunk)

    try:
        delivery = await asyncio.to_thread(analyze, target)
        vision = await asyncio.to_thread(analyze_video, target)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    words = delivery.get("words", []) if delivery else []
    turns = _split_turns(parsed, words)
    if len(turns) < 1:
        raise AppError(422, "VIDEO_NO_SPEECH", "录像里没有识别到作答内容，请检查麦克风")

    if delivery:
        delivery.pop("words", None)
    payload = {**(delivery or {}), "vision": vision, "engine": "video"}
    if duration_seconds:
        payload["durationSeconds"] = round(float(duration_seconds), 1)

    session_id = await create_voice_session(
        session,
        user.id,
        scene_id,
        turns,
        duration_seconds=int(duration_seconds or 0) or None,
        delivery=payload,
        engine="video",
        channel="VIDEO",
    )
    return ok({"id": session_id, "vision": vision, "delivery": payload})

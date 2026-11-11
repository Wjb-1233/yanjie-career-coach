"""视频面试：上传一段录像，拆出每道题的作答，并分析镜头表现。"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser
from app.features.auth.email_verify import require_verified
from app.features.evaluations.delivery import analyze
from app.features.video.metrics import analyze_video
from app.features.scenes.service import get_scene
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
        picked = [word for word in words if start <= float(word["start"]) < end]
        answer = "".join(word["text"] for word in picked).strip()
        if answer:
            probs = [float(word.get("p") or 0) for word in picked if word.get("p")]
            turns.append({
                "question": text,
                "answer": answer,
                "startMs": int(start * 1000),
                "endMs": int(end * 1000),
                "confidence": round(sum(probs) / len(probs), 2) if probs else None,
            })
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
    require_verified(user)
    await get_scene(session, scene_id, user.id)

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

    from app.features.recordings import storage
    from app.features.tasks.service import create_task

    try:
        recording_path = await asyncio.to_thread(storage.save_file, target, suffix)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    task = await create_task(
        user.id,
        "VIDEO_INTERVIEW",
        {
            "sceneId": scene_id,
            "questions": parsed,
            "durationSeconds": float(duration_seconds or 0),
            "recording": recording_path,
        },
    )
    return JSONResponse(
        status_code=202,
        content=ok(
            {
                "taskId": task.id,
                "status": task.status,
                "recordingUrl": storage.url_of(recording_path),
            }
        ),
    )

"""长任务队列：视频分析这类耗时操作改为后台执行，前端轮询进度。

任务状态落在数据库里，进程重启后未完成的任务会重新排队。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import AnalysisTask

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1.5
_running: asyncio.Task | None = None
_stop = asyncio.Event()


async def create_task(user_id: str, kind: str, payload: dict) -> AnalysisTask:
    async with session_factory() as session:
        task = AnalysisTask(user_id=user_id, kind=kind, payload=payload, status="PENDING", progress=0)
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def _update(task_id: str, **fields) -> None:
    async with session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
        if task is None:
            return
        for key, value in fields.items():
            setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def _claim_next() -> AnalysisTask | None:
    async with session_factory() as session:
        task = await session.scalar(
            select(AnalysisTask)
            .where(AnalysisTask.status == "PENDING")
            .order_by(AnalysisTask.created_at)
            .limit(1)
        )
        if task is None:
            return None
        task.status = "RUNNING"
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return task


async def process_video_interview(task: AnalysisTask) -> None:
    """视频面试：转写 → 镜头分析 → 建会话 → 评分。"""
    from app.features.evaluations.delivery import analyze
    from app.features.evaluations.service import evaluate_session
    from app.features.recordings import storage
    from app.features.video.metrics import analyze_video
    from app.features.video.router import _split_turns
    from app.features.voice.session import create_voice_session

    payload = task.payload or {}
    recording = payload.get("recording")
    questions = payload.get("questions") or []
    if not recording:
        raise RuntimeError("任务缺少录像文件")

    path = storage.path_of(recording)
    if not path.is_file():
        raise RuntimeError("录像文件已丢失")

    await _update(task.id, progress=15, stage="转写语音")
    delivery = await asyncio.to_thread(analyze, path)

    await _update(task.id, progress=45, stage="分析镜头表现")
    vision = await asyncio.to_thread(analyze_video, path)

    words = delivery.get("words", []) if delivery else []
    turns = _split_turns(questions, words)
    if not turns:
        raise RuntimeError("录像里没有识别到作答内容")

    if delivery:
        delivery.pop("words", None)
    payload_out = {**(delivery or {}), "vision": vision, "engine": "video"}

    await _update(task.id, progress=70, stage="生成训练记录")
    async with session_factory() as session:
        session_id = await create_voice_session(
            session,
            task.user_id,
            payload["sceneId"],
            turns,
            duration_seconds=int(payload.get("durationSeconds") or 0) or None,
            delivery=payload_out,
            engine="video",
            channel="VIDEO",
            recording_path=recording,
        )

    await _update(task.id, progress=85, stage="生成评分报告")
    async with session_factory() as session:
        try:
            await evaluate_session(session, task.user_id, session_id)
        except Exception as exc:  # noqa: BLE001 - 评分失败不影响回放
            logger.warning("task.evaluate_failed error_type=%s", type(exc).__name__)

    await _update(
        task.id,
        status="DONE",
        progress=100,
        stage="完成",
        result={"sessionId": session_id, "vision": vision},
    )


HANDLERS = {"VIDEO_INTERVIEW": process_video_interview}


async def _run_once() -> bool:
    task = await _claim_next()
    if task is None:
        return False
    handler = HANDLERS.get(task.kind)
    try:
        if handler is None:
            raise RuntimeError(f"未知任务类型 {task.kind}")
        await handler(task)
    except Exception as exc:  # noqa: BLE001
        logger.warning("task.failed kind=%s error_type=%s", task.kind, type(exc).__name__)
        await _update(task.id, status="FAILED", stage="失败", error=str(exc)[:300])
    return True


async def _worker() -> None:
    # 进程重启时把「运行中但没跑完」的任务放回队列
    async with session_factory() as session:
        stale = (
            await session.scalars(select(AnalysisTask).where(AnalysisTask.status == "RUNNING"))
        ).all()
        for item in stale:
            item.status = "PENDING"
            item.stage = "重新排队"
        if stale:
            await session.commit()

    while not _stop.is_set():
        try:
            worked = await _run_once()
        except Exception as exc:  # noqa: BLE001
            logger.warning("task.worker_error error_type=%s", type(exc).__name__)
            worked = False
        if not worked:
            try:
                await asyncio.wait_for(_stop.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass


def start_worker() -> None:
    global _running
    if _running is not None and not _running.done():
        return
    _stop.clear()
    _running = asyncio.create_task(_worker())


async def stop_worker() -> None:
    global _running
    _stop.set()
    if _running is not None:
        _running.cancel()
        try:
            await _running
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _running = None


async def get_task(user_id: str, task_id: str) -> AnalysisTask | None:
    async with session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
        if task is None or task.user_id != user_id:
            return None
        return task

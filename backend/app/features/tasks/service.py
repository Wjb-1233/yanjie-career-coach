"""长任务队列：视频分析这类耗时操作改为后台执行，前端轮询进度。

任务状态落在数据库里，进程重启后未完成的任务会重新排队。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core import metrics
from app.core.config import settings
from app.db.base import session_factory
from app.db.models import AnalysisTask

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1.5
# RUNNING 超过这个时间没更新，视为进程崩溃留下的任务
STALE_RUNNING_MINUTES = 15
# 录像真录了、题目与人脸指标也在，只是没转写出作答：降级出报告，不判失败
TRANSCRIPT_EMPTY_REASON = "录像里没有识别到作答内容"
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
    """原子领取一个待办任务。

    多进程部署时，`SKIP LOCKED` 保证同一任务只会被一个 worker 拿到；
    只在事务内锁定，commit 后即释放。
    """
    async with session_factory() as session:
        task = await session.scalar(
            select(AnalysisTask)
            .where(AnalysisTask.status == "PENDING")
            .order_by(AnalysisTask.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
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
    # 转写为空是常见情况（静音、没对着麦克风说）：录像、切题片段与人脸指标仍可用，
    # 这里降级出报告，而不是让整条任务失败、把用户前面录的像一起作废。
    transcript_reason = None if turns else TRANSCRIPT_EMPTY_REASON

    if delivery:
        delivery.pop("words", None)
    from app.features.video.segments import split_segments

    segments = await asyncio.to_thread(
        split_segments,
        path,
        questions,
        settings.recording_dir_path,
        storage.signed_url,
    )

    transcript = [
        {
            "roundNo": index + 1,
            "question": turn["question"],
            "text": turn["answer"],
            "startMs": turn.get("startMs"),
            "endMs": turn.get("endMs"),
            "confidence": turn.get("confidence"),
            "edited": False,
        }
        for index, turn in enumerate(turns)
    ]
    payload_out = {
        **(delivery or {}),
        "vision": vision,
        "engine": "video",
        "marks": questions,
        "transcript": transcript,
        "segments": segments,
    }
    if transcript_reason:
        payload_out["transcriptReason"] = transcript_reason

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
            degraded_reason=transcript_reason,
        )

    await _update(task.id, progress=85, stage="生成评分报告")
    async with session_factory() as session:
        try:
            # 视频会话建好后是 ACTIVE，先按正常流程结束，再走四维评分
            from app.features.training.service import finish_session

            await finish_session(session, task.user_id, session_id)
            await evaluate_session(session, task.user_id, session_id)
        except Exception as exc:  # noqa: BLE001 - 评分失败不影响回放
            logger.warning("task.evaluate_failed error_type=%s", type(exc).__name__)

    result: dict = {"sessionId": session_id, "vision": vision}
    if transcript_reason:
        result["degraded"] = True
        result["transcriptReason"] = transcript_reason
    await _update(
        task.id,
        status="DONE",
        progress=100,
        stage="完成" if not transcript_reason else "完成（未识别到作答，已降级出报告）",
        result=result,
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
        stage = (task.stage or "处理").strip()
        metrics.incr_event("analysis_task", "failed")
        await _update(task.id, status="FAILED", stage=f"{stage}失败", error=str(exc)[:300])
    return True


async def _execute(task_id: str) -> None:
    async with session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
    if task is None:
        return
    handler = HANDLERS.get(task.kind)
    try:
        if handler is None:
            raise RuntimeError(f"未知任务类型 {task.kind}")
        await handler(task)
    except Exception as exc:  # noqa: BLE001
        logger.warning("task.failed kind=%s error_type=%s", task.kind, type(exc).__name__)
        stage = (task.stage or "处理").strip()
        await _update(task.id, status="FAILED", stage=f"{stage}失败", error=str(exc)[:300])


async def queue_eta(task_id: str) -> dict:
    """排队位置与预计等待时间（按已完成任务的平均耗时估算）。"""
    from datetime import datetime as _dt

    from sqlalchemy import func

    async with session_factory() as session:
        task = await session.get(AnalysisTask, task_id)
        if task is None:
            return {}
        ahead = await session.scalar(
            select(func.count())
            .select_from(AnalysisTask)
            .where(AnalysisTask.status == "PENDING", AnalysisTask.created_at < task.created_at)
        )
        rows = (
            await session.scalars(
                select(AnalysisTask).where(AnalysisTask.status == "DONE").limit(20)
            )
        ).all()
        durations = [
            (row.updated_at - row.created_at).total_seconds()
            for row in rows
            if row.updated_at and row.created_at
        ]
        average = sum(durations) / len(durations) if durations else 30.0
    concurrency = max(1, settings.task_worker_concurrency)
    return {
        "ahead": int(ahead or 0),
        "etaSeconds": int(max(0, (ahead or 0) / concurrency * average)),
        "concurrency": concurrency,
    }


async def requeue_stale(minutes: int = STALE_RUNNING_MINUTES) -> int:
    """把「长时间没有心跳」的 RUNNING 任务放回队列。

    只回收超过 minutes 没更新的任务：多实例部署时不能抢别人正在跑的任务。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    async with session_factory() as session:
        stale = (
            await session.scalars(
                select(AnalysisTask).where(
                    AnalysisTask.status == "RUNNING",
                    AnalysisTask.updated_at < cutoff,
                )
            )
        ).all()
        for item in stale:
            item.status = "PENDING"
            item.stage = "重新排队"
        if stale:
            await session.commit()
        return len(stale)


async def _worker() -> None:
    await requeue_stale()

    running: set[asyncio.Task] = set()
    concurrency = max(1, settings.task_worker_concurrency)
    while not _stop.is_set():
        running = {item for item in running if not item.done()}
        worked = False
        while len(running) < concurrency:
            task = await _claim_next()
            if task is None:
                break
            running.add(asyncio.create_task(_execute(task.id)))
            worked = True
        if not worked:
            try:
                await asyncio.wait_for(_stop.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass
        else:
            await asyncio.sleep(0.2)


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

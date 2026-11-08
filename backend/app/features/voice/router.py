"""豆包端到端实时语音（Seeduplex / v3 duplex）代理。

浏览器只连本服务；密钥与鉴权头都在服务端补齐。
协议：全部为 JSON 文本帧，事件类型见官方文档。
"""

import asyncio
import logging
from uuid import uuid4

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser
from app.features.auth.email_verify import require_verified
from app.db.base import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from fastapi import Depends
from app.features.voice.session import create_voice_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["语音对话"])

REALTIME_URL = "wss://openspeech.bytedance.com/api/v3/duplex/realtime/dialogue"
RESOURCE_ID = "volc.speech.dialog"
APP_KEY = "PlgvMymc7f3tQnJ6"

# 同一时刻最多两条语音会话：豆包有会话数限制，本地管线也要占用 CPU
VOICE_SLOTS = asyncio.Semaphore(2)
BUSY_CLOSE_CODE = 4029
BUSY_REASON = "语音服务繁忙，请稍后重试"


def realtime_configured() -> bool:
    return bool(settings.doubao_realtime_app_id and settings.doubao_realtime_access_token)


@router.get("/status")
async def status() -> dict:
    return ok(
        {
            "enabled": realtime_configured(),
            "provider": "doubao-duplex",
            "voice": settings.doubao_realtime_voice,
            "sampleRate": {"input": 16000, "output": 24000},
        }
    )


@router.websocket("/ws")
async def voice_ws(client: WebSocket) -> None:
    await client.accept()
    if not realtime_configured():
        await client.close(code=4001, reason="语音服务未配置")
        return
    if VOICE_SLOTS.locked() and VOICE_SLOTS._value <= 0:  # noqa: SLF001
        await client.close(code=BUSY_CLOSE_CODE, reason=BUSY_REASON)
        return

    try:
        import websockets
        from websockets.exceptions import ConnectionClosed
    except ImportError:  # pragma: no cover
        await client.close(code=4002, reason="服务端缺少 websockets 依赖")
        return

    headers = {
        "X-Api-App-Key": APP_KEY,
        "X-Api-App-ID": settings.doubao_realtime_app_id,
        "X-Api-Access-Key": settings.doubao_realtime_access_token,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Connect-Id": str(uuid4()),
    }

    await VOICE_SLOTS.acquire()
    try:
        async with websockets.connect(REALTIME_URL, additional_headers=headers, max_size=None, open_timeout=20) as upstream:

            async def client_to_upstream() -> None:
                while True:
                    message = await client.receive_text()
                    await upstream.send(message)

            async def upstream_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await client.send_text(message.decode("utf-8", "ignore"))
                    else:
                        await client.send_text(message)

            tasks = [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                task.exception()
    except WebSocketDisconnect:
        return
    except ConnectionClosed as exc:
        logger.info("voice.upstream_closed code=%s", exc.code)
        await client.close(code=4003, reason="语音上游已断开")
    except Exception as exc:  # noqa: BLE001
        status = getattr(getattr(exc, "response", None), "status_code", None)
        logger.warning("voice.upstream_failed error_type=%s status=%s detail=%s", type(exc).__name__, status, str(exc)[:200])
        await client.close(code=4004, reason="语音上游不可用")
    finally:
        VOICE_SLOTS.release()


class VoiceTurn(BaseModel):
    question: str = Field(default="")
    answer: str = Field(default="")


@router.post("/sessions", status_code=201)
async def save_voice_session(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    sceneId: Annotated[str, Form()],
    turns: Annotated[str, Form()] = "[]",
    durationSeconds: Annotated[int | None, Form()] = None,
    engine: Annotated[str, Form()] = "doubao",
    audio: Annotated[UploadFile | None, File()] = None,
    video: Annotated[UploadFile | None, File()] = None,
) -> dict:
    """保存语音会话；若带音频，用本地模型分析语速与停顿。"""
    from app.features.evaluations.delivery import analyze

    try:
        parsed = [VoiceTurn(**item) for item in json.loads(turns)]
    except Exception:
        raise AppError(422, "VOICE_TURNS_INVALID", "对话内容格式不正确")

    from app.features.recordings import storage

    delivery: dict | None = None
    recording_path: str | None = None
    channel = "VOICE"
    if video is not None:
        # 实时视频房间：浏览器同时录音与录像，这里保存整段视频并做人脸技术指标
        suffix = Path(video.filename or "room.webm").suffix or ".webm"
        handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            shutil.copyfileobj(video.file, handle)
            handle.close()
            from app.features.video.metrics import analyze_video

            delivery = await asyncio.to_thread(analyze, handle.name)
            vision = await asyncio.to_thread(analyze_video, handle.name)
            recording_path = storage.save_file(Path(handle.name), suffix)
        finally:
            Path(handle.name).unlink(missing_ok=True)
        channel = "VIDEO"
        if delivery is None:
            delivery = {}
        delivery = {**delivery, "vision": vision, "engine": engine}
    elif audio is not None:
        suffix = Path(audio.filename or "voice.webm").suffix or ".webm"
        handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            shutil.copyfileobj(audio.file, handle)
            handle.close()
            delivery = await asyncio.to_thread(analyze, handle.name)
            recording_path = storage.save_file(Path(handle.name), suffix)
        finally:
            Path(handle.name).unlink(missing_ok=True)

    require_verified(user)
    session_id = await create_voice_session(
        session,
        user.id,
        sceneId,
        [{"question": turn.question, "answer": turn.answer} for turn in parsed],
        duration_seconds=durationSeconds,
        delivery=delivery or None,
        engine=engine if engine in {"doubao", "pipeline"} else "doubao",
        channel=channel,
        recording_path=recording_path,
    )
    return ok({"id": session_id, "delivery": delivery or None, "recordingUrl": storage.url_of(recording_path)})


@router.websocket("/ws/pipeline")
async def voice_pipeline_ws(client: WebSocket, sceneId: str | None = None) -> None:
    """pipecat 引擎：本地 Whisper + DeepSeek + 系统语音。"""
    from pipecat.pipeline.runner import PipelineRunner

    from app.features.voice.pipeline import build_pipeline

    await client.accept()
    if VOICE_SLOTS.locked() and VOICE_SLOTS._value <= 0:  # noqa: SLF001
        await client.close(code=BUSY_CLOSE_CODE, reason=BUSY_REASON)
        return
    instructions = (
        "你是一名中文面试官，正在做模拟面试。候选人说完后，先用一句话回应，再追问一个具体问题，"
        "每次不超过 60 字，不要自问自答，不要长篇独白。"
    )
    opening = "你好，我是今天的面试官，请先做个自我介绍。"
    if sceneId:
        from app.db.base import session_factory
        from app.db.models import Scene

        async with session_factory() as session:
            scene = await session.get(Scene, sceneId)
            if scene is not None:
                instructions = (
                    f"{instructions}\n本场场景：{scene.title}（{scene.category}）。"
                    f"你的角色：{scene.role_name}。背景：{scene.background}。目标：{scene.goal}。"
                )
                opening = scene.opening_line or f"你好，我是{scene.role_name}，我们先简单聊一聊。"

    await VOICE_SLOTS.acquire()
    try:
        task = build_pipeline(client, instructions, opening=opening)
        runner = PipelineRunner(handle_sigint=False, check_dangling_tasks=False)
        await runner.run(task)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice.pipeline_failed error_type=%s", type(exc).__name__)
        try:
            await client.close(code=4005, reason="语音管线启动失败")
        except Exception:
            pass
    finally:
        VOICE_SLOTS.release()

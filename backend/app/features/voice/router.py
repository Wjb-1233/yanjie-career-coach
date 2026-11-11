"""豆包端到端实时语音（Seeduplex / v3 duplex）代理。

浏览器只连本服务；密钥与鉴权头都在服务端补齐。
协议：全部为 JSON 文本帧，事件类型见官方文档。
"""

import asyncio
import logging
from uuid import uuid4

import json
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.core.security import CurrentUser, create_voice_ticket, decode_voice_ticket
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
# 没票或票失效：WS 无法用 Authorization 头，只能靠 ?ticket= 换连
UNAUTHORIZED_CLOSE_CODE = 4003
UNAUTHORIZED_REASON = "语音会话未授权"


PIPELINE_CLOSE_CODE = 4005
# 像密钥的长串（sk-… 或 32 位以上的乱码高熵串）：日志里一律抹掉
_KEY_LIKE = re.compile(r"sk-[A-Za-z0-9_\-]{6,}|[A-Za-z0-9_\-]{32,}")


def redact(message: str) -> str:
    """日志只留错误语义，凭据值不进日志文件。"""
    return _KEY_LIKE.sub("***", message)[:200]


def pipeline_failure_hint(exc: Exception) -> str:
    """把启动异常归到一个可读原因：一眼分清模型没配好还是依赖没装。"""
    detail = f"{type(exc).__name__} {exc}".lower()
    if isinstance(exc, ImportError) or "no module named" in detail or "not installed" in detail:
        return "管线依赖缺失"
    if (
        "api_key" in detail
        or "api key" in detail
        or "not configured" in detail
        or "authentication" in detail
        or "unauthorized" in detail
        or "401" in detail
    ):
        return "模型未配置"
    if "connect" in detail or "timeout" in detail or "timed out" in detail:
        return "模型服务不可达"
    return ""


async def close_pipeline_failed(client: WebSocket, exc: Exception) -> None:
    """管线启动失败统一出口：日志带异常类型与原因，关闭码 reason 也带可读原因。"""
    hint = pipeline_failure_hint(exc)
    logger.warning(
        "voice.pipeline_failed error_type=%s hint=%s error_msg=%s",
        type(exc).__name__,
        hint or "unknown",
        redact(str(exc)),
    )
    reason = "语音管线启动失败" + (f"：{hint}" if hint else "")
    try:
        await client.close(code=PIPELINE_CLOSE_CODE, reason=reason)
    except Exception:  # noqa: BLE001 - 连接可能已断，关闭失败不影响退出
        pass


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


async def authorize(client: WebSocket) -> str | None:
    """校验 query 里的票据；失败直接关闭连接并返回 None。"""
    user_id = decode_voice_ticket(client.query_params.get("ticket"))
    if user_id:
        return user_id
    await client.close(code=UNAUTHORIZED_CLOSE_CODE, reason=UNAUTHORIZED_REASON)
    return None


@router.post("/ws-ticket")
async def issue_ws_ticket(user: CurrentUser) -> dict:
    """登录后取一次性票据，供 /voice/ws 与 /voice/ws/pipeline 换连。"""
    ticket, expires_in = create_voice_ticket(user)
    return ok({"ticket": ticket, "expiresIn": expires_in})


@router.websocket("/ws")
async def voice_ws(client: WebSocket) -> None:
    await client.accept()
    if await authorize(client) is None:
        return
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


def _turn_marks(turns: list["VoiceTurn"]) -> list[dict]:
    """把带时间窗的轮次转成切段标记；缺时间的轮次跳过。"""
    return [
        {
            "text": turn.question or turn.answer[:40],
            "start": (turn.startMs or 0) / 1000,
            "end": (turn.endMs or 0) / 1000,
        }
        for turn in turns
        if turn.startMs is not None and turn.endMs is not None and turn.endMs > turn.startMs
    ]


class VoiceTurn(BaseModel):
    question: str = Field(default="")
    answer: str = Field(default="")
    # 实时房间会带上每轮的时间窗，用于把整段录像切成按题片段
    startMs: int | None = Field(default=None, ge=0)
    endMs: int | None = Field(default=None, ge=0)


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
        marks = _turn_marks(parsed)
        segments: list[dict] = []
        if marks and recording_path:
            from app.features.video.segments import split_segments

            segments = await asyncio.to_thread(
                split_segments,
                storage.path_of(recording_path),
                marks,
                settings.recording_dir_path,
                storage.signed_url,
            )
        delivery = {**delivery, "vision": vision, "engine": engine, "marks": marks, "segments": segments}
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
async def voice_pipeline_ws(client: WebSocket, sceneId: str | None = None, depth: str = "STANDARD", lang: str = "zh") -> None:
    """pipecat 引擎：本地 Whisper + DeepSeek + 系统语音。"""
    await client.accept()
    user_id = await authorize(client)
    if user_id is None:
        return

    try:
        from pipecat.pipeline.runner import PipelineRunner

        from app.features.voice.pipeline import build_pipeline
    except ImportError as exc:
        # 依赖没装齐也要给出可读原因，而不是断成一条没有理由的连接
        await close_pipeline_failed(client, exc)
        return

    if VOICE_SLOTS.locked() and VOICE_SLOTS._value <= 0:  # noqa: SLF001
        await client.close(code=BUSY_CLOSE_CODE, reason=BUSY_REASON)
        return
    instructions = (
        "你是一名中文面试官，正在做模拟面试。候选人说完后，先用一句话回应，再追问一个具体问题，"
        "每次不超过 60 字，不要自问自答，不要长篇独白。"
    )
    if lang == "en":
        instructions = (
            "You are an English-speaking interviewer. Ask one question at a time in English, "
            "briefly acknowledge the answer, then ask one specific follow-up. Keep every reply under 40 words. "
            "Do not answer for the candidate."
        )
    if depth == "THREE_LAYER":
        instructions += " 本场启用三层追问：先确认基础知识与事实，再让候选人比较方案优劣，最后给出复杂或异常场景；每轮只推进一层。"
    elif depth == "PRESSURE":
        instructions += " 本场是压力面：节奏快、连续追问证据和数字，不接客套，但保持专业尊重。"
    opening = "Hello, I'm your interviewer today. Please start with a brief self-introduction." if lang == "en" else "你好，我是今天的面试官，请先做个自我介绍。"
    if sceneId:
        from app.db.base import session_factory
        from app.features.scenes.service import get_scene

        async with session_factory() as session:
            try:
                scene = await get_scene(session, sceneId, user_id)
            except AppError:
                scene = None
            if scene is not None:
                instructions = (
                    f"{instructions}\n本场场景：{scene.title}（{scene.category}）。"
                    f"你的角色：{scene.role_name}。背景：{scene.background}。目标：{scene.goal}。"
                )
                opening = scene.opening_line or f"你好，我是{scene.role_name}，我们先简单聊一聊。"
                if lang == "en":
                    opening = "Hello, I'm your interviewer today. Please start with a brief self-introduction."

    await VOICE_SLOTS.acquire()
    try:
        task = build_pipeline(client, instructions, opening=opening, lang=lang)
        runner = PipelineRunner(handle_sigint=False, check_dangling_tasks=False)
        await runner.run(task)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await close_pipeline_failed(client, exc)
    finally:
        VOICE_SLOTS.release()

"""基于 pipecat 的语音对练管线（本地 STT + DeepSeek + 系统 TTS）。

作为豆包端到端语音的**备用引擎**：火山服务不可用或需要完全本地化时使用。
浏览器协议保持与原有通话页一致（二进制 PCM 16k 输入，二进制 PCM 24k 输出）。
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import WebSocket

from app.core.config import settings

SAMPLE_RATE_IN = 16000
SAMPLE_RATE_OUT = 24000
FFMPEG = Path("D:/graduation_design/tools/ffmpeg/node_modules/ffmpeg-static/ffmpeg.exe")


def ffmpeg_binary() -> str:
    if FFMPEG.exists():
        return str(FFMPEG)
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("找不到 ffmpeg")
    return found


def _synth_wav(text: str, out_wav: Path) -> None:
    work = Path(tempfile.mkdtemp())
    txt = work / "t.txt"
    ps = work / "t.ps1"
    txt.write_text(" ".join(text.split())[:200], encoding="utf-8")
    ps.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$s.SelectVoice('Microsoft Huihui Desktop')\n"
        f"$s.SetOutputToWaveFile('{out_wav.as_posix()}')\n"
        f"$text = Get-Content -Raw -Encoding UTF8 '{txt.as_posix()}'\n"
        "$s.Speak($text)\n$s.Dispose()\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)],
        check=True,
        capture_output=True,
    )
    shutil.rmtree(work, ignore_errors=True)


def _make_serializer():
    """自定义序列化：二进制帧 = 裸 PCM，文本帧 = JSON（用于字幕）。"""
    from pipecat.frames.frames import (
        Frame,
        InputAudioRawFrame,
        InterruptionFrame,
        OutputAudioRawFrame,
        TextFrame,
        TranscriptionFrame,
    )
    from pipecat.serializers.base_serializer import FrameSerializer

    class PcmJsonSerializer(FrameSerializer):
        async def serialize(self, frame: Frame) -> str | bytes | None:
            if isinstance(frame, OutputAudioRawFrame):
                return frame.audio
            if isinstance(frame, (TextFrame, TranscriptionFrame)):
                import json

                return json.dumps({"type": "text", "text": frame.text}, ensure_ascii=False)
            return None

        async def deserialize(self, data: str | bytes) -> Frame | None:
            if isinstance(data, (bytes, bytearray)):
                if len(data) == 0:  # 空帧 = 客户端打断
                    return InterruptionFrame()
                return InputAudioRawFrame(bytes(data), SAMPLE_RATE_IN, 1)
            return None

    return PcmJsonSerializer()


def _make_transcript_tap(websocket: WebSocket, role: str):
    """把 LLM / STT 的文本直接推给浏览器做字幕（TTS 会吞掉 TextFrame）。"""
    import json

    from pipecat.frames.frames import (
        Frame,
        LLMFullResponseEndFrame,
        TTSSpeakFrame,
        TextFrame,
        TranscriptionFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    class TranscriptTap(FrameProcessor):
        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            payload = None
            if role == "assistant":
                if isinstance(frame, TTSSpeakFrame):
                    # 开场白直接走 TTS，不会变成 TextFrame，这里补上字幕
                    payload = {"type": "assistant_delta", "text": frame.text}
                elif isinstance(frame, TextFrame):
                    payload = {"type": "assistant_delta", "text": frame.text}
                elif isinstance(frame, LLMFullResponseEndFrame):
                    payload = {"type": "assistant_end"}
            elif isinstance(frame, TranscriptionFrame):
                payload = {"type": "user", "text": frame.text}
            if payload:
                try:
                    await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                except Exception:
                    pass
            await self.push_frame(frame, direction)

    return TranscriptTap()


def build_pipeline(websocket: WebSocket, instructions: str, opening: str = ""):
    """构造 pipecat 管线；导入放在函数内，避免未安装时影响其他功能。"""
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.processors.audio.vad_processor import VADProcessor
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.tts_service import TTSService
    from pipecat.services.whisper.stt import WhisperSTTService
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )

    class SystemTTSService(TTSService):
        """用 Windows 中文语音合成，输出 24k 单声道 PCM。"""

        def __init__(self) -> None:
            super().__init__(sample_rate=SAMPLE_RATE_OUT, push_stop_frames=True, push_start_frame=True)

        async def run_tts(self, text: str, context_id: str):
            yield TTSStartedFrame()
            wav = Path(tempfile.mkdtemp()) / "out.wav"
            try:
                await asyncio.to_thread(_synth_wav, text, wav)
                raw = await asyncio.to_thread(
                    subprocess.run,
                    [
                        ffmpeg_binary(), "-y", "-i", str(wav),
                        "-f", "s16le", "-acodec", "pcm_s16le",
                        "-ac", "1", "-ar", str(SAMPLE_RATE_OUT), "-",
                    ],
                    capture_output=True,
                    check=True,
                )
                pcm = raw.stdout
                step = int(SAMPLE_RATE_OUT * 2 * 0.02)  # 20ms
                for offset in range(0, len(pcm), step):
                    chunk = pcm[offset:offset + step]
                    if chunk:
                        yield TTSAudioRawFrame(chunk, SAMPLE_RATE_OUT, 1)
            finally:
                shutil.rmtree(wav.parent, ignore_errors=True)
            yield TTSStoppedFrame()

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=SAMPLE_RATE_IN,
            audio_out_sample_rate=SAMPLE_RATE_OUT,
            serializer=_make_serializer(),
        ),
    )

    stt = WhisperSTTService(model="small", device="cpu", compute_type="int8", language="zh")
    llm = OpenAILLMService(
        api_key=settings.llm_api_key,
        base_url=f"{settings.llm_base_url.rstrip('/')}/v1",
        model=settings.llm_model,
    )
    tts = SystemTTSService()

    context = LLMContext([{"role": "system", "content": instructions}])
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            VADProcessor(vad_analyzer=SileroVADAnalyzer()),
            stt,
            _make_transcript_tap(websocket, "user"),
            context_aggregator.user(),
            llm,
            _make_transcript_tap(websocket, "assistant"),
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True, enable_metrics=False))

    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client) -> None:
        # 开场白直接走 TTS，不依赖 LLM：模型慢或超时也能保证面试官先开口
        from pipecat.frames.frames import TTSSpeakFrame

        text = opening or "你好，我是今天的面试官，请先做个自我介绍。"
        context.add_message({"role": "assistant", "content": text})
        await task.queue_frames([TTSSpeakFrame(text)])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(_transport, _client) -> None:
        await task.cancel()

    return task

"""微课旁白合成。

优先级：豆包 seed-tts-2.0（支持情绪，国内网络稳定）→ edge-tts 神经声线 → 系统语音。
后者用 SSML 调语速与停顿，避免念稿感。任何一层失败都不影响整门课。
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# 讲课时用的声线：晓晓偏自然口语，云希偏沉稳男声
VOICE_MAP = {
    "tutor": ("zh-CN-XiaoxiaoNeural", "+6%", "+2Hz"),
    "coach": ("zh-CN-YunxiNeural", "+4%", "+0Hz"),
    "female": ("zh-CN-XiaoyiNeural", "+4%", "+2Hz"),
}

ATTEMPTS = 4

# 豆包音色：kangkang 之外都是角色音色，适合讲课的是「天才同桌 / 爽朗少年」
DOUBAO_SPEAKERS = {
    "tutor": "saturn_zh_male_tiancaitongzhuo_tob",
    "coach": "saturn_zh_male_tiancaitongzhuo_tob",
    "female": "saturn_zh_female_bingjiaojiejie_tob",
}

DOUBAO_EMOTION = {
    "tutor": "gentle",
    "coach": "serious",
    "female": "gentle",
}

DOUBAO_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"


def _split_sentences(text: str, limit: int = 90) -> list[str]:
    """按标点切句，过短的片段并入上一句，让合成有自然停顿。"""
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return []

    raw: list[str] = []
    buffer = ""
    for char in cleaned:
        buffer += char
        if char in "。！？；!?;":
            raw.append(buffer)
            buffer = ""
    if buffer.strip():
        raw.append(buffer)

    merged: list[str] = []
    for piece in (item.strip() for item in raw):
        if not piece:
            continue
        if merged and len(piece) < 6:
            merged[-1] += piece
        else:
            merged.append(piece)

    chunks: list[str] = []
    for piece in merged:
        while len(piece) > limit:
            chunks.append(piece[:limit])
            piece = piece[limit:]
        if piece:
            chunks.append(piece)
    return chunks


def _doubao_tts(text: str, out_wav: Path, style: str) -> None:
    """豆包大模型语音合成：一次请求返回若干段 mp3，拼接后转 wav。"""
    import base64
    import json
    import uuid

    import httpx

    from app.core.config import settings

    app_id = settings.doubao_tts_app_id or settings.doubao_realtime_app_id
    token = settings.doubao_tts_access_token or settings.doubao_realtime_access_token
    if not app_id or not token:
        raise RuntimeError("doubao tts not configured")

    speaker = settings.doubao_tts_speaker or DOUBAO_SPEAKERS.get(style, DOUBAO_SPEAKERS["tutor"])
    emotion = settings.doubao_tts_emotion or DOUBAO_EMOTION.get(style, "gentle")

    payload = {
        "user": {"uid": "yanjie"},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "emotion": emotion,
            "audio_params": {"format": "mp3", "sample_rate": 24000, "speech_rate": 0},
        },
    }
    headers = {
        "X-Api-App-Id": app_id,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": "seed-tts-2.0",
        "X-Api-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }

    mp3 = out_wav.with_suffix(".mp3")
    audio = bytearray()
    last_error: str | None = None
    with httpx.Client(timeout=60, trust_env=False) as client:
        response = client.post(DOUBAO_URL, json=payload, headers=headers)
        for line in response.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("data"):
                audio.extend(base64.b64decode(chunk["data"]))
            code = chunk.get("code")
            if code not in (None, 0):
                last_error = str(chunk.get("message") or code)

    if len(audio) < 2048:
        raise RuntimeError(f"doubao tts empty: {last_error or response.status_code}")

    mp3.write_bytes(bytes(audio))
    # 直接交付 mp3：浏览器与 Remotion 都能播，省掉 ffmpeg 依赖
    mp3.replace(out_wav.with_suffix(".mp3"))


def _edge_tts(text: str, out_wav: Path, style: str) -> None:
    """用 edge-tts 命令行合成，避免在长驻进程里嵌套事件循环。"""
    import sys

    voice, rate, pitch = VOICE_MAP.get(style, VOICE_MAP["tutor"])
    mp3 = out_wav.with_suffix(".mp3")

    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "edge_tts",
                    "--voice",
                    voice,
                    f"--rate={rate}",
                    f"--pitch={pitch}",
                    "--text",
                    text,
                    "--write-media",
                    str(mp3),
                ],
                capture_output=True,
                timeout=90,
            )
            if result.returncode != 0 or not mp3.is_file() or mp3.stat().st_size < 2048:
                raise RuntimeError(f"edge-tts exit={result.returncode}")
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            mp3.unlink(missing_ok=True)
            logger.warning("narration.edge_retry attempt=%s error_type=%s", attempt + 1, type(exc).__name__)
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"edge-tts failed: {type(last).__name__}")


def _system_tts(text: str, out_wav: Path, style: str = "tutor") -> None:
    """系统语音兜底：用 SSML 调语速、停顿和重音，避免念稿式的平铺直叙。"""
    sentences = _split_sentences(text) or [text]
    voice = "Microsoft Huihui Desktop"
    body: list[str] = []
    for index, sentence in enumerate(sentences):
        # 短句放慢、长句略快；相邻句子在音高上做一点起伏
        rate = "+8%" if len(sentence) <= 12 else "+2%" if len(sentence) <= 26 else "-2%"
        pitch = "+4%" if index % 2 == 0 else "+1%"
        emphasis = ' level="moderate"' if len(sentence) <= 18 else ""
        body.append(
            f'<prosody rate="{rate}" pitch="{pitch}">'
            f"<emphasis{emphasis}>{_escape(sentence)}</emphasis>"
            "</prosody><break time=\"220ms\"/>"
        )
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">'
        f'<voice name="{voice}">' + "".join(body) + "</voice></speak>"
    )

    workdir = Path(tempfile.mkdtemp())
    ssml_file = workdir / "ssml.xml"
    ssml_file.write_text(ssml, encoding="utf-8")
    script = workdir / "tts.ps1"
    script.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        f"$s.SetOutputToWaveFile('{out_wav.as_posix()}')\n"
        f"$xml = Get-Content -Raw -Encoding UTF8 '{ssml_file.as_posix()}'\n"
        "$s.SpeakSsml($xml)\n"
        "$s.Dispose()\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        check=True,
        capture_output=True,
    )


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def audio_duration(path: Path) -> float:
    """读取音频时长（mp3 或 wav）。"""
    from mutagen import File as MutagenFile

    audio = MutagenFile(str(path))
    if audio is None or audio.info is None:
        raise RuntimeError(f"cannot read duration: {path.name}")
    return float(audio.info.length)


def synthesize_slide(text: str, workdir: Path, index: int, style: str = "tutor") -> tuple[Path, float, str]:
    """合成一幕旁白，返回（音频文件, 秒数, 引擎）。"""
    sentences = _split_sentences(text) or [text]
    pieces: list[Path] = []
    engine = "doubao"

    for position, sentence in enumerate(sentences):
        base = workdir / f"slide-{index}-part{position}"
        piece: Path | None = None
        for provider, label in (("doubao", "doubao"), ("edge", "edge"), ("system", "system")):
            try:
                if provider == "doubao":
                    target = base.with_suffix(".mp3")
                    _doubao_tts(sentence, target, style)
                elif provider == "edge":
                    target = base.with_suffix(".mp3")
                    _edge_tts(sentence, target, style)
                else:
                    target = base.with_suffix(".wav")
                    _system_tts(sentence, target, style)
                if target.is_file() and target.stat().st_size > 512:
                    piece = target
                    engine = label if not pieces else engine
                    break
            except Exception as exc:  # noqa: BLE001
                logger.warning("narration.%s_failed error_type=%s", provider, type(exc).__name__)
        if piece:
            pieces.append(piece)

    if not pieces:
        raise RuntimeError("no narration audio produced")

    merged = workdir / f"slide-{index}{pieces[0].suffix}"
    merged.write_bytes(b"".join(piece.read_bytes() for piece in pieces))
    for piece in pieces:
        piece.unlink(missing_ok=True)
    return merged, audio_duration(merged), engine

"""微课旁白：优先用在线神经语音（更像人），失败再退回系统语音。

顺序：edge-tts（中文神经声线，带停顿与语气起伏）→ Windows 系统语音。
在线合成偶发连不上，所以每次都做有限次重试；失败不影响整门课。
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


def _edge_tts(text: str, out_wav: Path, style: str) -> None:
    import edge_tts

    voice, rate, pitch = VOICE_MAP.get(style, VOICE_MAP["tutor"])
    mp3 = out_wav.with_suffix(".mp3")

    async def run() -> None:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        with mp3.open("wb") as handle:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    handle.write(chunk["data"])

    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(run())
            finally:
                loop.close()
            if mp3.is_file() and mp3.stat().st_size > 1024:
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(out_wav)],
                    check=True,
                    capture_output=True,
                )
                mp3.unlink(missing_ok=True)
                return
            raise RuntimeError("empty audio")
        except Exception as exc:  # noqa: BLE001
            last = exc
            mp3.unlink(missing_ok=True)
            logger.warning("narration.edge_retry attempt=%s error_type=%s", attempt + 1, type(exc).__name__)
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"edge-tts failed: {type(last).__name__}")


def _system_tts(text: str, out_wav: Path) -> None:
    workdir = Path(tempfile.mkdtemp())
    text_file = workdir / "text.txt"
    text_file.write_text(text, encoding="utf-8")
    script = workdir / "tts.ps1"
    script.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$s.SelectVoice('Microsoft Huihui Desktop')\n"
        "$s.Rate = 2\n"
        f"$s.SetOutputToWaveFile('{out_wav.as_posix()}')\n"
        f"$text = Get-Content -Raw -Encoding UTF8 '{text_file.as_posix()}'\n"
        "$s.Speak($text)\n"
        "$s.Dispose()\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        check=True,
        capture_output=True,
    )


def synthesize(text: str, out_wav: Path, style: str = "tutor") -> tuple[Path, str]:
    """合成一段旁白，返回（文件, 实际使用的引擎）。"""
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    sentences = _split_sentences(text)
    if not sentences:
        raise ValueError("empty narration text")

    pieces: list[Path] = []
    engine = "edge"
    for index, sentence in enumerate(sentences):
        piece = out_wav.with_name(f"{out_wav.stem}-part{index}.wav")
        try:
            _edge_tts(sentence, piece, style)
        except Exception:  # noqa: BLE001
            engine = "system"
            _system_tts(sentence, piece)
        pieces.append(piece)

    _concat(pieces, out_wav)
    for piece in pieces:
        piece.unlink(missing_ok=True)
    return out_wav, engine


def _concat(pieces: list[Path], out_wav: Path) -> None:
    if len(pieces) == 1:
        pieces[0].replace(out_wav)
        return
    listing = out_wav.with_suffix(".txt")
    listing.write_text(
        "\n".join(f"file '{piece.resolve().as_posix()}'" for piece in pieces), encoding="utf-8"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), str(out_wav)],
        check=True,
        capture_output=True,
    )
    listing.unlink(missing_ok=True)

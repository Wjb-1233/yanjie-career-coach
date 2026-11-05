"""表达节奏分析：用 faster-whisper 拿到词级时间戳，算出语速与停顿。

只用本地模型，不产生额外 API 费用；GPU 可用时用 int8_float16，否则回退 CPU。
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

FILLERS = ["然后", "就是", "那个", "其实", "反正", "所以说", "嗯", "额", "这个", "的话"]
PAUSE_THRESHOLD = 0.6  # 秒，超过即视为停顿
MODEL_DIR = Path(__file__).resolve().parents[3] / ".models"

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def warmup() -> bool:
    """预热语音模型；失败不影响主流程。"""
    try:
        _model()
        return True
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=1)
def _model():
    """默认 CPU int8（稳定、无需 CUDA 运行时）；设置 WHISPER_DEVICE=cuda 可切 GPU。"""
    from faster_whisper import WhisperModel

    size = os.environ.get("WHISPER_MODEL", "small")
    device = os.environ.get("WHISPER_DEVICE", "cpu").lower()
    settings = {"download_root": str(MODEL_DIR), "local_files_only": False}
    if device == "cuda":
        try:
            return WhisperModel(size, device="cuda", compute_type="int8_float16", **settings)
        except Exception as exc:  # pragma: no cover
            logger.warning("delivery.cuda_unavailable error_type=%s", type(exc).__name__)
    return WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=4, **settings)


def analyze(audio_path: str | Path) -> dict:
    """返回语速、停顿、填充词等指标；失败时返回空字典而不是抛错。"""
    try:
        segments, info = _model().transcribe(
            str(audio_path),
            language="zh",
            word_timestamps=True,
            vad_filter=True,
            beam_size=1,
        )
        words: list[tuple[str, float, float, float]] = []
        for segment in segments:
            for word in segment.words or []:
                text = (word.word or "").strip()
                if text:
                    words.append((text, float(word.start), float(word.end), float(getattr(word, "probability", 0.0) or 0.0)))
    except Exception as exc:  # pragma: no cover - 模型或音频问题
        logger.warning("delivery.analyze_failed error_type=%s", type(exc).__name__)
        return {}

    if not words:
        return {}

    text = "".join(word[0] for word in words)
    hanzi = len(re.findall(r"[\u4e00-\u9fff]", text))
    start, end = words[0][1], words[-1][2]
    duration = max(0.001, end - start)

    pauses: list[dict] = []
    for index in range(1, len(words)):
        gap = words[index][1] - words[index - 1][2]
        if gap >= PAUSE_THRESHOLD:
            pauses.append({"start": round(words[index - 1][2], 2), "end": round(words[index][1], 2), "seconds": round(gap, 2)})

    pause_total = sum(item["seconds"] for item in pauses)
    speaking = max(0.001, duration - pause_total)
    filler_hits = {word: text.count(word) for word in FILLERS if text.count(word)}

    return {
        "durationSeconds": round(duration, 1),
        "charCount": hanzi,
        "speechRate": round(hanzi / duration * 60, 1),          # 字/分钟（含停顿）
        "articulationRate": round(hanzi / speaking * 60, 1),     # 字/分钟（不含停顿）
        "pauseCount": len(pauses),
        "pauseTotalSeconds": round(pause_total, 1),
        "longestPause": max((item["seconds"] for item in pauses), default=0.0),
        "pauses": pauses[:10],
        "fillerTotal": sum(filler_hits.values()),
        "topFillers": sorted(
            ({"word": word, "count": count} for word, count in filler_hits.items()),
            key=lambda item: item["count"],
            reverse=True,
        )[:3],
        "text": text[:600],
        "words": [
            {"start": round(item[1], 2), "end": round(item[2], 2), "text": item[0], "p": round(item[3], 2)}
            for item in words
        ][:400],
    }

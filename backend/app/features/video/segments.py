"""V-03：把整段录像按题目时间窗切成独立的答题片段。

用 imageio-ffmpeg 自带的 ffmpeg 二进制，避免依赖系统 PATH。
切分失败只记日志，不影响主流程（报告仍可用整段录像回放）。
"""

from __future__ import annotations

import logging
import subprocess
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_SEGMENT_SECONDS = 1.0


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def split_segments(
    source: Path,
    marks: list[dict],
    dest_dir: Path,
    url_for,
) -> list[dict]:
    """按 marks 的 start/end 切段，返回 [{roundNo,startMs,endMs,file,url}]。"""
    if not source.is_file() or not marks:
        return []
    try:
        binary = _ffmpeg()
    except Exception as exc:  # noqa: BLE001
        logger.warning("segments.ffmpeg_missing error_type=%s", type(exc).__name__)
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    segments: list[dict] = []
    for index, mark in enumerate(marks):
        start = float(mark.get("start") or 0)
        end = float(mark.get("end") or 0)
        if end - start < MIN_SEGMENT_SECONDS:
            continue
        name = f"seg-{uuid.uuid4().hex[:12]}.mp4"
        target = dest_dir / name
        command = [
            binary,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.2f}",
            "-to",
            f"{end:.2f}",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(target),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, timeout=180)
        except Exception as exc:  # noqa: BLE001
            logger.warning("segments.split_failed error_type=%s", type(exc).__name__)
            continue
        if completed.returncode != 0 or not target.is_file() or target.stat().st_size < 1024:
            logger.warning("segments.split_nonzero code=%s", completed.returncode)
            target.unlink(missing_ok=True)
            continue
        segments.append(
            {
                "roundNo": index + 1,
                "question": str(mark.get("text") or ""),
                "startMs": int(start * 1000),
                "endMs": int(end * 1000),
                "file": name,
                "url": url_for(name),
            }
        )
    return segments

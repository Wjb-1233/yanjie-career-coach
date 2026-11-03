"""用 Remotion 渲染动态微课视频：幻灯片动画 + 中文旁白。

流程：
1. 每个分镜合成一段旁白（系统语音），量出时长
2. 把旁白拼成一条音轨（带小停顿）
3. 调用 remotion CLI 渲染 mp4，时长与音轨对齐
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import wave
from pathlib import Path

from app.infrastructure.narration import synthesize
from app.features.lessons.video import WIDTH, _speak

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[4]
VIDEO_DIR = ROOT / "video"
PUBLIC_DIR = VIDEO_DIR / "public"
GAP_SECONDS = 0.45


def _wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def _concat_wavs(parts: list[Path], gap: float, out_path: Path) -> float:
    """把多段 wav 用静音分隔拼成一条，返回总时长。"""
    params = None
    frames: list[bytes] = []
    gap_frames = 0
    for index, part in enumerate(parts):
        with wave.open(str(part), "rb") as handle:
            if params is None:
                params = handle.getparams()
                gap_frames = int(params.framerate * gap)
            frames.append(handle.readframes(handle.getnframes()))
        if index != len(parts) - 1:
            frames.append(b"\x00" * (gap_frames * params.sampwidth * params.nchannels))
    assert params is not None
    with wave.open(str(out_path), "wb") as out:
        out.setparams(params)
        for chunk in frames:
            out.writeframes(chunk)
    return _wav_seconds(out_path)


def step_text(step: dict) -> str:
    """课程步骤的讲解文字：历史数据里字段名叫 detail，新数据叫 explanation。"""
    return (step.get("explanation") or step.get("detail") or "").strip()


def render_lesson(lesson: dict, out_path: Path, key: str, dimension: str = "") -> Path:
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / f".remotion-{key}"
    work.mkdir(parents=True, exist_ok=True)

    slides: list[tuple[str, str]] = [
        (lesson.get("title", "微课"), lesson.get("intro", "")),
    ]
    for index, step in enumerate(lesson.get("steps", []), start=1):
        slides.append((step.get("title", ""), step_text(step)[:110]))

    wavs: list[Path] = []
    for index, (title, text) in enumerate(slides):
        wav = work / f"voice-{index}.wav"
        narration_text = f"{title}。{text}"[:170]
        try:
            synthesize(narration_text, wav, style="tutor")
        except Exception:  # noqa: BLE001
            _speak(narration_text, wav)
        wavs.append(wav)

    narration = work / "narration.wav"
    total = _concat_wavs(wavs, GAP_SECONDS, narration)

    durations = [round(_wav_seconds(wav) + GAP_SECONDS, 2) for wav in wavs]
    got = sum(durations)
    if got < total:
        durations[-1] = round(durations[-1] + (total - got), 2)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    audio_name = f"narration-{key}.wav"
    shutil.copyfile(narration, PUBLIC_DIR / audio_name)

    props = {
        "title": lesson.get("title", "微课"),
        "dimension": dimension or lesson.get("dimension") or "",
        "intro": lesson.get("intro", ""),
        "steps": [
            {
                "title": step.get("title", ""),
                "detail": step_text(step),
                "example": step.get("example", ""),
            }
            for step in lesson.get("steps", [])
        ],
        "slideDurations": durations,
        "audioSrc": audio_name,
    }
    props_file = work / "props.json"
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    npx = shutil.which("npx") or "npx"
    command = [
        npx,
        "remotion",
        "render",
        "src/index.tsx",
        "LessonVideo",
        str(out_path),
        f"--props={props_file}",
        "--log=error",
    ]
    logger.info("remotion.render_start key=%s slides=%s", key, len(durations))
    result = subprocess.run(
        command,
        cwd=str(VIDEO_DIR),
        capture_output=True,
        text=True,
        timeout=900,
        shell=False,
    )
    if result.returncode != 0:
        logger.warning("remotion.render_failed stderr=%s", (result.stderr or "")[-400:])
        raise RuntimeError("Remotion 渲染失败")

    chapters = []
    cursor = 0.0
    for index, duration in enumerate(durations):
        title = lesson.get("title", "微课") if index == 0 else lesson.get("steps", [{}])[index - 1].get("title", "")
        chapters.append({"title": title, "start": round(cursor, 2), "duration": duration})
        cursor += duration
    (out_path.with_suffix(".json")).write_text(
        json.dumps({"chapters": chapters, "duration": round(cursor, 2)}, ensure_ascii=False),
        encoding="utf-8",
    )

    shutil.rmtree(work, ignore_errors=True)
    return out_path

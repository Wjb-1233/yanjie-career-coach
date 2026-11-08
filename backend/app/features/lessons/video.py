"""把一门微课渲染成带中文配音的 mp4（幻灯片 + TTS + ffmpeg 合成）。

用法：
    PYTHONPATH=. .venv/Scripts/python.exe -m app.features.lessons.video --lesson <lesson_key>
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1600, 900
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]
FONT_BOLD = next((path for path in FONT_CANDIDATES if Path(path).exists()), None)

BG_TOP = (250, 248, 243)
BG_BOTTOM = (240, 236, 227)
INK = (28, 27, 24)
INK_SOFT = (92, 87, 79)
ACCENT = (178, 92, 44)
LINE = (214, 208, 197)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_CANDIDATES[0]
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def _background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * ratio) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color)
    return image


def _slide(kind: str, title: str, subtitle: str, body: list[str], footer: str) -> Image.Image:
    image = _background()
    draw = ImageDraw.Draw(image)

    draw.text((96, 74), "言阶 · 微课", font=_font(26), fill=INK_SOFT)
    draw.line([(96, 132), (WIDTH - 96, 132)], fill=LINE, width=2)

    if kind == "cover":
        y = 236
        for part in _wrap(draw, title, _font(70, True), WIDTH - 200)[:2]:
            draw.text((96, y), part, font=_font(70, True), fill=INK)
            y += 96
        y += 26
        for line in body:
            for part in _wrap(draw, line, _font(32), WIDTH - 200):
                draw.text((96, y), part, font=_font(32), fill=INK_SOFT)
                y += 50
        draw.text((96, HEIGHT - 120), footer, font=_font(26), fill=INK_SOFT)
        return image

    # 步骤序号：右上角浅色大号
    draw.text((WIDTH - 96, 170), title, font=_font(128, True), fill=(231, 225, 214), anchor="ra")
    draw.text((96, 246), subtitle, font=_font(50, True), fill=INK)

    y = 360
    for line in body:
        if line.startswith("「"):
            wrapped = _wrap(draw, line, _font(30), WIDTH - 260)
            if len(wrapped) > 3:
                wrapped = wrapped[:3]
                wrapped[-1] = wrapped[-1][:-1] + "…"
            box_height = len(wrapped) * 44 + 36
            draw.rounded_rectangle([(96, y - 10), (WIDTH - 96, y + box_height)], radius=16, fill=(238, 233, 224))
            for index, part in enumerate(wrapped):
                draw.text((124, y + 6 + index * 44), part, font=_font(30), fill=INK_SOFT)
            y += box_height + 30
            continue
        for part in _wrap(draw, line, _font(32), WIDTH - 200):
            draw.text((96, y), part, font=_font(32), fill=INK_SOFT if part.startswith("要点") else INK)
            y += 50
        y += 22

    draw.text((96, HEIGHT - 96), footer, font=_font(24), fill=INK_SOFT)
    return image


def _speak(text: str, out_wav: Path) -> None:
    """用系统中文语音合成，离线可用。

    文本单独写成 UTF-8 文件，由 PowerShell 读入，避免中文进入脚本引号导致解析失败。
    """
    workdir = Path(tempfile.mkdtemp())
    text_file = workdir / "text.txt"
    text_file.write_text(" ".join(text.split()), encoding="utf-8")
    script = workdir / "tts.ps1"
    script.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$s.SelectVoice('Microsoft Huihui Desktop')\n"
        "$s.Rate = 0\n"
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


def _ffmpeg() -> str:
    candidate = Path("D:/graduation_design/tools/ffmpeg/node_modules/ffmpeg-static/ffmpeg.exe")
    if candidate.exists():
        return str(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("找不到 ffmpeg")


def _media_duration(path: Path) -> float:
    """读取媒体时长（秒）：优先 ffprobe，没有就用 ffmpeg -i 解析，失败返回 0。"""
    import re

    try:
        ffmpeg = _ffmpeg()
        probe = Path(ffmpeg).with_name("ffprobe.exe" if ffmpeg.endswith(".exe") else "ffprobe")
        if probe.exists() or shutil.which("ffprobe"):
            binary = str(probe) if probe.exists() else "ffprobe"
            result = subprocess.run(
                [binary, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip() or 0)
        result = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True)
        match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def build_video(lesson: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp())
    ffmpeg = _ffmpeg()
    segments: list[Path] = []

    scenes: list[dict] = [
        {
            "kind": "cover",
            "title": lesson.get("title", "微课"),
            "subtitle": "",
            "body": [lesson.get("intro", "")[:120]],
            "say": f"{lesson.get('title', '')}。{lesson.get('intro', '')}",
        }
    ]
    for index, step in enumerate(lesson.get("steps", []), start=1):
        lines = [step.get("explanation") or step.get("detail") or ""]
        if step.get("example"):
            lines.append(f"「{step['example']}」")
        if step.get("practice"):
            lines.append(f"要点：{step['practice']}")
        scenes.append(
            {
                "kind": "step",
                "title": f"0{index}",
                "subtitle": step.get("title", ""),
                "body": lines,
                "say": f"第{index}步，{step.get('title', '')}。{step.get('explanation') or step.get('detail') or ''}",
            }
        )

    for index, scene in enumerate(scenes):
        image = _slide(scene["kind"], scene["title"], scene["subtitle"], scene["body"], "言阶 · 面试沟通训练")
        png = workdir / f"slide-{index}.png"
        image.save(png, "PNG")
        wav = workdir / f"voice-{index}.wav"
        _speak(scene["say"][:220], wav)
        segment = workdir / f"seg-{index}.mp4"
        subprocess.run(
            [
                ffmpeg, "-y", "-loop", "1", "-i", str(png), "-i", str(wav),
                "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-shortest", "-vf", f"scale={WIDTH}:{HEIGHT}",
                str(segment),
            ],
            check=True,
            capture_output=True,
        )
        segments.append(segment)

    listing = workdir / "concat.txt"
    listing.write_text("\n".join(f"file '{segment.as_posix()}'" for segment in segments), encoding="utf-8")
    subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out_path)],
        check=True,
        capture_output=True,
    )
    chapters = []
    cursor = 0.0
    for index, segment in enumerate(segments):
        duration = _media_duration(segment)
        title = lesson.get("title", "微课") if index == 0 else lesson.get("steps", [{}])[index - 1].get("title", "")
        chapters.append({"title": title, "start": round(cursor, 2), "duration": round(duration, 2)})
        cursor += duration
    out_path.with_suffix(".json").write_text(
        json.dumps({"chapters": chapters, "duration": round(cursor, 2)}, ensure_ascii=False),
        encoding="utf-8",
    )
    shutil.rmtree(workdir, ignore_errors=True)
    return out_path


def lesson_key(lesson: dict) -> str:
    raw = json.dumps(lesson, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    import sys

    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    target = Path("D:/graduation_design/backend/static/lessons") / f"{lesson_key(payload)}.mp4"
    build_video(payload, target)
    print(target)


def render_video_with_fallback(
    engine: str, lesson: dict, target: Path, key: str, dimension: str = ""
) -> tuple[str, Path, str]:
    """渲染微课；remotion 失败（没装 Node / 渲染报错）时回退到 Python 引擎。

    返回 (实际引擎, 实际文件, 实际 key)。
    """
    if engine == "remotion":
        try:
            from app.features.lessons.remotion_render import render_lesson

            render_lesson(lesson, target, key, dimension)
            return "remotion", target, key
        except Exception as exc:  # noqa: BLE001
            logger.warning("lesson.remotion_failed error_type=%s", type(exc).__name__)
            fallback_key = f"{key}-python"
            fallback_target = target.with_name(f"{fallback_key}.mp4")
            build_video(lesson, fallback_target)
            return "python-fallback", fallback_target, fallback_key

    build_video(lesson, target)
    return "python", target, key

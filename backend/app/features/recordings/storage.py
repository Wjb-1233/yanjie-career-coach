"""面试录像与语音的留存：用于报告页回放。"""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings

MAX_BYTES = 200 * 1024 * 1024
ALLOWED = {".webm", ".mp4", ".m4a", ".wav", ".ogg", ".opus", ".mp3"}


def save_upload(upload: UploadFile) -> str:
    """把上传的音频/视频存到录制目录，返回相对文件名。"""
    suffix = Path(upload.filename or "recording.webm").suffix.lower()
    if suffix not in ALLOWED:
        suffix = ".webm"
    name = f"{uuid4().hex}{suffix}"
    directory = settings.recording_dir_path
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    size = 0
    with target.open("wb") as handle:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                handle.close()
                target.unlink(missing_ok=True)
                raise ValueError("recording_too_large")
            handle.write(chunk)
    return name


def save_file(src: Path, suffix: str) -> str:
    """把本地文件复制进录制目录，返回相对文件名。"""
    if suffix.lower() not in ALLOWED:
        suffix = ".webm"
    name = f"{uuid4().hex}{suffix.lower()}"
    directory = settings.recording_dir_path
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, directory / name)
    return name


def url_of(name: str | None) -> str | None:
    return f"/media/recordings/{name}" if name else None


def remove(name: str | None) -> None:
    if name:
        (settings.recording_dir_path / name).unlink(missing_ok=True)


def copy_into(src: Path, name: str) -> None:
    """把已有文件放入录制目录（用于先分析后留存的场景）。"""
    directory = settings.recording_dir_path
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, directory / name)

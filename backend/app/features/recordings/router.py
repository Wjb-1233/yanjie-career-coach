"""录制回放：校验签名后返回文件（支持 Range，便于拖动进度条）。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.errors import AppError
from app.features.recordings.signing import verify

router = APIRouter(prefix="/media/recordings", tags=["回放"])

MIME = {
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
}


@router.get("/{name}")
async def play_recording(name: str, token: str = "", expires: int = 0) -> FileResponse:
    if "/" in name or "\\" in name or name.startswith("."):
        raise AppError(400, "RECORDING_INVALID", "文件名不合法")
    if not verify(name, token, expires):
        raise AppError(403, "RECORDING_FORBIDDEN", "回放链接已失效，请刷新页面")

    path = settings.recording_dir_path / name
    if not path.is_file():
        raise AppError(404, "RECORDING_NOT_FOUND", "这段录像已被清理")

    return FileResponse(
        path,
        media_type=MIME.get(path.suffix.lower(), "application/octet-stream"),
        headers={"Cache-Control": "private, max-age=600", "Content-Disposition": "inline"},
    )

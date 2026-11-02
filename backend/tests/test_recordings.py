"""录制文件留存与回放地址的单元测试。"""

from io import BytesIO

from starlette.datastructures import UploadFile

from app.core.config import settings
from app.features.recordings import storage


def _upload(name: str, payload: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(payload), filename=name)


def test_save_upload_writes_file_and_returns_url() -> None:
    name = storage.save_upload(_upload("voice.webm", b"fake-audio-bytes"))
    saved = settings.recording_dir_path / name
    try:
        assert saved.exists()
        assert saved.read_bytes() == b"fake-audio-bytes"
        assert name.endswith(".webm")
        url = storage.url_of(name)
        assert url.startswith(f"/media/recordings/{name}?token=")
        assert "expires=" in url
    finally:
        storage.remove(name)


def test_unknown_suffix_falls_back_to_webm() -> None:
    name = storage.save_upload(_upload("answer.xyz", b"data"))
    try:
        assert name.endswith(".webm")
    finally:
        storage.remove(name)


def test_remove_is_safe_for_missing_file() -> None:
    storage.remove("not-exists.webm")
    storage.remove(None)


def test_save_file_copies_existing_path(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-bytes")
    name = storage.save_file(source, ".mp4")
    try:
        assert (settings.recording_dir_path / name).read_bytes() == b"video-bytes"
    finally:
        storage.remove(name)

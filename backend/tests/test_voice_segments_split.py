"""按题切段：真实 ffmpeg 切出可播放片段。"""

from pathlib import Path

import pytest


def _make_video(target: Path) -> Path:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not ffmpeg:
        pytest.skip("ffmpeg 不可用")
    import subprocess

    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc=size=320x180:rate=20:duration=6",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(target),
        ],
        check=True,
        capture_output=True,
    )
    return target


def test_split_segments_produces_playable_files(tmp_path: Path) -> None:
    from app.features.video.segments import split_segments

    source = _make_video(tmp_path / "room.mp4")
    dest = tmp_path / "out"

    segments = split_segments(
        source,
        [
            {"text": "第一问", "start": 0.5, "end": 2.0},
            {"text": "第二问", "start": 3.0, "end": 5.0},
        ],
        dest,
        lambda name: f"/media/recordings/{name}",
    )

    assert [segment["roundNo"] for segment in segments] == [1, 2]
    assert [segment["question"] for segment in segments] == ["第一问", "第二问"]
    for segment in segments:
        assert (dest / segment["file"]).stat().st_size > 1024
        assert segment["url"].startswith("/media/recordings/")

"""微课渲染兜底：没有 Node 或 Remotion 报错时回退 Python 引擎。"""

from pathlib import Path


def test_remotion_failure_falls_back_to_python(monkeypatch, tmp_path: Path) -> None:
    from app.features.lessons import remotion_render, video as module

    def boom(*args, **kwargs):
        raise RuntimeError("node not found")

    def fake_build(lesson, out_path):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"fake-mp4")
        return Path(out_path)

    monkeypatch.setattr(remotion_render, "render_lesson", boom)
    monkeypatch.setattr(module, "build_video", fake_build)

    target = tmp_path / "lesson-remotion.mp4"
    engine, path, key = module.render_video_with_fallback(
        "remotion", {"title": "t", "steps": []}, target, "lesson-remotion"
    )

    assert engine == "python-fallback"
    assert key.endswith("-python")
    assert Path(path).exists()


def test_python_engine_stays_python(monkeypatch, tmp_path: Path) -> None:
    from app.features.lessons import video as module

    def fake_build(lesson, out_path):
        Path(out_path).write_bytes(b"fake-mp4")
        return Path(out_path)

    monkeypatch.setattr(module, "build_video", fake_build)

    target = tmp_path / "lesson-python.mp4"
    engine, path, key = module.render_video_with_fallback("python", {"title": "t"}, target, "lesson-python")
    assert engine == "python"
    assert Path(path).exists()

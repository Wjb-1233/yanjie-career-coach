"""镜头分析的可重复性与预热测试（不需要真实人脸）。"""

from pathlib import Path

from app.features.video import metrics


def test_warmup_is_idempotent() -> None:
    first = metrics.warmup()
    second = metrics.warmup()
    assert first == second
    assert isinstance(first, bool)


def test_analyze_missing_file_returns_dict(tmp_path: Path) -> None:
    result = metrics.analyze_video(tmp_path / "nope.webm")
    assert isinstance(result, dict)
    assert result.get("available") is False

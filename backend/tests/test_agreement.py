"""评分一致性统计的单元测试。"""

from app.features.evaluations.agreement import by_dimension, render_markdown, spearman, summarize


def test_spearman_perfect_and_reverse() -> None:
    assert spearman([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0
    assert spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0


def test_spearman_needs_enough_samples() -> None:
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([3, 3, 3], [1, 2, 3]) is None


def test_summarize_reports_bias_and_agreement() -> None:
    stats = summarize([(3, 3), (4, 4), (2, 3), (5, 4)])
    assert stats["count"] == 4
    assert stats["mae"] == 0.5
    assert stats["exactAgreement"] == 0.5
    assert stats["withinOne"] == 1.0
    assert stats["bias"] == 0.0


def test_by_dimension_groups() -> None:
    rows = [
        {"dimension": "内容与逻辑", "model": 3, "human": 3},
        {"dimension": "内容与逻辑", "model": 4, "human": 3},
        {"dimension": "贴合问题", "model": 2, "human": 3},
    ]
    grouped = by_dimension(rows)
    assert grouped["内容与逻辑"]["count"] == 2
    assert grouped["贴合问题"]["count"] == 1


def test_markdown_contains_key_metrics() -> None:
    stats = summarize([(3, 3), (4, 4), (2, 3)])
    text = render_markdown(stats, {"内容与逻辑": stats}, 3)
    assert "Spearman" in text
    assert "内容与逻辑" in text
    assert "一档内一致率" in text

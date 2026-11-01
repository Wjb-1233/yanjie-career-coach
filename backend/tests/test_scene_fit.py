"""场景维度匹配的单元测试。"""

from types import SimpleNamespace

from app.features.plans.scene_fit import affinity, heuristic_fit, merge_fit


def _scene(**kwargs) -> SimpleNamespace:
    base = {
        "title": "薪资沟通",
        "goal": "把薪资预期说清楚",
        "background": "HR 询问薪资",
        "tags": [],
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_keyword_heuristic_favours_matching_dimension() -> None:
    fit = heuristic_fit(_scene())
    assert fit["correctness"] > fit["logic"]


def test_affinity_prefers_target_dimension() -> None:
    scene = _scene(scene_fit={"logic": 0.2, "relevance": 0.2, "correctness": 0.9, "concision": 0.2})
    assert affinity(scene, ["correctness"]) > affinity(scene, ["logic"])


def test_affinity_falls_back_to_heuristic_without_fit() -> None:
    scene = _scene(scene_fit=None)
    value = affinity(scene, ["correctness"])
    assert 0 < value <= 1


def test_merge_prefers_history_when_present() -> None:
    heuristic = {"logic": 0.4, "relevance": 0.2, "correctness": 0.2, "concision": 0.2}
    history = {"logic": 0.5, "relevance": 0.5, "correctness": 0.0, "concision": 0.0}
    merged = merge_fit(heuristic, history)
    assert merged["relevance"] > merged["correctness"]
    assert abs(sum(merged.values()) - 1.2) < 0.3  # 权重仍在合理区间

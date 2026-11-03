"""JD × 简历匹配分析的单元测试。"""

from app.features.training.job_match import fallback_match, normalize_match

JD = """岗位职责：
1. 负责订单系统的后端开发，要求熟悉 MySQL 与 Redis；
2. 有高并发系统经验，能定位性能瓶颈；
3. 具备跨团队协作经验，能推进项目上线。
"""

RESUME = """王同学，软件工程本科。实习期间负责订单系统下单链路，使用 Redis 预扣库存，
把 P99 从 800ms 降到 200ms，主导过一次跨部门上线协调。
"""


def test_fallback_match_scores_overlap() -> None:
    result = fallback_match(JD, RESUME, None)
    assert 20 <= result["score"] <= 95
    assert result["requirementCount"] >= 2
    assert isinstance(result["gaps"], list)


def test_fallback_without_resume_low_score() -> None:
    with_resume = fallback_match(JD, RESUME, None)
    without = fallback_match(JD, None, None)
    assert with_resume["score"] >= without["score"]


def test_normalize_clamps_and_fills() -> None:
    fallback = fallback_match(JD, RESUME, None)
    merged = normalize_match({"score": 130, "strengths": [], "gaps": ["高并发经验"]}, fallback)
    assert merged["score"] == 100
    assert merged["gaps"][0]["requirement"] == "高并发经验"
    assert merged["strengths"]  # 回落到规则结果


def test_normalize_rejects_empty_payload() -> None:
    fallback = fallback_match(JD, RESUME, None)
    assert normalize_match({}, fallback) == fallback

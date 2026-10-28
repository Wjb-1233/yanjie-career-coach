from types import SimpleNamespace

from app.features.evaluations.service import fallback_evaluation


def test_fallback_returns_five_bounded_dimensions() -> None:
    messages = [
        SimpleNamespace(
            round_no=1,
            content="首先感谢你的提醒，我建议今天先确认三项交付，再讨论风险。",
            flagged=False,
        )
    ]

    result = fallback_evaluation(messages)
    scores = result.scores.model_dump()

    assert set(scores) == {"logic", "appropriateness", "impact", "relevance", "concision"}
    assert all(1 <= score <= 5 for score in scores.values())

from scripts.load_test import AttemptResult, build_summary, parse_sse_data, percentile


def test_percentile_uses_linear_interpolation() -> None:
    assert percentile([100, 200, 300, 400], 0.50) == 250
    assert percentile([100, 200, 300, 400], 0.95) == 385
    assert percentile([], 0.95) is None


def test_summary_rejects_degraded_or_slow_runs() -> None:
    results = [
        AttemptResult(
            virtual_user=1,
            success=True,
            first_token_ms=3500,
            total_response_ms=4000,
            degraded=True,
        ),
        AttemptResult(
            virtual_user=2,
            success=True,
            first_token_ms=4000,
            total_response_ms=4500,
        ),
    ]

    summary = build_summary(
        results,
        wall_seconds=5,
        target_first_token_ms=3000,
        allow_degraded=False,
    )

    assert summary["successRate"] == 1
    assert summary["degradedResponses"] == 1
    assert summary["latencyMs"]["firstToken"]["p95"] == 3975
    assert summary["releaseGates"]["noUnexpectedDegradation"] is False
    assert summary["releaseGates"]["firstTokenP95WithinTarget"] is False
    assert summary["passed"] is False


def test_summary_allows_local_fallback_when_explicit() -> None:
    result = AttemptResult(
        virtual_user=1,
        success=True,
        first_token_ms=120,
        degraded=True,
    )
    summary = build_summary(
        [result],
        wall_seconds=0.2,
        target_first_token_ms=3000,
        allow_degraded=True,
    )
    assert summary["passed"] is True


def test_sse_payload_parser_is_defensive() -> None:
    assert parse_sse_data('data: {"degraded": true}') == {"degraded": True}
    assert parse_sse_data("data: not-json") == {}

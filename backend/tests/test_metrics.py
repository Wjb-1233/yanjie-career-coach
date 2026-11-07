"""指标端点：Prometheus 文本格式，标签只到路由模板。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_metrics_exposes_request_counters() -> None:
    with TestClient(app, client=(f"metrics-{uuid4().hex}", 50100)) as client:
        client.get("/api/v1/health")
        client.get("/api/v1/health")

        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = response.text
        assert 'http_requests_total{method="GET"' in body
        assert 'status="200"' in body
        assert "/health" in body
        assert "http_request_duration_seconds_bucket" in body
        assert "http_request_duration_seconds_sum" in body
        assert "app_info{" in body
        assert "process_uptime_seconds" in body


def test_metrics_records_unmatched_without_error_counter() -> None:
    with TestClient(app, client=(f"metrics-{uuid4().hex}", 50101)) as client:
        missing = client.get("/api/v1/not-a-real-route")
        assert missing.status_code == 404

        body = client.get("/metrics").text
        assert 'route="unmatched"' in body
        # 404 是路由未命中，不应记为 5xx
        assert "http_errors_total{route=\"/api/v1/not-a-real-route\"}" not in body


def test_metrics_keeps_route_template_not_raw_path() -> None:
    with TestClient(app, client=(f"metrics-{uuid4().hex}", 50102)) as client:
        client.get("/api/v1/scenes/does-not-exist")

        body = client.get("/metrics").text
        assert "does-not-exist" not in body
        assert "{scene_id}" in body


def test_business_event_counter() -> None:
    from app.core import metrics

    metrics.incr_event("evaluation", "degraded")
    body = metrics.render()
    assert 'app_events_total{event="evaluation",outcome="degraded"}' in body

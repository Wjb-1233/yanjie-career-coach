from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


LOCAL_PAGE = "http://127.0.0.1:4173/login?redirect=/"
LOCAL_ORIGIN = "http://127.0.0.1:4173"


def test_local_demo_buttons_issue_normal_tokens_with_correct_roles(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    with TestClient(app, client=("demo-login-local", 50000)) as client:
        status = client.get("/api/v1/auth/demo-status", headers={"Referer": LOCAL_PAGE})
        assert status.json()["data"]["enabled"] is True

        student = client.post(
            "/api/v1/auth/demo-login", headers={"Origin": LOCAL_ORIGIN}, json={"role": "STUDENT"}
        )
        assert student.status_code == 200
        assert student.json()["data"]["user"]["role"] == "STUDENT"
        assert "refresh_token=" in student.headers["set-cookie"]
        student_headers = {"Authorization": f"Bearer {student.json()['data']['accessToken']}"}
        assert client.get("/api/v1/admin/overview", headers=student_headers).status_code == 403

        admin = client.post(
            "/api/v1/auth/demo-login", headers={"Origin": LOCAL_ORIGIN}, json={"role": "ADMIN"}
        )
        assert admin.status_code == 200
        assert admin.json()["data"]["user"]["role"] == "ADMIN"
        admin_headers = {"Authorization": f"Bearer {admin.json()['data']['accessToken']}"}
        assert client.get("/api/v1/admin/overview", headers=admin_headers).status_code == 200


def test_demo_login_rejects_nonlocal_and_non_development_requests(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    with TestClient(app, client=("demo-login-blocked", 50000)) as client:
        assert client.get("/api/v1/auth/demo-status").json()["data"]["enabled"] is False
        assert client.post("/api/v1/auth/demo-login", json={"role": "ADMIN"}).status_code == 404
        public = {"Origin": "https://example.com"}
        assert client.post("/api/v1/auth/demo-login", headers=public, json={"role": "ADMIN"}).status_code == 404
        assert client.post("/api/v1/auth/demo-login", headers={"Origin": LOCAL_ORIGIN}, json={"role": "OWNER"}).status_code == 422

        monkeypatch.setattr(settings, "environment", "production")
        assert client.get("/api/v1/auth/demo-status", headers={"Referer": LOCAL_PAGE}).json()["data"]["enabled"] is False
        assert client.post(
            "/api/v1/auth/demo-login", headers={"Origin": LOCAL_ORIGIN}, json={"role": "ADMIN"}
        ).status_code == 404

"""注销账号与前端错误上报。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> tuple[dict[str, str], str]:
    email = f"{prefix}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "DeleteTest123!", "displayName": "注销"},
    )
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}, email


def test_delete_account_requires_confirm_and_password() -> None:
    with TestClient(app, client=(f"delete-{uuid4().hex}", 50140)) as client:
        headers, email = _register(client, "delete")

        wrong_confirm = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "DeleteTest123!", "confirm": "删除"},
        )
        assert wrong_confirm.status_code == 400
        assert wrong_confirm.json()["title"] == "CONFIRM_REQUIRED"

        wrong_password = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "WrongPassword123!", "confirm": "注销"},
        )
        assert wrong_password.status_code == 403
        assert wrong_password.json()["title"] == "PASSWORD_INVALID"

        ok = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "DeleteTest123!", "confirm": "注销"},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["data"]["deleted"] is True

        # 账号已删除：登录失败、旧 token 失效
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "DeleteTest123!"},
            headers={"Referer": "http://testserver/"},
        )
        assert login.status_code == 401
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_delete_account_removes_private_data() -> None:
    with TestClient(app, client=(f"delete-{uuid4().hex}", 50141)) as client:
        headers, _ = _register(client, "delete")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene})

        response = client.request(
            "DELETE",
            "/api/v1/auth/me/delete",
            headers=headers,
            json={"password": "DeleteTest123!", "confirm": "注销"},
        )
        assert response.status_code == 200

        fresh_headers, _ = _register(client, "another")
        export = client.get("/api/v1/auth/me/export", headers=fresh_headers).json()["data"]
        assert export["sessions"] == []


def test_client_error_report_is_accepted_and_counted() -> None:
    from app.core import metrics

    before = metrics.render().count('app_events_total{event="client_error",outcome="received"}')
    with TestClient(app, client=(f"telemetry-{uuid4().hex}", 50142)) as client:
        response = client.post(
            "/api/v1/client-errors",
            json={"message": "TypeError: x is undefined", "route": "/report/1", "stack": "at foo()"},
        )
        assert response.status_code == 204

        oversized = client.post("/api/v1/client-errors", json={"message": "x" * 400})
        assert oversized.status_code == 422

    after = metrics.render()
    assert 'app_events_total{event="client_error",outcome="received"}' in after
    assert after.count('app_events_total{event="client_error",outcome="received"}') == before + 1

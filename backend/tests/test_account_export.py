"""个人数据导出：内容归用户所有，且不包含他人数据。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> tuple[dict[str, str], str]:
    email = f"{prefix}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "ExportTest123!", "displayName": "导出", "consent": True},
    )
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}, email


def test_export_contains_own_training_data() -> None:
    with TestClient(app, client=(f"export-{uuid4().hex}", 50130)) as client:
        headers, email = _register(client, "export")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        session = client.post(
            "/api/v1/training-sessions",
            headers=headers,
            json={"sceneId": scene},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/training-sessions/{session}/messages/complete",
            headers=headers,
            json={"content": "我负责过一次订单系统优化，把接口延迟降了一半。"},
        )

        exported = client.get("/api/v1/auth/me/export", headers=headers)
        assert exported.status_code == 200, exported.text
        data = exported.json()["data"]
        assert data["schemaVersion"] == 1
        assert data["account"]["email"] == email
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["id"] == session
        assert data["sessions"][0]["rounds"]
        assert any("订单系统优化" in row["content"] for row in data["sessions"][0]["rounds"])
        assert "password" not in str(data["account"]).lower()


def test_export_does_not_include_other_users_data() -> None:
    with TestClient(app, client=(f"export-{uuid4().hex}", 50131)) as client:
        owner, _ = _register(client, "owner")
        other, _ = _register(client, "other")
        scene = client.get("/api/v1/scenes", headers=owner).json()["data"][0]["id"]
        session = client.post("/api/v1/training-sessions", headers=owner, json={"sceneId": scene}).json()["data"]["id"]

        exported = client.get("/api/v1/auth/me/export", headers=other).json()["data"]
        assert all(item["id"] != session for item in exported["sessions"])


def test_export_requires_login() -> None:
    with TestClient(app, client=(f"export-{uuid4().hex}", 50132)) as client:
        assert client.get("/api/v1/auth/me/export").status_code == 401

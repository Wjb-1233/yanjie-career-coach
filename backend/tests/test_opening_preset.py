"""开场白走场景预设，不依赖模型。"""

import uuid

from fastapi.testclient import TestClient


def test_create_session_uses_scene_opening_without_llm(monkeypatch) -> None:
    from app.features.training import resume as resume_module

    async def boom(*args, **kwargs):
        raise AssertionError("没有预设开场白时不应该调用模型")

    monkeypatch.setattr(resume_module, "opening_question", boom)

    from app.main import app

    with TestClient(app) as client:
        email = f"opening-{uuid.uuid4().hex[:8]}@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Opening123!", "displayName": "开场校验", "consent": True},
        )
        token = reg.json()["data"]["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}
        scene = client.get("/api/v1/scenes?size=1", headers=headers).json()["data"][0]
        created = client.post(
            "/api/v1/training-sessions", json={"sceneId": scene["id"]}, headers=headers
        )
        assert created.status_code == 201
        opening = created.json()["data"]["messages"][0]["content"]
        assert opening.strip()

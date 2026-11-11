"""提示卡：给出结构与关键词，不泄露完整答案。"""

import uuid

from fastapi.testclient import TestClient


def _headers(client: TestClient) -> dict:
    email = f"hint-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "HintTest123!", "displayName": "提示", "consent": True},
    )
    return {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}


def test_hint_returns_question_structure_and_keywords() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _headers(client)
        scene = client.get("/api/v1/scenes?size=1", headers=headers).json()["data"][0]
        created = client.post(
            "/api/v1/training-sessions", json={"sceneId": scene["id"]}, headers=headers
        ).json()["data"]

        response = client.post(f"/api/v1/training-sessions/{created['id']}/hint", headers=headers)
        assert response.status_code == 200, response.text
        hint = response.json()["data"]
        assert hint["question"]
        assert 3 <= len(hint["structure"]) <= 4
        assert hint["keywords"]
        assert any("不要背答案" in tip for tip in hint["tips"])

"""语音会话落库、引擎标记与旧文案兼容的测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.legacy_text import modernize
from app.main import app


def _register(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"voice-{uuid4().hex[:8]}@example.com",
            "password": "VoiceTest123",
            "displayName": "语音测试",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def test_voice_session_marks_channel_and_engine() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        scene = client.get("/api/v1/scenes?size=1", headers=headers).json()["data"][0]

        created = client.post(
            "/api/v1/voice/sessions",
            headers=headers,
            data={
                "sceneId": scene["id"],
                "turns": '[{"question":"请自我介绍","answer":"我是应届生，做过两个后端项目。"}]',
                "durationSeconds": "42",
                "engine": "pipeline",
            },
        )
        assert created.status_code == 201, created.text
        session_id = created.json()["data"]["id"]

        detail = client.get(f"/api/v1/training-sessions/{session_id}", headers=headers).json()["data"]
        assert detail["channel"] == "VOICE"
        assert detail["durationSeconds"] == 42
        assert detail["delivery"]["engine"] == "pipeline"

        history = client.get("/api/v1/training-sessions", headers=headers).json()["data"]
        row = next(item for item in history if item["id"] == session_id)
        assert row["channel"] == "VOICE"
        assert row["delivery"]["engine"] == "pipeline"


def test_voice_session_rejects_empty_turns() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        scene = client.get("/api/v1/scenes?size=1", headers=headers).json()["data"][0]
        response = client.post(
            "/api/v1/voice/sessions",
            headers=headers,
            data={"sceneId": scene["id"], "turns": "[]", "durationSeconds": "0"},
        )
        assert response.status_code == 422


def test_modernize_replaces_legacy_dimension_words() -> None:
    payload = {
        "title": "感染力提升微课",
        "steps": [{"detail": "感染力是最低维度", "meta": {"impact": 2}}],
        "items": ["用感染力打动对方", 3],
    }
    cleaned = modernize(payload)
    text = str(cleaned)
    assert "感染力" not in text
    assert "信息完整提升微课" in cleaned["title"]
    assert cleaned["steps"][0]["meta"]["correctness"] == 2
    assert cleaned["items"][1] == 3

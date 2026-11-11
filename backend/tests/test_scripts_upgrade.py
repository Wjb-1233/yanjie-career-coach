"""话术优化：维度映射、故事引用与试听接口的测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.features.scripts.service import DIMENSION_GUIDANCE, normalize_dimension
from app.main import app


def test_dimension_guidance_covers_four_dimensions() -> None:
    assert set(DIMENSION_GUIDANCE) == {"内容与逻辑", "贴合问题", "信息完整", "表达干净"}


def test_legacy_dimension_names_map_to_current() -> None:
    assert normalize_dimension("感染力") == "信息完整"
    assert normalize_dimension("逻辑性") == "内容与逻辑"
    assert normalize_dimension("贴合问题") == "贴合问题"
    assert normalize_dimension(None) is None


def _auth(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"script-{uuid4().hex[:8]}@example.com", "password": "ScriptTest123", "displayName": "话术", "consent": True},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def test_preview_returns_audio_url(monkeypatch) -> None:
    from app.features.scripts import router as script_router

    monkeypatch.setattr(script_router, "preview_speech", lambda text: "/media/tts/probe.wav")
    with TestClient(app) as client:
        headers = _auth(client)
        response = client.post("/api/v1/scripts/preview", headers=headers, json={"text": "这是要试听的一句话"})
        assert response.status_code == 200
        assert response.json()["data"]["url"] == "/media/tts/probe.wav"


def test_preview_rejects_empty_text() -> None:
    with TestClient(app) as client:
        headers = _auth(client)
        response = client.post("/api/v1/scripts/preview", headers=headers, json={"text": "  "})
        assert response.status_code == 404

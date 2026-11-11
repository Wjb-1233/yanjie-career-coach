"""实时视频房间：录像与镜头指标走 VIDEO 渠道，并与语音会话共用评分链路。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "房间", "consent": True},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def test_video_room_session_uses_video_channel(monkeypatch) -> None:
    from app.features.evaluations import delivery
    from app.features.video import metrics

    monkeypatch.setattr(delivery, "analyze", lambda _path: {"speechRate": 180, "durationSeconds": 30})
    monkeypatch.setattr(metrics, "analyze_video", lambda _path: {"tips": ["光线偏暗"], "onCamera": 0.8})

    with TestClient(app, client=(f"room-{uuid4().hex}", 50050)) as client:
        headers = _register(client, "room")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]

        response = client.post(
            "/api/v1/voice/sessions",
            headers=headers,
            data={
                "sceneId": scene,
                "turns": '[{"question": "介绍一下自己", "answer": "我叫小王，做过订单系统性能优化。"}]',
                "engine": "doubao",
                "durationSeconds": "30",
            },
            files={"video": ("room.webm", b"\x1aE\xdf\xa3fake-webm", "video/webm")},
        )
        assert response.status_code == 201, response.text
        body = response.json()["data"]
        assert body["recordingUrl"]
        assert body["delivery"]["vision"]["onCamera"] == 0.8

        session = client.get(f"/api/v1/training-sessions/{body['id']}", headers=headers).json()["data"]
        assert session["channel"] == "VIDEO"
        assert session["delivery"]["vision"]["tips"]


def test_voice_session_stays_voice_channel(monkeypatch) -> None:
    from app.features.evaluations import delivery

    monkeypatch.setattr(delivery, "analyze", lambda _path: {"speechRate": 200})

    with TestClient(app, client=(f"room-{uuid4().hex}", 50051)) as client:
        headers = _register(client, "voiceonly")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        response = client.post(
            "/api/v1/voice/sessions",
            headers=headers,
            data={
                "sceneId": scene,
                "turns": '[{"question": "介绍一下自己", "answer": "我叫小李，做过数据看板。"}]',
                "durationSeconds": "20",
            },
            files={"audio": ("voice.webm", b"\x1aE\xdf\xa3fake", "audio/webm")},
        )
        assert response.status_code == 201, response.text
        session = client.get(f"/api/v1/training-sessions/{response.json()['data']['id']}", headers=headers).json()["data"]
        assert session["channel"] == "VOICE"

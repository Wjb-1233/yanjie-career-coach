"""语音 WebSocket 票据鉴权：无票/失效票直接 4003，有效票才进入后续检查。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.features.voice import router as voice_router
from app.main import app

TICKET_INVALID = 4003


def _register(client: TestClient) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"ws-{uuid4().hex[:8]}@example.com",
            "password": "VoiceWs12345",
            "displayName": "语音票据",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
    return headers, user_id


def _ticket(user_id: str, *, secret: str | None = None, expires_in: int = 60, typ: str = "voice-ticket") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "typ": typ,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        },
        secret or settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _close_code(client: TestClient, path: str) -> int:
    """连上后应立刻被服务端关闭，返回关闭码。"""
    with pytest.raises(WebSocketDisconnect) as info:
        with client.websocket_connect(path) as socket:
            socket.receive_text()
    return info.value.code


def test_ws_without_ticket_is_rejected() -> None:
    with TestClient(app, client=(f"ws-{uuid4().hex}", 50210)) as client:
        assert _close_code(client, "/api/v1/voice/ws") == TICKET_INVALID


def test_ws_with_forged_ticket_is_rejected() -> None:
    with TestClient(app, client=(f"ws-{uuid4().hex}", 50211)) as client:
        forged = _ticket("someone", secret="a-forged-secret-that-is-long-enough-32ch")
        assert _close_code(client, f"/api/v1/voice/ws?ticket={forged}") == TICKET_INVALID


def test_ws_with_expired_ticket_is_rejected() -> None:
    with TestClient(app, client=(f"ws-{uuid4().hex}", 50212)) as client:
        _, user_id = _register(client)
        expired = _ticket(user_id, expires_in=-120)
        assert _close_code(client, f"/api/v1/voice/ws?ticket={expired}") == TICKET_INVALID


def test_ws_rejects_access_token_as_ticket() -> None:
    with TestClient(app, client=(f"ws-{uuid4().hex}", 50213)) as client:
        headers, _ = _register(client)
        access = headers["Authorization"].removeprefix("Bearer ")
        assert _close_code(client, f"/api/v1/voice/ws?ticket={access}") == TICKET_INVALID


def test_pipeline_ws_without_ticket_is_rejected() -> None:
    with TestClient(app, client=(f"ws-{uuid4().hex}", 50214)) as client:
        assert _close_code(client, "/api/v1/voice/ws/pipeline?depth=STANDARD&lang=zh") == TICKET_INVALID


def test_ws_ticket_requires_login() -> None:
    with TestClient(app, client=(f"ws-{uuid4().hex}", 50215)) as client:
        denied = client.post("/api/v1/voice/ws-ticket")
        assert denied.status_code == 401, denied.text
        assert denied.json()["title"] == "UNAUTHORIZED"


def test_issued_ticket_authorizes_ws(monkeypatch) -> None:
    # 票据通过后才会走到「语音服务未配置」检查；这里固定该分支，避免真的连上游
    monkeypatch.setattr(voice_router, "realtime_configured", lambda: False)
    with TestClient(app, client=(f"ws-{uuid4().hex}", 50216)) as client:
        headers, _ = _register(client)
        issued = client.post("/api/v1/voice/ws-ticket", headers=headers)
        assert issued.status_code == 200, issued.text
        data = issued.json()["data"]
        assert data["expiresIn"] == 60
        assert data["ticket"]
        assert _close_code(client, f"/api/v1/voice/ws?ticket={data['ticket']}") == 4001

"""令牌用途（typ）隔离：只有 typ=access 的令牌能当登录态用。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _register(client: TestClient) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"token-{uuid4().hex[:8]}@example.com",
            "password": "TokenTest123",
            "displayName": "令牌测试",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, me.json()["data"]["id"]


def _sign(user_id: str, typ: str | None, *, secret: str | None = None, expires_in: int = 3600) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": user_id,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    if typ is not None:
        payload["typ"] = typ
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_access_token_still_works_and_carries_typ() -> None:
    with TestClient(app, client=(f"token-{uuid4().hex}", 50200)) as client:
        headers, user_id = _register(client)
        payload = jwt.decode(
            headers["Authorization"].removeprefix("Bearer "),
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        assert payload["typ"] == "access"
        assert payload["sub"] == user_id


def test_email_verify_token_cannot_be_used_as_bearer() -> None:
    with TestClient(app, client=(f"token-{uuid4().hex}", 50201)) as client:
        _, user_id = _register(client)
        denied = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_sign(user_id, 'verify')}"})
        assert denied.status_code == 401, denied.text
        assert denied.json()["title"] == "TOKEN_INVALID"


def test_voice_ticket_cannot_be_used_as_bearer() -> None:
    with TestClient(app, client=(f"token-{uuid4().hex}", 50202)) as client:
        _, user_id = _register(client)
        denied = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_sign(user_id, 'voice-ticket')}"})
        assert denied.status_code == 401, denied.text
        assert denied.json()["title"] == "TOKEN_INVALID"


def test_token_without_typ_is_rejected() -> None:
    with TestClient(app, client=(f"token-{uuid4().hex}", 50203)) as client:
        _, user_id = _register(client)
        denied = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_sign(user_id, None)}"})
        assert denied.status_code == 401, denied.text
        assert denied.json()["title"] == "TOKEN_INVALID"

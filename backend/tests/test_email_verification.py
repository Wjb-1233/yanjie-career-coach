"""邮箱验证：开启后未验证不能开始训练，验证后恢复。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _enable(monkeypatch, sent: list[dict]) -> None:
    from app.core.config import settings
    from app.features.auth import email_verify
    from app.infrastructure import mailer

    monkeypatch.setattr(settings, "require_email_verification", True, raising=False)
    monkeypatch.setattr(mailer, "smtp_configured", lambda: True)

    async def fake_send(to: str, subject: str, body: str) -> bool:
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr(mailer, "send_email", fake_send)
    monkeypatch.setattr(email_verify.mailer, "send_email", fake_send)


def _register(client: TestClient, prefix: str) -> tuple[dict[str, str], str]:
    email = f"{prefix}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "VerifyTest123!", "displayName": "验证"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}, email


def test_unverified_user_cannot_start_training(monkeypatch) -> None:
    sent: list[dict] = []
    _enable(monkeypatch, sent)

    with TestClient(app, client=(f"verify-{uuid4().hex}", 50170)) as client:
        headers, _ = _register(client, "verify")
        assert len(sent) == 1 and "验证邮箱" in sent[0]["subject"]

        me = client.get("/api/v1/auth/me", headers=headers).json()["data"]
        assert me["emailVerified"] is False

        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        blocked = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene})
        assert blocked.status_code == 403
        assert blocked.json()["title"] == "EMAIL_NOT_VERIFIED"


def test_confirm_token_unlocks_training(monkeypatch) -> None:
    sent: list[dict] = []
    _enable(monkeypatch, sent)

    with TestClient(app, client=(f"verify-{uuid4().hex}", 50171)) as client:
        headers, _ = _register(client, "verify")
        body = sent[0]["body"]
        token = body.split("token=", 1)[1].split("\n", 1)[0].strip()

        confirmed = client.post("/api/v1/auth/verify-email/confirm", json={"token": token})
        assert confirmed.status_code == 200, confirmed.text

        me = client.get("/api/v1/auth/me", headers=headers).json()["data"]
        assert me["emailVerified"] is True

        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene})
        assert created.status_code == 201, created.text


def test_invalid_token_rejected() -> None:
    with TestClient(app, client=(f"verify-{uuid4().hex}", 50172)) as client:
        response = client.post(
            "/api/v1/auth/verify-email/confirm",
            json={"token": "not-a-real-token-but-long-enough"},
        )
        assert response.status_code == 422
        assert response.json()["title"] == "VERIFY_TOKEN_INVALID"


def test_verification_disabled_by_default() -> None:
    with TestClient(app, client=(f"verify-{uuid4().hex}", 50173)) as client:
        headers, _ = _register(client, "verify")
        me = client.get("/api/v1/auth/me", headers=headers).json()["data"]
        assert me["emailVerified"] is True

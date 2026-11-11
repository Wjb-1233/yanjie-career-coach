"""忘记密码链路：邮件链接重置、单次使用、过期与工单回退。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> tuple[str, str]:
    email = f"{prefix}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "ResetTest123!", "displayName": "重置", "consent": True},
    )
    assert response.status_code == 201, response.text
    return email, "ResetTest123!"


def _enable_mail(monkeypatch, sent: list[dict]) -> None:
    from app.features.auth import password_reset as module

    monkeypatch.setattr(module.mailer, "smtp_configured", lambda: True)

    async def fake_send(to: str, link: str, minutes: int) -> bool:
        sent.append({"to": to, "link": link, "minutes": minutes})
        return True

    monkeypatch.setattr(module.mailer, "send_password_reset", fake_send)


def test_reset_link_flow(monkeypatch) -> None:
    sent: list[dict] = []
    _enable_mail(monkeypatch, sent)

    with TestClient(app, client=(f"reset-{uuid4().hex}", 50160)) as client:
        email, old_password = _register(client, "reset")

        requested = client.post("/api/v1/auth/password-reset/request", json={"email": email})
        assert requested.status_code == 200
        assert len(sent) == 1
        token = sent[0]["link"].split("token=", 1)[1]

        new_password = "NewPassword123!"
        confirm = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "password": new_password},
        )
        assert confirm.status_code == 200, confirm.text

        # 新密码可登录，旧密码不可
        assert client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": new_password},
            headers={"Referer": "http://testserver/"},
        ).status_code == 200
        assert client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": old_password},
            headers={"Referer": "http://testserver/"},
        ).status_code == 401

        # 令牌单次使用
        reused = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "password": "AnotherPass123!"},
        )
        assert reused.status_code == 422
        assert reused.json()["title"] == "RESET_TOKEN_INVALID"


def test_expired_token_rejected(monkeypatch) -> None:
    sent: list[dict] = []
    _enable_mail(monkeypatch, sent)

    with TestClient(app, client=(f"reset-{uuid4().hex}", 50161)) as client:
        email, _ = _register(client, "reset")
        client.post("/api/v1/auth/password-reset/request", json={"email": email})
        token = sent[0]["link"].split("token=", 1)[1]

        import hashlib

        from app.db.base import session_factory
        from app.db.models import PasswordResetToken

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        async def expire() -> None:
            async with session_factory() as session:
                row = await session.scalar(
                    select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
                )
                assert row is not None
                row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
                await session.commit()

        client.portal.call(expire)

        response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "password": "AnotherPass123!"},
        )
        assert response.status_code == 422


def test_unknown_email_still_returns_success(monkeypatch) -> None:
    sent: list[dict] = []
    _enable_mail(monkeypatch, sent)

    with TestClient(app, client=(f"reset-{uuid4().hex}", 50162)) as client:
        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": f"nobody-{uuid4().hex[:8]}@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["submitted"] is True
        assert sent == []


def test_without_smtp_falls_back_to_admin_ticket(monkeypatch) -> None:
    from app.features.auth import password_reset as module

    monkeypatch.setattr(module.mailer, "smtp_configured", lambda: False)

    with TestClient(app, client=(f"reset-{uuid4().hex}", 50163)) as client:
        email, _ = _register(client, "reset")
        response = client.post("/api/v1/auth/password-reset/request", json={"email": email})
        assert response.status_code == 200

        from app.db.base import session_factory
        from app.db.models import PasswordResetRequest, User

        async def has_ticket() -> bool:
            async with session_factory() as session:
                user = await session.scalar(select(User).where(User.email == email))
                ticket = await session.scalar(
                    select(PasswordResetRequest).where(
                        PasswordResetRequest.user_id == user.id,
                        PasswordResetRequest.status == "PENDING",
                    )
                )
                return ticket is not None

        assert client.portal.call(has_ticket) is True

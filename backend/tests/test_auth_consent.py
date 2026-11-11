"""注册的《隐私政策》同意位：不勾选必须被拒绝，勾选后正常创建账号。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "ConsentTest123!"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": f"consent-{uuid4().hex[:8]}@example.com",
        "password": PASSWORD,
        "displayName": "同意",
    }
    payload.update(overrides)
    return payload


def test_register_without_consent_is_rejected() -> None:
    with TestClient(app, client=(f"consent-{uuid4().hex}", 50180)) as client:
        email = f"consent-{uuid4().hex[:8]}@example.com"
        response = client.post("/api/v1/auth/register", json=_payload(email=email))

        assert response.status_code == 422, response.text
        body = response.json()
        assert body["title"] == "CONSENT_REQUIRED"
        assert "隐私政策" in body["detail"]
        # 被拒绝的请求不能留下账号：同一邮箱仍然无法登录
        login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 401, login.text


def test_register_with_consent_false_is_rejected() -> None:
    with TestClient(app, client=(f"consent-{uuid4().hex}", 50181)) as client:
        response = client.post("/api/v1/auth/register", json=_payload(consent=False))

        assert response.status_code == 422, response.text
        assert response.json()["title"] == "CONSENT_REQUIRED"


def test_register_with_consent_succeeds() -> None:
    with TestClient(app, client=(f"consent-{uuid4().hex}", 50182)) as client:
        email = f"consent-{uuid4().hex[:8]}@example.com"
        response = client.post("/api/v1/auth/register", json=_payload(email=email, consent=True))

        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["user"]["email"] == email
        assert data["accessToken"]

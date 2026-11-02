"""回放签名与鉴权的测试。"""

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.features.recordings import storage
from app.features.recordings.signing import sign, verify
from app.main import app


def test_sign_and_verify_roundtrip() -> None:
    token, expires = sign("clip.webm", ttl=60)
    assert verify("clip.webm", token, expires)
    assert not verify("other.webm", token, expires)
    assert not verify("clip.webm", token[:-1] + "0", expires)


def test_expired_signature_rejected() -> None:
    token, expires = sign("clip.webm", ttl=-5)
    assert expires < time.time()
    assert not verify("clip.webm", token, expires)


def test_missing_signature_rejected() -> None:
    assert not verify("clip.webm", "", 0)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_playback_requires_valid_signature(client: TestClient) -> None:
    from io import BytesIO

    from starlette.datastructures import UploadFile

    name = storage.save_upload(UploadFile(file=BytesIO(b"x"), filename="probe.webm"))
    try:
        denied = client.get(f"/media/recordings/{name}")
        assert denied.status_code == 403

        token, expires = sign(name, ttl=60)
        allowed = client.get(f"/media/recordings/{name}", params={"token": token, "expires": expires})
        assert allowed.status_code == 200
        assert allowed.headers["content-type"] == "video/webm"
    finally:
        storage.remove(name)


def test_playback_rejects_path_tricks(client: TestClient) -> None:
    token, expires = sign("../settings.py", ttl=60)
    response = client.get("/media/recordings/..%2Fsettings.py", params={"token": token, "expires": expires})
    assert response.status_code in (400, 403, 404)

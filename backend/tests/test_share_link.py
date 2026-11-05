"""教练查看链接：只读、可批注、过期与篡改都拒绝。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "分享"},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _finished_session(client: TestClient, headers: dict[str, str]) -> str:
    scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
    sid = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene}).json()["data"]["id"]
    for index in range(2):
        client.post(
            f"/api/v1/training-sessions/{sid}/messages/complete",
            headers=headers,
            json={"content": f"第{index + 1}轮：先说结论，再补依据。"},
        )
    assert client.post(f"/api/v1/training-sessions/{sid}/finish?create_plan=false", headers=headers).status_code == 200
    return sid


def test_share_link_is_read_only_and_annotatable() -> None:
    with TestClient(app, client=(f"share-{uuid4().hex}", 50040)) as client:
        headers = _register(client, "share")
        session_id = _finished_session(client, headers)

        created = client.post(f"/api/v1/share/training-sessions/{session_id}", headers=headers)
        assert created.status_code == 200
        url = created.json()["data"]["url"]
        token = url.rsplit("/", 1)[-1]
        api_url = f"/api/v1/share/{token}"

        opened = client.get(api_url)
        assert opened.status_code == 200
        payload = opened.json()["data"]
        assert payload["overallScore"] is not None
        assert "recordingUrl" in payload

        annotated = client.post(f"{api_url}/annotations", json={"atMs": 1200, "comment": "开场缺少结论", "author": "教练"})
        assert annotated.status_code == 200
        assert len(annotated.json()["data"]["annotations"]) == 1

        again = client.get(api_url).json()["data"]
        assert again["annotations"][0]["comment"] == "开场缺少结论"
        # 链接只读：不存在改分的入口
        assert client.patch(api_url, json={"overallScore": 100}).status_code in {404, 405}


def test_share_link_rejects_other_user_and_tampering() -> None:
    with TestClient(app, client=(f"share-{uuid4().hex}", 50041)) as client:
        owner = _register(client, "owner")
        stranger = _register(client, "stranger")
        session_id = _finished_session(client, owner)

        assert client.post(f"/api/v1/share/training-sessions/{session_id}", headers=stranger).status_code == 404
        url = client.post(f"/api/v1/share/training-sessions/{session_id}", headers=owner).json()["data"]["url"]
        token = url.rsplit("/", 1)[-1]

        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
        assert client.get(f"/api/v1/share/{tampered}").status_code == 404


def test_expired_share_link_is_gone() -> None:
    from app.features.share.router import issue_token

    with TestClient(app, client=(f"share-{uuid4().hex}", 50042)) as client:
        headers = _register(client, "expire")
        session_id = _finished_session(client, headers)
        token, _ = issue_token(session_id, ttl=-1)
        response = client.get(f"/api/v1/share/{token}")
        assert response.status_code == 410
        assert response.json()["title"] == "SHARE_EXPIRED"

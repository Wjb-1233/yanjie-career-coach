"""教练查看链接可撤销：撤销后原链接与打印版报告一并失效，非本人一律 404。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "撤销", "consent": True},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _finished_session(client: TestClient, headers: dict[str, str]) -> str:
    scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
    sid = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene}).json()["data"]["id"]
    for index in range(2):
        client.post(
            f"/api/v1/training-sessions/{sid}/messages/complete",
            headers=headers,
            json={"content": f"第{index + 1}轮：先说结论，再补依据。结果把响应时间从 800ms 降到 300ms。"},
        )
    assert client.post(f"/api/v1/training-sessions/{sid}/finish?create_plan=false", headers=headers).status_code == 200
    return sid


def _share_token(client: TestClient, headers: dict[str, str], session_id: str) -> str:
    url = client.post(f"/api/v1/share/training-sessions/{session_id}", headers=headers).json()["data"]["url"]
    return url.rsplit("/", 1)[-1]


def test_revoked_link_and_report_are_gone() -> None:
    with TestClient(app, client=(f"revoke-{uuid4().hex}", 50050)) as client:
        headers = _register(client, "revoke")
        session_id = _finished_session(client, headers)
        token = _share_token(client, headers, session_id)

        assert client.get(f"/api/v1/share/{token}").status_code == 200
        assert client.get(f"/api/v1/share/{token}/report").status_code == 200

        revoked = client.delete(f"/api/v1/share/{token}", headers=headers)
        assert revoked.status_code == 200
        assert revoked.json()["data"]["revoked"] is True

        gone = client.get(f"/api/v1/share/{token}")
        assert gone.status_code == 410
        assert gone.json()["title"] == "SHARE_REVOKED"
        assert "撤销" in gone.json()["detail"]

        report = client.get(f"/api/v1/share/{token}/report")
        assert report.status_code == 410
        assert report.json()["title"] == "SHARE_REVOKED"

        # 撤销是幂等的：再撤一次仍然成功，不会变成 500
        assert client.delete(f"/api/v1/share/{token}", headers=headers).status_code == 200


def test_only_owner_can_revoke() -> None:
    with TestClient(app, client=(f"revoke-{uuid4().hex}", 50051)) as client:
        owner = _register(client, "revoke-owner")
        stranger = _register(client, "revoke-stranger")
        session_id = _finished_session(client, owner)
        token = _share_token(client, owner, session_id)

        assert client.delete(f"/api/v1/share/{token}", headers=stranger).status_code == 404
        # 别人的撤销无效，链接照旧可读
        assert client.get(f"/api/v1/share/{token}").status_code == 200


def test_report_page_renders_scores_and_rounds() -> None:
    with TestClient(app, client=(f"revoke-{uuid4().hex}", 50052)) as client:
        headers = _register(client, "revoke-report")
        session_id = _finished_session(client, headers)
        token = _share_token(client, headers, session_id)

        payload = client.get(f"/api/v1/share/{token}").json()["data"]
        report = client.get(f"/api/v1/share/{token}/report")
        assert report.status_code == 200
        assert report.headers["content-type"].startswith("text/html")
        page = report.text

        # 打印提示 + 场景 + 四维分数与总分
        assert "Ctrl+P" in page
        assert payload["sceneTitle"] in page
        assert labels_in(page, payload["scores"])
        assert str(payload["scores"]["logic"]) in page
        assert str(round(payload["overallScore"], 1)) in page
        # 逐题问答摘要、证据区与总评
        assert "第 1 题" in page
        assert "逐题问答摘要" in page
        assert "证据与整改" in page
        assert payload["summary"][:12] in page
        # 无外部资源、无脚本
        assert "http://" not in page and "https://" not in page
        assert "<script" not in page


def labels_in(page: str, scores: dict[str, int]) -> bool:
    for label in ("内容与逻辑", "贴合问题", "信息完整", "表达干净"):
        if label not in page:
            return False
    return all(str(value) in page for value in scores.values())

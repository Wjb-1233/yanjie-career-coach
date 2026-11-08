"""群面：题目、发言轮转与评估。"""

import uuid

from fastapi.testclient import TestClient


def _headers(client: TestClient) -> dict:
    email = f"group-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "GroupTest123!", "displayName": "群面"},
    )
    return {"Authorization": f"Bearer {reg.json()['data']['accessToken']}"}


def test_topics_and_opening() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _headers(client)
        topics = client.get("/api/v1/group-interviews/topics", headers=headers).json()["data"]
        assert len(topics) >= 5
        created = client.post(
            "/api/v1/group-interviews",
            json={"topicId": topics[0]["id"]},
            headers=headers,
        )
        assert created.status_code == 201
        data = created.json()["data"]
        assert data["status"] == "ACTIVE"
        assert "无领导小组讨论" in data["turns"][0]["text"]
        assert topics[0]["prompt"][:10] in data["turns"][0]["text"]


def test_message_rotates_speakers_and_finish_scores() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _headers(client)
        topic = client.get("/api/v1/group-interviews/topics", headers=headers).json()["data"][0]
        group = client.post(
            "/api/v1/group-interviews", json={"topicId": topic["id"]}, headers=headers
        ).json()["data"]

        first = client.post(
            f"/api/v1/group-interviews/{group['id']}/messages",
            json={"content": "我同意先做性能优化，因为它是所有功能的基础，我建议先小范围验证。"},
            headers=headers,
        )
        assert first.status_code == 200
        turns = first.json()["data"]["turns"]
        assert turns[-1]["role"] == "候选人 A"

        second = client.post(
            f"/api/v1/group-interviews/{group['id']}/messages",
            json={"content": "我想补充一个风险：只做性能优化收益不够直观，是否同时做数据看板？"},
            headers=headers,
        )
        assert second.status_code == 200
        turns = second.json()["data"]["turns"]
        assert turns[-1]["role"] == "候选人 B"

        finished = client.post(
            f"/api/v1/group-interviews/{group['id']}/finish", headers=headers
        )
        assert finished.status_code == 200
        result = finished.json()["data"]["result"]
        assert 0 <= result["score"] <= 100
        assert len(result["dimensions"]) == 4


def test_cannot_send_after_finish() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _headers(client)
        topic = client.get("/api/v1/group-interviews/topics", headers=headers).json()["data"][0]
        group = client.post(
            "/api/v1/group-interviews", json={"topicId": topic["id"]}, headers=headers
        ).json()["data"]
        client.post(f"/api/v1/group-interviews/{group['id']}/messages", json={"content": "我先说两句看法。"}, headers=headers)
        client.post(f"/api/v1/group-interviews/{group['id']}/finish", headers=headers)
        blocked = client.post(
            f"/api/v1/group-interviews/{group['id']}/messages",
            json={"content": "还能继续说吗？"},
            headers=headers,
        )
        assert blocked.status_code == 409

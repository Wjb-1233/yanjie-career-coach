"""题库：聚合场景题目，收藏与掌握度按用户持久化。"""

import uuid

from fastapi.testclient import TestClient


def _client_and_headers(client: TestClient) -> dict:
    email = f"bank-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "BankTest123!", "displayName": "题库"},
    )
    token = reg.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_bank_aggregates_scene_questions() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _client_and_headers(client)
        response = client.get("/api/v1/question-bank?size=50", headers=headers)
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["total"] > 100
        assert len(body["items"]) == 50
        assert body["facets"]["industries"]
        first = body["items"][0]
        assert {"id", "text", "sceneId", "category", "difficulty"} <= set(first)


def test_bank_favorite_and_mastered_persist() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _client_and_headers(client)
        first = client.get("/api/v1/question-bank?size=1", headers=headers).json()["data"]["items"][0]
        qid = first["id"]

        saved = client.put(
            f"/api/v1/question-bank/{qid}",
            json={"favorite": True, "mastered": True},
            headers=headers,
        )
        assert saved.status_code == 200
        assert saved.json()["data"] == {"id": qid, "favorite": True, "mastered": True}

        favorites = client.get("/api/v1/question-bank?favorite=true", headers=headers).json()["data"]
        assert favorites["total"] == 1
        assert favorites["items"][0]["id"] == qid
        assert favorites["items"][0]["mastered"] is True

        mastered = client.get("/api/v1/question-bank?state=mastered", headers=headers).json()["data"]
        assert mastered["total"] == 1


def test_bank_rejects_unknown_question() -> None:
    from app.main import app

    with TestClient(app) as client:
        headers = _client_and_headers(client)
        response = client.put(
            "/api/v1/question-bank/not-a-question",
            json={"favorite": True},
            headers=headers,
        )
        assert response.status_code == 404

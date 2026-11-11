"""题库刷题：分页筛选、收藏/掌握 upsert、用户隔离与概览统计一致。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{uuid4().hex[:8]}@example.com",
            "password": "QuestionBank123!",
            "displayName": "题库",
            "consent": True,
        },
    )
    assert response.status_code < 400, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _all_items(client: TestClient, headers: dict[str, str], **params) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        payload = client.get(
            "/api/v1/question-bank", headers=headers, params={**params, "page": page, "size": 100}
        ).json()["data"]
        items.extend(payload["items"])
        if page * 100 >= payload["total"]:
            return items
        page += 1


def test_list_pagination_and_filters() -> None:
    with TestClient(app, client=(f"bank-{uuid4().hex}", 50130)) as client:
        headers = _register(client, "bank")

        first = client.get("/api/v1/question-bank", headers=headers).json()["data"]
        assert first["page"] == 1 and first["size"] == 20
        assert len(first["items"]) == 20
        assert first["total"] >= 100
        assert set(first["items"][0]) >= {"id", "sceneId", "sceneTitle", "text", "dimension", "favorite", "mastered"}

        # 新用户没有任何标记：未掌握为全部，已掌握与收藏都是空
        assert client.get("/api/v1/question-bank", headers=headers, params={"mastered": "true"}).json()["data"]["total"] == 0
        assert client.get("/api/v1/question-bank", headers=headers, params={"favorite": "true"}).json()["data"]["total"] == 0
        assert client.get("/api/v1/question-bank", headers=headers, params={"mastered": "false"}).json()["data"]["total"] == first["total"]

        # 维度筛选
        dimension = first["items"][0]["dimension"]
        filtered = client.get("/api/v1/question-bank", headers=headers, params={"dimension": dimension}).json()["data"]
        assert filtered["total"] < first["total"]
        assert all(item["dimension"] == dimension for item in filtered["items"])

        # 场景筛选 + 分页
        scene_id = first["items"][0]["sceneId"]
        by_scene = client.get("/api/v1/question-bank", headers=headers, params={"sceneId": scene_id}).json()["data"]
        assert all(item["sceneId"] == scene_id for item in by_scene["items"])
        page_two = client.get("/api/v1/question-bank", headers=headers, params={"page": 2}).json()["data"]
        assert page_two["page"] == 2 and page_two["items"][0]["id"] != first["items"][0]["id"]

        assert client.get("/api/v1/question-bank", headers=headers, params={"page": 0}).status_code == 422
        assert client.get("/api/v1/question-bank").status_code == 401


def test_state_upsert_and_read_back() -> None:
    with TestClient(app, client=(f"bank-{uuid4().hex}", 50131)) as client:
        headers = _register(client, "bank")
        target = client.get("/api/v1/question-bank", headers=headers).json()["data"]["items"][0]["id"]

        marked = client.patch(f"/api/v1/question-bank/{target}/state", headers=headers, json={"mastered": True})
        assert marked.status_code == 200, marked.text
        assert marked.json()["data"] == {"questionId": target, "favorite": False, "mastered": True}

        listed = client.get("/api/v1/question-bank", headers=headers, params={"mastered": "true"}).json()["data"]
        assert listed["total"] == 1 and listed["items"][0]["id"] == target
        assert client.get("/api/v1/question-bank/summary", headers=headers).json()["data"]["mastered"] == 1

        # 只传 favorite 时 mastered 保持原值（upsert 的局部更新）
        patched = client.patch(f"/api/v1/question-bank/{target}/state", headers=headers, json={"favorite": True}).json()["data"]
        assert patched == {"questionId": target, "favorite": True, "mastered": True}
        assert client.get("/api/v1/question-bank", headers=headers, params={"favorite": "true"}).json()["data"]["total"] == 1

        # 取消掌握不影响收藏
        client.patch(f"/api/v1/question-bank/{target}/state", headers=headers, json={"mastered": False})
        summary = client.get("/api/v1/question-bank/summary", headers=headers).json()["data"]
        assert summary["mastered"] == 0 and summary["favorite"] == 1
        assert client.get("/api/v1/question-bank", headers=headers, params={"mastered": "false"}).json()["data"]["total"] == summary["total"]

        assert client.patch("/api/v1/question-bank/q0000000000000000/state", headers=headers, json={"favorite": True}).status_code == 404
        assert client.patch(f"/api/v1/question-bank/{target}/state", headers=headers, json={}).status_code == 422


def test_state_is_scoped_to_owner() -> None:
    with TestClient(app, client=(f"bank-{uuid4().hex}", 50132)) as client:
        owner = _register(client, "bank-owner")
        other = _register(client, "bank-other")
        target = client.get("/api/v1/question-bank", headers=owner).json()["data"]["items"][0]["id"]

        client.patch(f"/api/v1/question-bank/{target}/state", headers=owner, json={"mastered": True, "favorite": True})

        # 他人读不到我的标记
        mine = [item for item in _all_items(client, other) if item["id"] == target][0]
        assert mine["mastered"] is False and mine["favorite"] is False
        assert client.get("/api/v1/question-bank/summary", headers=other).json()["data"]["mastered"] == 0

        # 他人改同一题只写自己的记录
        client.patch(f"/api/v1/question-bank/{target}/state", headers=other, json={"mastered": True})
        assert client.get("/api/v1/question-bank/summary", headers=other).json()["data"]["mastered"] == 1
        owner_summary = client.get("/api/v1/question-bank/summary", headers=owner).json()["data"]
        assert owner_summary["mastered"] == 1 and owner_summary["favorite"] == 1
        owner_item = [item for item in _all_items(client, owner) if item["id"] == target][0]
        assert owner_item["mastered"] is True and owner_item["favorite"] is True
        other_item = [item for item in _all_items(client, other) if item["id"] == target][0]
        assert other_item["mastered"] is True and other_item["favorite"] is False


def test_summary_matches_list() -> None:
    with TestClient(app, client=(f"bank-{uuid4().hex}", 50133)) as client:
        headers = _register(client, "bank")
        items = _all_items(client, headers)
        for item in items[:3]:
            client.patch(f"/api/v1/question-bank/{item['id']}/state", headers=headers, json={"mastered": True})

        summary = client.get("/api/v1/question-bank/summary", headers=headers).json()["data"]
        listed = _all_items(client, headers)
        mastered_items = [item for item in listed if item["mastered"]]

        assert summary["total"] == len(listed)
        assert summary["mastered"] == len(mastered_items) == 3
        assert sum(row["total"] for row in summary["dimensions"]) == summary["total"]
        assert sum(row["total"] for row in summary["scenes"]) == summary["total"]
        assert sum(row["mastered"] for row in summary["dimensions"]) == summary["mastered"]
        assert sum(row["mastered"] for row in summary["scenes"]) == summary["mastered"]
        assert len(summary["scenes"]) == len({item["sceneId"] for item in listed})
        assert all(0.0 <= row["rate"] <= 100.0 for row in summary["dimensions"] + summary["scenes"])

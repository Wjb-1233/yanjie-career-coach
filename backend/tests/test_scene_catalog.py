from collections import Counter
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.seed import SCENES
from app.main import app


def test_seed_catalog_covers_every_visible_category() -> None:
    expected = {"HR 初面", "技术一面", "技术二面 / 复面", "交叉面 / 总监面", "HRBP/HR 终面", "大老板 / 高管终面"}
    counts = Counter(scene["category"] for scene in SCENES)
    assert set(counts) == expected | {"基础能力提升"}
    assert all(counts[category] >= 1 for category in expected)
    assert counts["基础能力提升"] == 5
    assert len({scene["id"] for scene in SCENES}) == len(SCENES)
    assert all(all(scene.get(field) for field in (
        "title", "industry", "position", "role_name", "difficulty", "background", "goal", "tags", "opening_line"
    )) for scene in SCENES)
    assert {scene["difficulty"] for scene in SCENES} == {"入门", "中级", "进阶"}
    assert {"为什么选择我们公司", "如何回应加班安排", "最早到岗时间怎么谈"}.issubset(
        {scene["title"] for scene in SCENES}
    )


def test_every_category_has_a_startable_scene() -> None:
    with TestClient(app, client=(f"catalog-{uuid4().hex}", 50000)) as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": f"catalog-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!",
            "displayName": "场景覆盖测试",
        })
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        response = client.get("/api/v1/scenes", params={"size": 100}, headers=headers)
        assert response.status_code == 200
        scenes = response.json()["data"]
        assert len(scenes) >= len(SCENES)
        for category in ("HR 初面", "技术一面", "技术二面 / 复面", "交叉面 / 总监面", "HRBP/HR 终面", "大老板 / 高管终面", "基础能力提升"):
            scene = next(item for item in scenes if item["category"] == category)
            started = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene["id"]})
            assert started.status_code == 201
            assert started.json()["data"]["sceneId"] == scene["id"]


def test_scene_favorites_are_private_and_listed_separately() -> None:
    with TestClient(app, client=(f"scene-favorites-{uuid4().hex}", 50000)) as client:
        users = []
        for _ in range(2):
            registered = client.post("/api/v1/auth/register", json={
                "email": f"favorite-{uuid4().hex[:8]}@example.com",
                "password": "GraduateDesign123!", "displayName": "收藏测试",
            })
            users.append({"Authorization": f"Bearer {registered.json()['data']['accessToken']}"})
        scene_id = client.get("/api/v1/scenes", headers=users[0]).json()["data"][0]["id"]
        assert client.get("/api/v1/scenes/favorites", headers=users[0]).json()["data"] == []
        assert client.post(f"/api/v1/scenes/{scene_id}/favorite", headers=users[0]).status_code == 200
        favorites = client.get("/api/v1/scenes/favorites", headers=users[0]).json()["data"]
        assert [item["id"] for item in favorites] == [scene_id]
        assert favorites[0]["favorite"] is True
        assert client.get("/api/v1/scenes/favorites", headers=users[1]).json()["data"] == []

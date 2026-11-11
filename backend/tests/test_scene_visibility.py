"""场景详情越权（IDOR）：他人私密场景一律 404，public 仍对所有人可见。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{uuid4().hex[:8]}@example.com",
            "password": "SceneVisibility123!",
            "displayName": prefix,
            "consent": True,
        },
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _private_scene(client: TestClient, headers: dict[str, str]) -> dict:
    payload = {
        "title": f"自建私密场景-{uuid4().hex[:6]}",
        "industry": "互联网",
        "position": "后端开发工程师",
        "roleName": "技术负责人",
        "category": "技术二面/复面",
        "difficulty": "中级",
        "background": "电商中台团队，负责订单与库存服务，日均千万级请求。",
        "goal": "考察接口设计、性能优化与故障排查思路。",
        "openingLine": "你好，我是技术负责人，今天聊聊你的项目。",
        "questions": [
            {"text": "介绍一下你做过的最复杂的接口设计", "dimension": "内容与逻辑"},
            {"text": "线上接口超时你会怎么排查", "dimension": "信息完整"},
        ],
    }
    created = client.post("/api/v1/my-scenes", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    return created.json()["data"]


def test_private_scene_detail_hidden_from_others() -> None:
    with TestClient(app, client=(f"idor-{uuid4().hex}", 50070)) as client:
        owner = _register(client, "owner")
        stranger = _register(client, "stranger")
        scene = _private_scene(client, owner)

        detail = client.get(f"/api/v1/scenes/{scene['id']}", headers=owner)
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["id"] == scene["id"]

        hidden = client.get(f"/api/v1/scenes/{scene['id']}", headers=stranger)
        assert hidden.status_code == 404
        assert hidden.json()["title"] == "NOT_FOUND"
        assert hidden.json()["detail"] == "场景不存在"

        # 同一越权口子的第二个入口：用他人私密场景开训练会话
        blocked = client.post(
            "/api/v1/training-sessions", headers=stranger, json={"sceneId": scene["id"]}
        )
        assert blocked.status_code == 404
        assert blocked.json()["detail"] == "场景不存在"

        # 列表行为不变：他人私密场景本就不出现
        listed = client.get("/api/v1/scenes", headers=stranger, params={"size": 100}).json()["data"]
        assert all(item["id"] != scene["id"] for item in listed)


def test_public_scene_detail_open_to_everyone() -> None:
    with TestClient(app, client=(f"idor-{uuid4().hex}", 50071)) as client:
        headers = _register(client, "reader")
        public_id = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]

        response = client.get(f"/api/v1/scenes/{public_id}", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["visibility"] == "public"

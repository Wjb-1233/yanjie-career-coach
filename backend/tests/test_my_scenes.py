"""我的场景：创建校验、私有隔离、能进训练与推荐。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "MySceneTest123!", "displayName": "自建"},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _payload(**overrides) -> dict:
    body = {
        "title": "字节跳动-后端开发-二面",
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
    body.update(overrides)
    return body


def test_create_and_list_my_scene() -> None:
    with TestClient(app, client=(f"mine-{uuid4().hex}", 50060)) as client:
        headers = _register(client, "mine")
        created = client.post("/api/v1/my-scenes", headers=headers, json=_payload())
        assert created.status_code == 201, created.text
        scene = created.json()["data"]
        assert scene["mine"] is True
        assert scene["visibility"] == "private"

        listed = client.get("/api/v1/my-scenes", headers=headers).json()["data"]
        assert listed["count"] == 1
        assert listed["items"][0]["id"] == scene["id"]

        # 出现在场景广场（自己的私有场景）
        scenes = client.get("/api/v1/scenes", headers=headers, params={"size": 100}).json()["data"]
        assert any(item["id"] == scene["id"] for item in scenes)


def test_question_validation_and_duplicate_title() -> None:
    with TestClient(app, client=(f"mine-{uuid4().hex}", 50061)) as client:
        headers = _register(client, "mine")
        one = client.post(
            "/api/v1/my-scenes",
            headers=headers,
            json=_payload(questions=[{"text": "只有一个问题可以吗"}]),
        )
        assert one.status_code == 422
        assert one.json()["title"] == "QUESTIONS_TOO_FEW"

        ok_first = client.post("/api/v1/my-scenes", headers=headers, json=_payload())
        assert ok_first.status_code == 201
        duplicate = client.post("/api/v1/my-scenes", headers=headers, json=_payload())
        assert duplicate.status_code == 422
        assert duplicate.json()["title"] == "SCENE_TITLE_DUPLICATE"

        deduped = client.post(
            "/api/v1/my-scenes",
            headers=headers,
            json=_payload(
                title="另一个场景标题",
                questions=[
                    {"text": "线上接口超时你会怎么排查"},
                    {"text": "线上接口超时你会怎么排查？"},
                    {"text": "介绍一下你做过的最复杂的接口设计"},
                ],
            ),
        )
        assert deduped.status_code == 201, deduped.text
        assert len(deduped.json()["data"]["tags"]) == 0
        # 去重后仍剩两条，问题库应为两条
        detail = client.get(f"/api/v1/my-scenes", headers=headers).json()["data"]["items"]
        target = next(item for item in detail if item["id"] == deduped.json()["data"]["id"])
        assert target["title"] == "另一个场景标题"


def test_private_scene_is_isolated() -> None:
    with TestClient(app, client=(f"mine-{uuid4().hex}", 50062)) as client:
        owner = _register(client, "owner")
        other = _register(client, "other")
        scene = client.post("/api/v1/my-scenes", headers=owner, json=_payload()).json()["data"]

        # 别人看不到、改不了、删不掉
        others = client.get("/api/v1/my-scenes", headers=other).json()["data"]
        assert all(item["id"] != scene["id"] for item in others["items"])
        assert client.patch(f"/api/v1/my-scenes/{scene['id']}", headers=other, json=_payload()).status_code == 404
        assert client.delete(f"/api/v1/my-scenes/{scene['id']}", headers=other).status_code == 404

        # 场景广场也不出现
        scenes = client.get("/api/v1/scenes", headers=other, params={"size": 100}).json()["data"]
        assert all(item["id"] != scene["id"] for item in scenes)


def test_my_scene_can_be_trained_and_deleted() -> None:
    with TestClient(app, client=(f"mine-{uuid4().hex}", 50063)) as client:
        headers = _register(client, "mine")
        scene = client.post("/api/v1/my-scenes", headers=headers, json=_payload()).json()["data"]

        session = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene["id"]})
        assert session.status_code == 201, session.text

        assert client.delete(f"/api/v1/my-scenes/{scene['id']}", headers=headers).status_code == 204
        listed = client.get("/api/v1/my-scenes", headers=headers).json()["data"]
        assert listed["count"] == 0
        # 历史会话仍可访问（软删除）
        assert client.get(f"/api/v1/training-sessions/{session.json()['data']['id']}", headers=headers).status_code == 200

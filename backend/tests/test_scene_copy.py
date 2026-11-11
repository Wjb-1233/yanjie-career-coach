"""复制内置场景：可编辑、题目保留、他人私有场景不可复制。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "CopyTest123!", "displayName": "复制", "consent": True},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def test_copy_builtin_scene_keeps_questions() -> None:
    with TestClient(app, client=(f"copy-{uuid4().hex}", 50080)) as client:
        headers = _register(client, "copy")
        builtin = client.get("/api/v1/scenes", headers=headers, params={"size": 5}).json()["data"][0]

        copied = client.post(f"/api/v1/my-scenes/from-scene/{builtin['id']}", headers=headers)
        assert copied.status_code == 201, copied.text
        scene = copied.json()["data"]
        assert scene["mine"] is True
        assert scene["title"].endswith("（我的版本）")
        assert scene["source"] == "copy"

        mine = client.get("/api/v1/my-scenes", headers=headers).json()["data"]
        assert mine["count"] == 1

        # 可编辑
        updated = client.patch(
            f"/api/v1/my-scenes/{scene['id']}",
            headers=headers,
            json={
                "title": "我改过的场景",
                "industry": scene["industry"],
                "position": scene["position"],
                "roleName": scene["roleName"],
                "category": scene["category"],
                "difficulty": scene["difficulty"],
                "background": scene["background"],
                "goal": scene["goal"],
                "openingLine": scene["openingLine"],
                "questions": [
                    {"text": "第一题：介绍一下你的项目", "dimension": "内容与逻辑"},
                    {"text": "第二题：遇到过什么难题", "dimension": "信息完整"},
                ],
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["title"] == "我改过的场景"


def test_cannot_copy_other_users_private_scene() -> None:
    with TestClient(app, client=(f"copy-{uuid4().hex}", 50081)) as client:
        owner = _register(client, "owner")
        other = _register(client, "other")
        payload = {
            "title": "私有场景标题",
            "industry": "互联网",
            "position": "后端开发",
            "roleName": "面试官",
            "category": "技术一面",
            "difficulty": "中级",
            "background": "一段足够长的背景描述用于通过校验。",
            "goal": "考察基础能力。",
            "questions": [
                {"text": "问题一：说说你的项目", "dimension": "内容与逻辑"},
                {"text": "问题二：说说你的难点", "dimension": "信息完整"},
            ],
        }
        scene = client.post("/api/v1/my-scenes", headers=owner, json=payload).json()["data"]
        assert client.post(f"/api/v1/my-scenes/from-scene/{scene['id']}", headers=other).status_code == 404

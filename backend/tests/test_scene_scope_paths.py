"""场景归属校验在话术 / 语音 / 视频三个入口保持一致：他人私密场景一律 404。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"scope-{prefix}-{uuid4().hex[:8]}@example.com",
            "password": "SceneScope123!",
            "displayName": prefix,
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _private_scene(client: TestClient, headers: dict[str, str]) -> dict:
    payload = {
        "title": f"归属校验私密场景-{uuid4().hex[:6]}",
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


def _public_scene_id(client: TestClient, headers: dict[str, str]) -> str:
    return client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]


def test_owner_generates_scripts_from_private_scene() -> None:
    """回归保护：scripts.generate 必须把 user_id 传给 get_scene，本人私密场景不能被 404。"""

    with TestClient(app, client=(f"scope-{uuid4().hex}", 50090)) as client:
        owner = _register(client, "owner")
        scene = _private_scene(client, owner)

        generated = client.post(
            "/api/v1/scripts/generate",
            headers=owner,
            json={"sceneId": scene["id"], "objective": "回答为什么选择这个岗位"},
        )
        assert generated.status_code == 201, generated.text
        versions = generated.json()["data"]["versions"]
        assert len(versions) == 3
        assert all(item["sceneId"] == scene["id"] for item in versions)


def test_voice_session_rejects_foreign_private_scene() -> None:
    with TestClient(app, client=(f"scope-{uuid4().hex}", 50091)) as client:
        owner = _register(client, "owner")
        stranger = _register(client, "stranger")
        scene = _private_scene(client, owner)

        blocked = client.post(
            "/api/v1/voice/sessions",
            headers=stranger,
            data={
                "sceneId": scene["id"],
                "turns": '[{"question":"请自我介绍","answer":"我是应届生，做过两个后端项目。"}]',
                "durationSeconds": "30",
            },
        )
        assert blocked.status_code == 404
        assert blocked.json()["detail"] == "场景不存在"


def test_video_interview_rejects_foreign_private_scene() -> None:
    with TestClient(app, client=(f"scope-{uuid4().hex}", 50092)) as client:
        owner = _register(client, "owner")
        stranger = _register(client, "stranger")
        scene = _private_scene(client, owner)

        blocked = client.post(
            "/api/v1/video-interviews",
            headers=stranger,
            data={"sceneId": scene["id"], "questions": "[]", "durationSeconds": "30"},
            files={"video": ("answer.webm", b"\x1aE\xdf\xa3fake-webm", "video/webm")},
        )
        assert blocked.status_code == 404
        assert blocked.json()["detail"] == "场景不存在"


def test_public_scene_scripts_generate_unchanged() -> None:
    with TestClient(app, client=(f"scope-{uuid4().hex}", 50093)) as client:
        headers = _register(client, "reader")
        public_id = _public_scene_id(client, headers)

        generated = client.post(
            "/api/v1/scripts/generate",
            headers=headers,
            json={"sceneId": public_id, "objective": "复述一次项目复盘的结论"},
        )
        assert generated.status_code == 201, generated.text
        data = generated.json()["data"]
        assert data["versions"] and data["versions"][0]["sceneId"] == public_id

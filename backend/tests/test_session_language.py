"""英文面试：会话记录语言，提示词切换为英文。"""

import uuid

from fastapi.testclient import TestClient

from app.features.training.graph import prompt_node


def _state(language: str) -> dict:
    return {
        "round_no": 2,
        "max_rounds": 12,
        "user_text": "I built an order system.",
        "scene_title": "后端开发技术面试",
        "scene_id": "scene-interview-03",
        "scene_category": "技术一面",
        "scene_difficulty": "中级",
        "role_name": "技术面试官",
        "scene_background": "校招技术一面",
        "scene_goal": "考察基础与项目",
        "core_idea": "",
        "resume_text": "",
        "stage": "DISCOVERY",
        "flags": [],
        "should_finish": False,
        "finish_after_reply": False,
        "mode": "STANDARD",
        "depth": "STANDARD",
        "language": language,
        "planned_question": "",
        "prompt": "",
    }


def test_english_prompt_requires_english() -> None:
    prompt = prompt_node(_state("en"))["prompt"]
    assert "conducted in English" in prompt


def test_chinese_prompt_has_no_english_directive() -> None:
    prompt = prompt_node(_state("zh"))["prompt"]
    assert "conducted in English" not in prompt


def test_create_session_persists_language() -> None:
    from app.main import app

    with TestClient(app) as client:
        email = f"lang-{uuid.uuid4().hex[:8]}@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "LangTest123!", "displayName": "英文面试"},
        )
        token = reg.json()["data"]["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}
        scene = client.get("/api/v1/scenes?size=1", headers=headers).json()["data"][0]
        created = client.post(
            "/api/v1/training-sessions",
            json={"sceneId": scene["id"], "language": "en"},
            headers=headers,
        )
        assert created.status_code == 201
        assert created.json()["data"]["language"] == "en"

"""追问强度：会写进会话并体现在面试官提示里。"""

import uuid

from fastapi.testclient import TestClient

from app.features.training.graph import prompt_node


def _state(depth: str) -> dict:
    return {
        "round_no": 2,
        "max_rounds": 12,
        "user_text": "我做过订单系统优化。",
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
        "depth": depth,
        "planned_question": "",
        "prompt": "",
    }


def test_three_layer_prompt_mentions_layers() -> None:
    prompt = prompt_node(_state("THREE_LAYER"))["prompt"]
    assert "三层追问" in prompt
    assert "比较方案优劣" in prompt


def test_pressure_prompt_mentions_pressure() -> None:
    prompt = prompt_node(_state("PRESSURE"))["prompt"]
    assert "压力面" in prompt


def test_standard_prompt_has_no_depth_note() -> None:
    prompt = prompt_node(_state("STANDARD"))["prompt"]
    assert "压力面" not in prompt
    assert "三层追问" not in prompt


def test_create_session_persists_depth() -> None:
    from app.main import app

    with TestClient(app) as client:
        email = f"depth-{uuid.uuid4().hex[:8]}@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "DepthTest123!", "displayName": "追问强度", "consent": True},
        )
        token = reg.json()["data"]["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}
        scene = client.get("/api/v1/scenes?size=1", headers=headers).json()["data"][0]
        created = client.post(
            "/api/v1/training-sessions",
            json={"sceneId": scene["id"], "depth": "THREE_LAYER"},
            headers=headers,
        )
        assert created.status_code == 201
        assert created.json()["data"]["depth"] == "THREE_LAYER"

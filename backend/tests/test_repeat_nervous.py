"""再说一遍与安抚：不推进轮次，安抚写进提示词。"""

import uuid

from fastapi.testclient import TestClient

from app.features.training.graph import prompt_node
from app.features.training.service import is_nervous, is_repeat_request


def test_repeat_detection() -> None:
    assert is_repeat_request("能再说一遍吗？")
    assert is_repeat_request("抱歉没听清")
    assert is_repeat_request("Could you repeat that?")
    assert not is_repeat_request("我做过订单系统优化")


def test_nervous_detection() -> None:
    assert is_nervous("我有点紧张")
    assert is_nervous("I'm nervous")
    assert not is_nervous("我说完了")


def _prompt(nervous: bool) -> str:
    return prompt_node(
        {
            "round_no": 2,
            "max_rounds": 12,
            "user_text": "我有点紧张",
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
            "language": "zh",
            "nervous": nervous,
            "planned_question": "",
            "prompt": "",
        }
    )["prompt"]


def test_nervous_note_in_prompt() -> None:
    assert "安抚" in _prompt(True)
    assert "安抚" not in _prompt(False)


def test_repeat_does_not_advance_round() -> None:
    from app.main import app

    with TestClient(app) as client:
        email = f"repeat-{uuid.uuid4().hex[:8]}@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "RepeatTest123!", "displayName": "重复", "consent": True},
        )
        token = reg.json()["data"]["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}
        scene = client.get("/api/v1/scenes?size=1", headers=headers).json()["data"][0]
        created = client.post(
            "/api/v1/training-sessions", json={"sceneId": scene["id"]}, headers=headers
        ).json()["data"]

        repeated = client.post(
            f"/api/v1/training-sessions/{created['id']}/messages/complete",
            json={"content": "能再说一遍吗？"},
            headers=headers,
        )
        assert repeated.status_code == 200
        body = repeated.json()["data"]
        assert body["roundNo"] == 0
        assert "再说一遍" in body["content"]

        answered = client.post(
            f"/api/v1/training-sessions/{created['id']}/messages/complete",
            json={"content": "我有三段实习，主要做后端开发。"},
            headers=headers,
        )
        assert answered.status_code == 200
        assert answered.json()["data"]["roundNo"] == 1

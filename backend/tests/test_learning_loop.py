from importlib import import_module
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app


def finish_training(client: TestClient, headers: dict[str, str], scene_id: str, create_plan: bool) -> str:
    created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id})
    assert created.status_code == 201
    session_id = created.json()["data"]["id"]
    for index in range(6):
        response = client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete", headers=headers,
            json={"content": f"第{index + 1}轮：我的结论是先解决客户问题，依据是已有反馈，明天提交方案。"},
        )
        assert response.status_code == 200
    response = client.post(
        f"/api/v1/training-sessions/{session_id}/finish?create_plan={str(create_plan).lower()}", headers=headers,
    )
    assert response.status_code == 200
    return session_id


@pytest.mark.parametrize(
    ("retest_logic", "expected_status", "expected_delta"),
    [(4, "IMPROVED", 2), (2, "NEEDS_PRACTICE", 0), (None, "PROVISIONAL", 2)],
)
def test_plan_closes_with_foundation_scene_and_original_scene_retest(
    monkeypatch, retest_logic: int | None, expected_status: str, expected_delta: int,
) -> None:
    evaluation_count = 0

    async def fake_complete(system_prompt: str, _user_prompt: str, **_kwargs):
        nonlocal evaluation_count
        assert "评分员" in system_prompt, "new plans must not generate course or rewrite tasks"
        evaluation_count += 1
        if evaluation_count == 4 and retest_logic is None:
            raise TimeoutError("synthetic retest timeout")
        logic = 2 if evaluation_count == 1 else (retest_logic if evaluation_count == 4 else 3)
        return {
            "scores": {"logic": logic, "appropriateness": 4, "impact": 4, "relevance": 4, "concision": 4},
            "summary": "结论需要更明确，逐步补充依据。",
            "suggestions": [
                {"roundNo": 1, "problem": "结论不够靠前", "original": "我会处理", "rewrite": "我的结论是先处理客户问题。"},
                {"roundNo": 2, "problem": "缺少行动", "original": "再看看", "rewrite": "明天提交方案。"},
            ],
            "styleTags": ["务实"],
        }

    async def fake_stream(_system_prompt, _messages):
        yield "你能再解释一下依据和下一步安排吗？"

    async def no_model_limit(_user_id):
        return None

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    monkeypatch.setattr(llm_gateway, "stream_text", fake_stream)
    monkeypatch.setattr(import_module("app.features.training.router"), "limit_model_user", no_model_limit)

    with TestClient(app, client=(f"loop-{uuid4().hex}", 50000)) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": f"loop-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "闭环测试"},
        )
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        baseline_id = finish_training(client, headers, "scene-interview-03", True)
        plan = client.get("/api/v1/training-plans", headers=headers).json()["data"][0]
        plan_id = plan["id"]
        assert plan["focusDimension"] == "逻辑性"
        assert [(task["key"], task["actionType"]) for task in plan["tasks"]] == [
            ("practice", "TRAINING"), ("retest", "RETEST"),
        ]
        assert plan["tasks"][0]["sceneId"] == "scene-foundation-logic"
        assert plan["tasks"][1]["sceneId"] == "scene-interview-03"
        assert plan["tasks"][0]["sourceSessionId"] == baseline_id

        premature = client.post(
            f"/api/v1/training-plans/{plan_id}/tasks/practice/complete", headers=headers,
            json={"evidence": baseline_id},
        )
        assert premature.status_code == 422
        assert premature.json()["title"] == "SCENE_MISMATCH"

        wrong_id = finish_training(client, headers, "scene-interview-03", False)
        wrong = client.post(
            f"/api/v1/training-plans/{plan_id}/tasks/practice/complete", headers=headers,
            json={"evidence": wrong_id},
        )
        assert wrong.status_code == 422
        assert wrong.json()["title"] == "SCENE_MISMATCH"

        practice_id = finish_training(client, headers, "scene-foundation-logic", False)
        practiced = client.post(
            f"/api/v1/training-plans/{plan_id}/tasks/practice/complete", headers=headers,
            json={"evidence": practice_id},
        )
        assert practiced.status_code == 200
        assert practiced.json()["data"]["progress"] == 50

        retest_id = finish_training(client, headers, "scene-interview-03", False)
        completed = client.post(
            f"/api/v1/training-plans/{plan_id}/tasks/retest/complete", headers=headers,
            json={"evidence": retest_id},
        )
        assert completed.status_code == 200
        comparison = completed.json()["data"]["comparison"]
        assert completed.json()["data"]["progress"] == 100
        assert comparison["baselineSessionId"] == baseline_id
        assert comparison["retestSessionId"] == retest_id
        assert comparison["scoreDeltas"]["logic"] == expected_delta
        assert comparison["status"] == expected_status

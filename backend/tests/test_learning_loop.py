from importlib import import_module
from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app


PLAN_DRAFT = {
    "title": "逻辑性专项提升：先复盘再学微课",
    "lesson": {
        "title": "逻辑性微课",
        "intro": "用三个步骤让回答先有结论，再有依据，最后落到行动。",
        "steps": [
            {
                "title": "先给结论",
                "explanation": "开口第一句先说结论，让对方立刻知道你要回答什么。",
                "example": "我的结论是：先解决客户反馈的这个问题。",
            },
            {
                "title": "再给依据",
                "explanation": "用一条可核对的事实支撑结论，不堆形容词。",
                "example": "依据是本周三位客户都提到同一处报错。",
            },
            {
                "title": "落到行动",
                "explanation": "明确谁在什么时候做什么，避免空泛表态。",
                "example": "我今天下午提交方案，明天在群里同步结果。",
            },
        ],
        "exercise": "结合最近一次真实沟通，用上面三个方法重写一段至少 40 字的逻辑性表达。",
    },
    "practice_task": "回到逻辑性基础场景完成至少 6 轮对话，重点练习结论先行。",
    "rewrite_task": "对照逐轮批注，挑选问题最大的回答重新组织表达。",
    "retest_task": "回到原场景完成新一轮训练，对比逻辑性评分变化。",
}


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


def test_plan_is_review_then_lesson_and_closes(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, _user_prompt: str, **_kwargs):
        if "两步训练计划" in system_prompt or "微型训练计划" in system_prompt:
            return PLAN_DRAFT
        if "微课教练" in system_prompt:
            return {"passed": True, "feedback": "回答具体，包含了课程方法与明确行动。"}
        if "改写教练" in system_prompt:
            return {"passed": True, "feedback": "改写回应了原问题。"}
        assert "评分员" in system_prompt
        return {
            "scores": {"logic": 2, "appropriateness": 4, "impact": 4, "relevance": 4, "concision": 4},
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
            ("course", "COURSE"),
        ]
        assert plan["tasks"][0]["lesson"]["steps"][0]["title"] == "先给结论"

        for index in range(3):
            step = client.post(
                f"/api/v1/training-plans/{plan_id}/tasks/course/steps/{index}/complete", headers=headers,
            )
            assert step.status_code == 200

        answered = client.post(
            f"/api/v1/training-plans/{plan_id}/tasks/course/practice", headers=headers,
            json={"answer": "我的结论是先处理客户反馈的问题，依据是本周三位客户都提到同一处报错，我今天下午提交修复方案并同步结果。"},
        )
        assert answered.status_code == 200
        data = answered.json()["data"]
        assert data["progress"] == 100
        assert data["status"] == "COMPLETED"
        assert data["tasks"][0]["practicePassed"] is True

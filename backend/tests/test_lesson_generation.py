from importlib import import_module
from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app

ANSWER = "我的结论是先解决客户问题，依据是本周三位客户反馈同一处报错，明天提交方案。"

LESSON_JSON = {
    "title": "把结论说在别人听得懂的次序里",
    "intro": "你这次逻辑性 2 分，问题不在没内容，而在先讲过程、后说结论。",
    "steps": [
        {"title": "先给结论", "explanation": "开口第一句就把结论放出来，让对方知道要听什么。", "example": "我建议先修数据一致性。"},
        {"title": "补一条依据", "explanation": "紧跟一句可核对的事实，不要用形容词。", "example": "本周有 12 笔订单对账不平。"},
        {"title": "给下一步", "explanation": "最后说清你准备做什么、什么时候回。", "example": "我今天下午提交修复，明天同步结果。"},
    ],
    "exercise": "用你自己的项目，按结论-依据-下一步重写一段 40 字以上的回答。",
}

PLAN_JSON = {
    "title": "逻辑性提升计划",
    "lesson": LESSON_JSON,
    "practice_task": "回到原场景再练一次",
    "rewrite_task": "改写两段薄弱回答",
    "retest_task": "再次训练并对比评分",
}


CHOSEN_COURSE_ID = {"value": None}


def _fake_llm(monkeypatch):
    async def fake_complete(system_prompt: str, _user_prompt: str, **_kwargs):
        if "课件素材" in system_prompt:
            payload = dict(LESSON_JSON)
            if CHOSEN_COURSE_ID["value"]:
                payload["courseId"] = CHOSEN_COURSE_ID["value"]
            return payload
        if "提升计划" in system_prompt:
            return PLAN_JSON
        if "评分员" in system_prompt:
            return {
                "scores": {"logic": 2, "appropriateness": 3, "correctness": 3, "relevance": 3, "concision": 4},
                "summary": "结论清楚，依据偏薄。",
                "suggestions": [
                    {
                        "roundNo": 1,
                        "problem": "缺少可核对的数据",
                        "original": ANSWER,
                        "rewrite": "本周三位客户反馈同一处报错。",
                        "reference": "本周三位客户反馈同一处报错，我今天下午提交修复方案。",
                    }
                ],
                "styleTags": ["务实"],
                "evidence": [
                    {
                        "dimension": "logic",
                        "roundNo": 1,
                        "quote": ANSWER,
                        "reason": "只有结论，缺少依据。",
                        "nextAction": "每轮补一条可核对的事实。",
                        "resumeQuote": None,
                    }
                ],
            }
        return {"scores": {"logic": 3, "appropriateness": 3, "correctness": 3, "relevance": 3, "concision": 3},
                "summary": "ok", "suggestions": [], "styleTags": [], "evidence": []}

    async def fake_stream(_system_prompt, _messages):
        yield "好的，请继续。"

    async def no_limit(_user_id):
        return None

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    monkeypatch.setattr(llm_gateway, "stream_text", fake_stream)
    monkeypatch.setattr(import_module("app.features.training.router"), "limit_model_user", no_limit)


def test_lesson_generated_on_demand(monkeypatch) -> None:
    _fake_llm(monkeypatch)
    with TestClient(app, client=(f"ls-{uuid4().hex}", 50000)) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"ls-{uuid4().hex[:8]}@example.com",
                "password": "GraduateDesign123!",
                "displayName": "微课测试",
                "consent": True,
            },
        )
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": "scene-interview-03"})
        session_id = created.json()["data"]["id"]
        for _ in range(3):
            client.post(
                f"/api/v1/training-sessions/{session_id}/messages/complete",
                headers=headers,
                json={"content": ANSWER},
            )
        finished = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert finished.status_code == 200

        plans = client.get("/api/v1/training-plans", headers=headers).json()["data"]
        assert plans, "结束训练后应生成计划"
        plan_id = plans[0]["id"]

        lesson = client.post(
            f"/api/v1/training-plans/{plan_id}/lesson",
            headers=headers,
            json={"task_key": "course"},
        )
        assert lesson.status_code == 200, lesson.text
        data = lesson.json()["data"]
        assert data["lesson"]["aiGenerated"] is True
        assert len(data["lesson"]["steps"]) == 3
        assert data["lesson"]["intro"]
        assert data["source"]["title"]

        admin = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "Admin123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin.json()['data']['accessToken']}"}
        focus = plans[0]["focusDimension"]
        created_course = client.post(
            "/api/v1/admin/courses",
            headers=admin_headers,
            json={
                "title": "把薪资谈判讲成价值对话",
                "dimension": focus,
                "minutes": 18,
                "description": "适用于薪资、涨幅等需要说服对方的场景。",
                "content": "先锚定关切；用事实替代形容词；给区间不给单点；说明下一步。",
                "active": True,
            },
        )
        assert created_course.status_code in (200, 201), created_course.text
        course_id = created_course.json()["data"]["id"]
        CHOSEN_COURSE_ID["value"] = course_id

        swapped = client.post(
            f"/api/v1/training-plans/{plan_id}/lesson",
            headers=headers,
            json={"task_key": "course", "force": True},
        )
        assert swapped.status_code == 200, swapped.text
        assert swapped.json()["data"]["source"]["id"] == course_id

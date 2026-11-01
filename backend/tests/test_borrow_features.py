from importlib import import_module
from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app

ANSWER = "我的结论是先解决客户问题，依据是已有反馈，明天提交方案。"


def _fake_llm(monkeypatch):
    async def fake_complete(system_prompt: str, user_prompt: str, **_kwargs):
        if "面试出题策划" in system_prompt:
            return {
                "plan": [
                    {"text": "请说明你如何定位这个岗位的核心职责", "dimension": "针对性", "difficulty": "中级"},
                    {"text": "讲一个你主导的跨团队协作案例", "dimension": "逻辑性", "difficulty": "中级"},
                    {"text": "如果资源不足你会怎么取舍", "dimension": "逻辑性", "difficulty": "进阶"},
                ]
            }
        if "评分员" in system_prompt:
            return {
                "scores": {"logic": 2, "appropriateness": 3, "correctness": 3, "relevance": 3, "concision": 4},
                "summary": "结论清楚，但依据偏薄。",
                "suggestions": [
                    {
                        "roundNo": 1,
                        "problem": "只给了结论，没有可核对的数据",
                        "original": ANSWER,
                        "rewrite": "我的结论是先解决客户问题，依据是本周三位客户反馈同一处报错。",
                        "reference": "我的结论是先解决客户反馈的问题：本周三位客户提到同一处报错，我今天下午提交修复方案，明天同步结果。",
                    }
                ],
                "styleTags": ["务实"],
                "evidence": [
                    {
                        "dimension": "logic",
                        "roundNo": 1,
                        "quote": ANSWER,
                        "reason": "只有结论和行动，缺少可核对的依据。",
                        "nextAction": "每轮补一条可核对的事实。",
                        "resumeQuote": None,
                    }
                ],
            }
        return {"scores": {"logic": 3, "appropriateness": 3, "correctness": 3, "relevance": 3, "concision": 3},
                "summary": "ok", "suggestions": [], "styleTags": [], "evidence": []}

        if "改写" in system_prompt:
            return {"rewrite": "我希望今天下午能拿到答复，方便安排后续。", "reason": "改成可协商的语气。"}
        if "评分员" in system_prompt:
            return {
                "scores": {"logic": 2, "appropriateness": 3, "correctness": 3, "relevance": 3, "concision": 4},
                "summary": "结论清楚，但依据偏薄。",
                "suggestions": [
                    {
                        "roundNo": 1,
                        "problem": "只给了结论，没有可核对的数据",
                        "original": ANSWER,
                        "rewrite": "我的结论是先解决客户问题，依据是本周三位客户反馈同一处报错。",
                        "reference": "我的结论是先解决客户反馈的问题：本周三位客户提到同一处报错，我今天下午提交修复方案，明天同步结果。",
                    }
                ],
                "styleTags": ["务实"],
                "evidence": [
                    {
                        "dimension": "logic",
                        "roundNo": 1,
                        "quote": ANSWER,
                        "reason": "只有结论和行动，缺少可核对的依据。",
                        "nextAction": "每轮补一条可核对的事实。",
                        "resumeQuote": None,
                    }
                ],
            }
        return {"scores": {"logic": 3, "appropriateness": 3, "correctness": 3, "relevance": 3, "concision": 3},
                "summary": "ok", "suggestions": [], "styleTags": [], "evidence": []}

    async def fake_stream(_system_prompt, _messages):
        yield "我理解了，请继续说明你的依据。"

    async def no_limit(_user_id):
        return None

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    monkeypatch.setattr(llm_gateway, "stream_text", fake_stream)
    monkeypatch.setattr(import_module("app.features.training.router"), "limit_model_user", no_limit)


def _login(client: TestClient) -> dict[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"br-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!",
            "displayName": "借鉴测试",
        },
    )
    return {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}


def test_job_description_builds_question_plan(monkeypatch) -> None:
    _fake_llm(monkeypatch)
    with TestClient(app, client=(f"jd-{uuid4().hex}", 50000)) as client:
        headers = _login(client)
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": "scene-interview-03"})
        session_id = created.json()["data"]["id"]

        jd = client.post(
            f"/api/v1/training-sessions/{session_id}/jd",
            headers=headers,
            json={"jd_text": "岗位职责：负责后端服务的设计与稳定性，要求熟悉 Python 与高并发场景。"},
        )
        assert jd.status_code == 200
        data = jd.json()["data"]
        assert data["jdText"]
        assert data["questionTotal"] == 3
        assert data["questionCovered"] == 0

        client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=headers,
            json={"content": ANSWER},
        )
        after = client.get(f"/api/v1/training-sessions/{session_id}", headers=headers).json()["data"]
        assert after["questionCovered"] == 1

        cleared = client.delete(f"/api/v1/training-sessions/{session_id}/jd", headers=headers)
        assert cleared.status_code == 200
        assert cleared.json()["data"]["jdText"] is None


def test_report_exposes_speech_stats_and_mistakes(monkeypatch) -> None:
    _fake_llm(monkeypatch)
    with TestClient(app, client=(f"mk-{uuid4().hex}", 50000)) as client:
        headers = _login(client)
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": "scene-interview-03"})
        session_id = created.json()["data"]["id"]
        for _ in range(3):
            client.post(
                f"/api/v1/training-sessions/{session_id}/messages/complete",
                headers=headers,
                json={"content": ANSWER + "然后就是按计划推进。"},
            )
        finished = client.post(f"/api/v1/training-sessions/{session_id}/finish?create_plan=false", headers=headers)
        assert finished.status_code == 200

        evaluation = client.get(f"/api/v1/evaluations/{session_id}", headers=headers).json()["data"]
        stats = evaluation["speechStats"]
        assert stats["rounds"] == 3
        assert stats["fillerTotal"] >= 2  # “然后”“就是”
        assert stats["topFillers"][0]["count"] >= 1

        mistakes = client.get("/api/v1/training-sessions/mistakes?size=50", headers=headers).json()["data"]["items"]
        assert mistakes, "低分轮次应进入错题本"
        first = mistakes[0]
        assert first["dimension"] == "逻辑性"
        assert first["score"] == 2
        assert first["quote"]
        assert first["status"] == "PENDING"
        assert first["generatedCount"] == 0


def test_mistake_generation_and_status(monkeypatch) -> None:
    _fake_llm(monkeypatch)
    with TestClient(app, client=(f"mg-{uuid4().hex}", 50000)) as client:
        headers = _login(client)
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": "scene-interview-03"})
        session_id = created.json()["data"]["id"]
        for _ in range(3):
            client.post(
                f"/api/v1/training-sessions/{session_id}/messages/complete",
                headers=headers,
                json={"content": ANSWER + "然后就是按计划推进。"},
            )
        client.post(f"/api/v1/training-sessions/{session_id}/finish?create_plan=false", headers=headers)

        mistakes = client.get("/api/v1/training-sessions/mistakes?size=50", headers=headers).json()["data"]["items"]
        assert mistakes
        item = mistakes[0]
        assert item["status"] == "PENDING"
        assert item["generatedCount"] == 0
        assert "reference" not in item
        assert item["sceneId"]

        generated = client.post(
            "/api/v1/scripts/generate",
            headers=headers,
            json={
                "sceneId": item["sceneId"],
                "objective": "改进逻辑性",
                "originalText": item["quote"],
                "dimension": item["dimension"],
                "sourceSessionId": item["sessionId"],
                "sourceRound": item["roundNo"],
            },
        )
        assert generated.status_code == 201
        versions = generated.json()["data"]["versions"]
        assert len(versions) == 3
        assert versions[0]["dimension"] == item["dimension"]
        assert versions[0]["sourceSessionId"] == item["sessionId"]

        after = client.get("/api/v1/training-sessions/mistakes", headers=headers).json()["data"]["items"]
        assert after[0]["generatedCount"] == 3

        blocked = client.patch(
            "/api/v1/training-sessions/mistakes/state",
            headers=headers,
            json={
                "sessionId": item["sessionId"],
                "roundNo": item["roundNo"],
                "dimension": item["dimension"],
                "status": "RESOLVED",
            },
        )
        assert blocked.status_code == 422
        assert blocked.json()["title"] == "PRACTICE_REQUIRED"

        retry = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": "scene-interview-03"})
        retry_id = retry.json()["data"]["id"]
        for _ in range(3):
            client.post(
                f"/api/v1/training-sessions/{retry_id}/messages/complete",
                headers=headers,
                json={"content": ANSWER + "然后就是按计划推进。"},
            )
        client.post(f"/api/v1/training-sessions/{retry_id}/finish?create_plan=false", headers=headers)

        patched = client.patch(
            "/api/v1/training-sessions/mistakes/state",
            headers=headers,
            json={
                "sessionId": item["sessionId"],
                "roundNo": item["roundNo"],
                "dimension": item["dimension"],
                "status": "RESOLVED",
            },
        )
        assert patched.status_code == 200, patched.text
        resolved = client.get("/api/v1/training-sessions/mistakes?include_resolved=true&size=50", headers=headers).json()["data"]["items"]
        match = next(
            (row for row in resolved
             if row["sessionId"] == item["sessionId"] and row["roundNo"] == item["roundNo"]
             and row["dimension"] == item["dimension"]),
            None,
        )
        assert match and match["status"] == "RESOLVED"

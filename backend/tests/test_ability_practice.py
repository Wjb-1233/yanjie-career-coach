from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app


def test_weakest_dimension_practice_uses_real_answer_and_persists_feedback(monkeypatch) -> None:
    feedback_quote = {"value": "我先比较了两个方案", "quota": False}

    async def fake_complete(system_prompt: str, _user_prompt: str, **_kwargs):
        if "评分员" in system_prompt:
            return {
                "scores": {"logic": 2, "appropriateness": 4, "impact": 3, "relevance": 4, "concision": 4},
                "summary": "需要解释做法和结果。",
                "suggestions": [{"roundNo": 1, "problem": "理由不足", "original": "我负责接口开发", "rewrite": "我负责接口开发，并说明方案选择。"}],
                "styleTags": ["缺少依据"],
                "evidence": [{"dimension": "logic", "roundNo": 1, "quote": "我负责接口开发", "reason": "只讲职责，缺少依据。", "nextAction": "解释方案选择和结果。"}],
            }
        assert "能力教练" in system_prompt
        if feedback_quote["quota"]:
            request = httpx.Request("POST", "https://example.invalid/chat/completions")
            response = httpx.Response(402, request=request)
            raise httpx.HTTPStatusError("quota exhausted", request=request, response=response)
        return {
            "score": 4,
            "answerQuote": feedback_quote["value"],
            "strength": "说明了方案选择的过程。",
            "gap": "结果还不够具体。",
            "nextAction": "补充真实的验证结果。",
        }

    async def fake_stream(_system_prompt, _messages):
        yield "请继续介绍验证过程。"

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    monkeypatch.setattr(llm_gateway, "stream_text", fake_stream)

    with TestClient(app, client=(f"ability-{uuid4().hex}", 50000)) as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": f"ability-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!",
            "displayName": "能力练习测试",
        })
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        assert client.get("/api/v1/ability/current").status_code == 401
        assert client.get("/api/v1/ability/current", headers=headers).json()["data"] is None

        scene_id = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        session_id = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id}).json()["data"]["id"]
        for answer in ("我负责接口开发，并处理接口超时。", "我用压测验证了接口性能，并修改缓存策略。"):
            assert client.post(f"/api/v1/training-sessions/{session_id}/messages", headers=headers, json={"content": answer}).status_code == 200
        assert client.post(f"/api/v1/training-sessions/{session_id}/finish?create_plan=false", headers=headers).status_code == 200

        current = client.get("/api/v1/ability/current", headers=headers).json()["data"]
        assert current["dimension"] == "logic"
        assert current["baselineScore"] == 2
        assert current["sessionId"] == session_id
        assert current["sceneId"] == scene_id
        assert current["roundCount"] == 2
        assert len(current["reviewTurns"]) == 2
        assert current["reviewTurns"][0]["answer"] == "我负责接口开发，并处理接口超时。"
        assert current["reviewTurns"][0]["isFocusEvidence"] is True
        assert current["reportSummary"]
        assert current["reportSuggestions"]
        assert current["evidenceQuote"] == "我负责接口开发"
        assert current["evidenceQuote"] in current["originalAnswer"]
        assert current["question"]
        assert current["attempts"] == []

        answer = "我先比较了两个方案，再用压测验证接口性能，最终调整了缓存策略。"
        created = client.post("/api/v1/ability/attempts", headers=headers, json={"evaluationId": current["evaluationId"], "answer": answer})
        assert created.status_code == 201
        result = created.json()["data"]
        assert result["score"] == 4
        assert result["answerQuote"] in result["answer"]
        assert client.get("/api/v1/ability/current", headers=headers).json()["data"]["attempts"][0]["id"] == result["id"]
        assert client.post("/api/v1/ability/attempts", headers=headers, json={"evaluationId": str(uuid4()), "answer": answer}).status_code == 409
        feedback_quote["value"] = "这是模型编造的原句"
        rejected = client.post("/api/v1/ability/attempts", headers=headers, json={"evaluationId": current["evaluationId"], "answer": answer})
        assert rejected.status_code == 503
        assert len(client.get("/api/v1/ability/current", headers=headers).json()["data"]["attempts"]) == 1
        feedback_quote["quota"] = True
        quota_error = client.post("/api/v1/ability/attempts", headers=headers, json={"evaluationId": current["evaluationId"], "answer": answer})
        assert quota_error.status_code == 503
        assert "余额不足" in quota_error.json()["detail"]

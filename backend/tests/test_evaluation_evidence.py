from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app


def test_report_keeps_only_verifiable_score_evidence(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, _user_prompt: str, **_kwargs):
        if "评分员" not in system_prompt:
            raise AssertionError("unexpected model call")
        return {
            "scores": {"logic": 2, "appropriateness": 4, "impact": 3, "relevance": 3, "concision": 4},
            "summary": "结论尚可，依据不足。",
            "suggestions": [{"roundNo": 1, "problem": "依据不具体", "original": "我负责接口开发", "rewrite": "我负责接口开发，并通过压测验证性能。"}],
            "styleTags": ["待补证据"],
            "evidence": [
                {"dimension": "logic", "roundNo": 1, "quote": "我负责接口开发", "reason": "有职责但缺乏推理依据。", "nextAction": "补充技术选择的理由。"},
                {"dimension": "impact", "roundNo": 2, "quote": "我负责接口开发", "reason": "错轮引用。", "nextAction": "补充数据。"},
                {"dimension": "relevance", "roundNo": 1, "quote": "从未说过的话", "reason": "伪造引用。", "nextAction": "正面回答。"},
                {"dimension": "concision", "roundNo": 2, "quote": "我用压测结果验证了性能", "reason": "表达较为集中。", "nextAction": "用一句话先讲结论。"},
            ],
        }

    async def fake_stream(_system_prompt, _messages):
        yield "你能进一步解释做法吗？"

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    monkeypatch.setattr(llm_gateway, "stream_text", fake_stream)

    with TestClient(app, client=(f"evidence-{uuid4().hex}", 50000)) as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": f"evidence-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!",
            "displayName": "证据测试",
        })
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        scene_id = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id})
        session_id = created.json()["data"]["id"]
        opening_id = created.json()["data"]["messages"][0]["id"]
        for content in ("我负责接口开发，并解决了超时问题。", "我用压测结果验证了性能，并调整缓存策略。"):
            response = client.post(f"/api/v1/training-sessions/{session_id}/messages", headers=headers, json={"content": content})
            assert response.status_code == 200
            assert "event: done" in response.text
        transcript = client.get(f"/api/v1/training-sessions/{session_id}", headers=headers).json()["data"]["messages"]
        answer_one = next(item for item in transcript if item["speaker"] == "USER" and item["roundNo"] == 1)

        finished = client.post(f"/api/v1/training-sessions/{session_id}/finish?create_plan=false", headers=headers)
        assert finished.status_code == 200
        report = finished.json()["data"]
        assert report["planId"] is None
        assert {item["dimension"] for item in report["evidence"]} == {"logic", "concision"}
        logic = next(item for item in report["evidence"] if item["dimension"] == "logic")
        assert logic["questionMessageId"] == opening_id
        assert logic["answerMessageId"] == answer_one["id"]
        assert logic["quote"] in logic["answer"]
        assert logic["resumeQuote"] is None
        reopened = client.get(f"/api/v1/evaluations/{session_id}", headers=headers)
        assert reopened.status_code == 200
        assert reopened.json()["data"]["evidence"] == report["evidence"]

        removed = client.delete(f"/api/v1/training-sessions/{session_id}", headers=headers)
        assert removed.status_code == 204
        assert client.get(f"/api/v1/evaluations/{session_id}", headers=headers).status_code == 404


def test_evidence_validator_requires_resume_quote_to_exist_in_resume() -> None:
    from app.db.models import Message
    from app.features.evaluations.service import validated_evidence

    question = Message(id="question", round_no=0, speaker="AI", content="请介绍项目。")
    answer = Message(id="answer", round_no=1, speaker="USER", content="我用 Python 做接口开发。")
    draft = {"dimension": "logic", "roundNo": 1, "quote": "我用 Python", "reason": "回答包含具体技术。", "nextAction": "解释选择理由。", "resumeQuote": "简历里不存在的项目"}
    result = validated_evidence([draft], [question, answer], "真实简历：Python 接口项目")
    assert len(result) == 1
    assert result[0].resume_quote is None

    question.content = "简历写到 Python 接口项目，请介绍技术选择。"
    draft["resumeQuote"] = "Python 接口项目"
    linked = validated_evidence([draft], [question, answer], "真实简历：Python 接口项目")
    assert linked[0].resume_quote == "Python 接口项目"

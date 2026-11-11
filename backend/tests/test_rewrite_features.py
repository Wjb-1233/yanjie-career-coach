from importlib import import_module
from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app


def _register(client: TestClient) -> dict[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"rw-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!",
            "displayName": "改写测试",
            "consent": True,
        },
    )
    return {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}


def test_flagged_message_returns_targeted_rewrite(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, user_prompt: str, **_kwargs):
        if "改写" in system_prompt:
            return {"rewrite": "我希望今天下午能拿到明确答复，方便安排后续安排。", "reason": "把命令口吻改成可协商的请求。"}
        if "四步微型训练计划" in system_prompt or "两步训练计划" in system_prompt:
            return {"title": "逻辑性提升计划", "lesson": {"title": "课", "intro": "x", "steps": [], "exercise": "x"},
                    "practiceTask": "p", "rewriteTask": "r", "retestTask": "t"}
        return {
            "scores": {"logic": 3, "appropriateness": 3, "correctness": 3, "relevance": 3, "concision": 3},
            "summary": "表达直接，但语气偏硬。",
            "suggestions": [],
            "styleTags": ["直接"],
        }

    async def fake_stream(_system_prompt, _messages):
        yield "好的，我记下了。"

    async def no_limit(_user_id):
        return None

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    monkeypatch.setattr(llm_gateway, "stream_text", fake_stream)
    monkeypatch.setattr(import_module("app.features.training.router"), "limit_model_user", no_limit)

    with TestClient(app, client=(f"rw-{uuid4().hex}", 50000)) as client:
        headers = _register(client)
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": "scene-interview-03"})
        session_id = created.json()["data"]["id"]

        first = client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=headers,
            json={"content": "你必须今天下午就给我答复，少废话。"},
        )
        assert first.status_code == 200
        assert first.json()["data"]["flags"], "命中风险标签的句子应当被打上标记"

        rewrite = client.post(
            f"/api/v1/training-sessions/{session_id}/messages/1/rewrite", headers=headers,
        )
        assert rewrite.status_code == 200
        data = rewrite.json()["data"]
        assert data["original"].startswith("你必须")
        assert data["rewrite"] != data["original"]
        assert data["reason"]
        assert data["flags"]

        # 未被标记的轮次不提供改写
        client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=headers,
            json={"content": "我理解这个问题，可以按步骤说明我的做法。"},
        )
        plain = client.post(
            f"/api/v1/training-sessions/{session_id}/messages/2/rewrite", headers=headers,
        )
        assert plain.status_code == 422
        assert plain.json()["title"] == "NO_RISK_FLAG"


def test_script_versions_keep_original_for_diff(monkeypatch) -> None:
    async def fake_complete(_system_prompt: str, _user_prompt: str, **_kwargs):
        return {
            "versions": [
                {"style": "正式", "content": "我负责了其中的接口设计部分。", "highlights": ["结构清晰"]},
                {"style": "亲和", "content": "这块主要是我在跟进的。", "highlights": ["语气自然"]},
                {"style": "简洁", "content": "我负责接口设计。", "highlights": ["简短"]},
            ],
            "coachNote": "对比语气与信息量。",
        }

    async def no_limit(_user_id):
        return None

    monkeypatch.setattr(type(llm_gateway), "configured", property(lambda self: True))
    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)
    monkeypatch.setattr(import_module("app.features.scripts.router"), "limit_model_user", no_limit)

    with TestClient(app, client=(f"sc-{uuid4().hex}", 50000)) as client:
        headers = _register(client)
        generated = client.post(
            "/api/v1/scripts/generate",
            headers=headers,
            json={"sceneId": "scene-interview-03", "objective": "说明项目职责", "originalText": "我负责所有"},
        )
        assert generated.status_code == 201
        versions = generated.json()["data"]["versions"]
        assert len(versions) == 3
        assert all(version["original"] == "我负责所有" for version in versions)

"""流程回归：视频任务先结束会话再评分、计划任务不再派生新计划、降级报告可重算。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app


PLAN_DRAFT = {
    "title": "内容整理提升计划",
    "lesson": {
        "title": "结论先行微课",
        "intro": "三个步骤把话说清。",
        "steps": [
            {"title": "先说结论", "explanation": "第一句给结论。", "example": "我的结论是先修数据。"},
            {"title": "再补依据", "explanation": "给一条可核对事实。", "example": "本周三位客户反馈同一处报错。"},
            {"title": "落到行动", "explanation": "说清谁何时做什么。", "example": "今天提交方案，明早同步。"},
        ],
        "exercise": "重写一段至少 40 字的表达。",
    },
    "practice_task": "重写一段回答。",
    "rewrite_task": "把原回答改写成完整版本。",
    "retest_task": "同场景再练一轮并对比分数。",
}

GOOD_SCORE = {
    "scores": {"logic": 3, "correctness": 3, "relevance": 3, "concision": 3},
    "summary": "结构完整。",
    "suggestions": [],
    "styleTags": ["稳健"],
}


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "流程"},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _train(client: TestClient, headers: dict[str, str], scene_id: str, rounds: int = 2, plan: bool = True) -> str:
    session_id = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id}).json()["data"]["id"]
    for index in range(rounds):
        client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=headers,
            json={"content": f"第{index + 1}轮：结论、依据、行动都说清楚。"},
        )
    response = client.post(
        f"/api/v1/training-sessions/{session_id}/finish?create_plan={'true' if plan else 'false'}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return session_id


def test_plan_task_session_does_not_create_another_plan(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, _user: str, **_kwargs):
        if "提升计划" in system_prompt:
            return PLAN_DRAFT
        return GOOD_SCORE

    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)

    with TestClient(app, client=(f"chain-{uuid4().hex}", 50030)) as client:
        headers = _register(client, "chain")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        _train(client, headers, scene)
        plan = client.get("/api/v1/training-plans", headers=headers).json()["data"][0]
        task = next(item for item in plan["tasks"] if item["actionType"] == "SCENE")

        started = client.post(
            "/api/v1/training-sessions",
            headers=headers,
            json={"sceneId": task["sceneId"], "planId": plan["id"], "taskKey": task["key"]},
        ).json()["data"]["id"]
        for index in range(6):
            client.post(
                f"/api/v1/training-sessions/{started}/messages/complete",
                headers=headers,
                json={"content": f"第{index + 1}轮：结论、依据、行动。"},
            )
        finished = client.post(f"/api/v1/training-sessions/{started}/finish", headers=headers)
        assert finished.status_code == 200, finished.text

        plans = client.get("/api/v1/training-plans", headers=headers).json()["data"]
        assert len(plans) == 1, "计划任务里的训练不应再派生新计划"


def test_degraded_evaluation_can_be_rescored(monkeypatch) -> None:
    calls = {"count": 0}

    async def flaky(system_prompt: str, _user: str, **_kwargs):
        calls["count"] += 1
        # 第一次评分时模型不可用，之后恢复正常
        if calls["count"] <= 3:
            raise TimeoutError("synthetic outage")
        if "提升计划" in system_prompt:
            return PLAN_DRAFT
        return GOOD_SCORE

    monkeypatch.setattr(llm_gateway, "complete_json", flaky)

    with TestClient(app, client=(f"rescore-{uuid4().hex}", 50031)) as client:
        headers = _register(client, "rescore")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        session_id = _train(client, headers, scene, plan=False)

        degraded = client.get(f"/api/v1/evaluations/{session_id}", headers=headers).json()["data"]
        assert degraded["degraded"] is True

        rescored = client.post(f"/api/v1/evaluations/{session_id}?force=true", headers=headers)
        assert rescored.status_code == 201, rescored.text
        assert rescored.json()["data"]["degraded"] is False


def test_video_task_finishes_session_before_scoring(monkeypatch) -> None:
    """视频任务必须先把会话标记 FINISHED，再走评分，否则报告永远 404。"""
    order: list[str] = []

    from app.features.tasks import service as task_service

    async def fake_update(*_args, **_kwargs):
        return None

    monkeypatch.setattr(task_service, "_update", fake_update)

    from app.features.evaluations import delivery as delivery_module
    from app.features.evaluations import service as evaluation_service
    from app.features.training import service as training_service
    from app.features.video import metrics as metrics_module

    monkeypatch.setattr(delivery_module, "analyze", lambda _path: {"words": [{"text": "我", "start": 0}, {"text": "可以", "start": 1}]})
    monkeypatch.setattr(metrics_module, "analyze_video", lambda _path: {"tips": []})

    async def fake_create_voice_session(*_args, **_kwargs):
        return "session-fake"

    monkeypatch.setattr(
        "app.features.voice.session.create_voice_session", fake_create_voice_session
    )

    async def fake_finish(_session, _user, _sid):
        order.append("finish")

    async def fake_evaluate(_session, _user, _sid, **_kwargs):
        order.append("evaluate")

    monkeypatch.setattr(training_service, "finish_session", fake_finish)
    monkeypatch.setattr(evaluation_service, "evaluate_session", fake_evaluate)

    task = SimpleNamespace(
        id="task-fake",
        user_id="user-fake",
        payload={"recording": "fake.webm", "questions": [{"text": "问题", "start": 0, "end": 5}], "sceneId": "scene-x"},
    )

    import asyncio

    original_path_of = None
    from app.features.recordings import storage

    original_path_of = storage.path_of
    monkeypatch.setattr(storage, "path_of", lambda _name: __import__("pathlib").Path(__file__))
    try:
        asyncio.run(task_service.process_video_interview(task))
    finally:
        if original_path_of:
            monkeypatch.setattr(storage, "path_of", original_path_of)

    assert order == ["finish", "evaluate"], f"调用顺序错误: {order}"

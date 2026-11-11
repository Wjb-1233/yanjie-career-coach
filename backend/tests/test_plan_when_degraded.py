"""降级（模型不可用）时仍必须产出训练计划：守护「能力提升」主线不断。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app
from tests.plan_task_helper import add_scene_task


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!",
            "displayName": "降级计划",
            "consent": True,
        },
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _run_rounds(client: TestClient, headers: dict[str, str], session_id: str, rounds: int) -> None:
    for index in range(rounds):
        replied = client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=headers,
            json={"content": f"第{index + 1}轮：我先给结论，再补一条可核对依据，最后说明下一步。"},
        )
        assert replied.status_code == 200, replied.text


def _break_model(monkeypatch) -> None:
    async def unavailable(*_args, **_kwargs):
        raise TimeoutError("model down")

    monkeypatch.setattr(llm_gateway, "complete_json", unavailable)


def test_degraded_finish_returns_fallback_plan(monkeypatch) -> None:
    _break_model(monkeypatch)

    with TestClient(app, client=(f"degraded-plan-{uuid4().hex}", 50081)) as client:
        headers = _register(client, "degradedplan")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        session_id = client.post(
            "/api/v1/training-sessions", headers=headers, json={"sceneId": scene}
        ).json()["data"]["id"]
        _run_rounds(client, headers, session_id, 2)

        finished = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert finished.status_code == 200, finished.text
        report = finished.json()["data"]
        assert report["degraded"] is True
        assert report["planId"], "降级评分也必须返回 planId，否则报告页没有「能力提升」入口"

        plans = client.get("/api/v1/training-plans", headers=headers).json()["data"]
        assert len(plans) == 1, "降级评分应产出 1 份兜底计划"
        plan = plans[0]
        assert plan["id"] == report["planId"]
        assert plan["sequence"] == 1

        # 文字会话的任务组合：本场复盘 + 改写 + 微课
        keys = [task["key"] for task in plan["tasks"]]
        assert keys == ["session-review", "rewrite", "course"], keys
        assert [task["actionType"] for task in plan["tasks"]] == ["REPORT", "REWRITE", "COURSE"]
        assert all(task["sourceSessionId"] == session_id for task in plan["tasks"])

        # 兜底文案必须让用户看出这是离线示例，不是模型个性化结果
        course = next(task for task in plan["tasks"] if task["key"] == "course")
        assert "离线示例内容" in course["lesson"]["intro"], course["lesson"]["intro"]
        assert len(course["lesson"]["steps"]) == 3


def test_repeated_finish_keeps_single_plan_when_degraded(monkeypatch) -> None:
    _break_model(monkeypatch)

    with TestClient(app, client=(f"degraded-twice-{uuid4().hex}", 50082)) as client:
        headers = _register(client, "degradedtwice")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        session_id = client.post(
            "/api/v1/training-sessions", headers=headers, json={"sceneId": scene}
        ).json()["data"]["id"]
        _run_rounds(client, headers, session_id, 2)

        first = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        again = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert first.status_code == again.status_code == 200
        assert again.json()["data"]["planId"] == first.json()["data"]["planId"]

        plans = client.get("/api/v1/training-plans", headers=headers).json()["data"]
        assert len(plans) == 1, "重复 finish 不应生成第二份计划"


def test_degraded_plan_session_does_not_spawn_another_plan(monkeypatch) -> None:
    _break_model(monkeypatch)

    with TestClient(app, client=(f"degraded-chain-{uuid4().hex}", 50083)) as client:
        headers = _register(client, "degradedchain")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        session_id = client.post(
            "/api/v1/training-sessions", headers=headers, json={"sceneId": scene}
        ).json()["data"]["id"]
        _run_rounds(client, headers, session_id, 2)
        client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        plan = client.get("/api/v1/training-plans", headers=headers).json()["data"][0]

        key = add_scene_task(plan["id"], scene)
        chained = client.post(
            "/api/v1/training-sessions",
            headers=headers,
            json={"sceneId": scene, "planId": plan["id"], "taskKey": key},
        ).json()["data"]["id"]
        _run_rounds(client, headers, chained, 6)
        client.post(f"/api/v1/training-sessions/{chained}/finish", headers=headers)

        plans = client.get("/api/v1/training-plans", headers=headers).json()["data"]
        assert len(plans) == 1, "计划任务里的训练不再派生新计划（training.plan_id 幂等约束）"

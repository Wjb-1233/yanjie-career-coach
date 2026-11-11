"""计划编号、累积与降级仍生成计划（走兜底分支）的回归测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.llm import llm_gateway
from app.main import app
from tests.plan_task_helper import add_scene_task


PLAN_DRAFT = {
    "title": "信息完整提升计划",
    "lesson": {
        "title": "信息完整微课",
        "intro": "三个步骤把结论、依据、行动说全。",
        "steps": [
            {"title": "先说结论", "explanation": "开口第一句把结论放出来。", "example": "我的结论是先修数据一致性。"},
            {"title": "补一条依据", "explanation": "用可核对的事实支撑结论。", "example": "依据是本周三位客户反馈同一处报错。"},
            {"title": "落到行动", "explanation": "明确谁在什么时候做什么。", "example": "我今天下午提交方案，明早同步结果。"},
        ],
        "exercise": "用三个步骤重写一段至少 40 字的表达。",
    },
    "practice_task": "用三步法重写一段回答。",
    "rewrite_task": "把原来的回答改写成完整版本。",
    "retest_task": "回到原场景再练一轮并对比分数。",
}

SCORE = {
    "scores": {"logic": 2, "correctness": 2, "relevance": 3, "concision": 3},
    "summary": "结论与依据需要补全。",
    "suggestions": [{"roundNo": 1, "problem": "缺少依据", "original": "我会处理", "rewrite": "我先修数据一致性。"}],
    "styleTags": ["务实"],
}


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "计划编号", "consent": True},
    )
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _finish(client: TestClient, headers: dict[str, str], scene_id: str, rounds: int = 2, plan: bool = True) -> str:
    created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id})
    session_id = created.json()["data"]["id"]
    for index in range(rounds):
        client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=headers,
            json={"content": f"第{index + 1}轮：我先给结论，再补一条可核对依据，最后说明下一步。"},
        )
    finished = client.post(
        f"/api/v1/training-sessions/{session_id}/finish?create_plan={'true' if plan else 'false'}",
        headers=headers,
    )
    assert finished.status_code == 200, finished.text
    return session_id


def test_each_evaluation_creates_numbered_plan(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, _user: str, **_kwargs):
        if "提升计划" in system_prompt:
            return PLAN_DRAFT
        return SCORE

    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)

    with TestClient(app, client=(f"number-{uuid4().hex}", 50010)) as client:
        headers = _register(client, "number")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]

        _finish(client, headers, scene)
        _finish(client, headers, scene)

        plans = client.get("/api/v1/training-plans", headers=headers).json()["data"]
        assert len(plans) == 2, "每次评分都应生成一份新计划"
        assert sorted(plan["sequence"] for plan in plans) == [1, 2]
        assert all(plan["status"] == "ACTIVE" for plan in plans), "未完成的计划应累积保留"


def test_degraded_evaluation_still_creates_plan(monkeypatch) -> None:
    async def unavailable(*_args, **_kwargs):
        raise TimeoutError("model down")

    monkeypatch.setattr(llm_gateway, "complete_json", unavailable)

    with TestClient(app, client=(f"degraded-{uuid4().hex}", 50011)) as client:
        headers = _register(client, "degradedplan")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]

        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene}).json()["data"]["id"]
        for index in range(2):
            client.post(
                f"/api/v1/training-sessions/{created}/messages/complete",
                headers=headers,
                json={"content": f"第{index}轮：我先说结论，再补依据。"},
            )
        finished = client.post(f"/api/v1/training-sessions/{created}/finish", headers=headers)
        assert finished.status_code == 200
        assert finished.json()["data"]["degraded"] is True

        plans = client.get("/api/v1/training-plans", headers=headers).json()["data"]
        assert len(plans) == 1, "降级评分同样生成计划（走 generate_plan 的兜底分支）"


def test_plan_session_requires_six_rounds_and_auto_completes(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, _user: str, **_kwargs):
        if "提升计划" in system_prompt:
            return PLAN_DRAFT
        return SCORE

    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)

    with TestClient(app, client=(f"rounds-{uuid4().hex}", 50012)) as client:
        headers = _register(client, "rounds")
        scene = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        _finish(client, headers, scene)
        plan = client.get("/api/v1/training-plans", headers=headers).json()["data"][0]
        key = add_scene_task(plan["id"], scene)
        task = {"key": key, "sceneId": scene}

        started = client.post(
            "/api/v1/training-sessions",
            headers=headers,
            json={"sceneId": task["sceneId"], "planId": plan["id"], "taskKey": task["key"]},
        )
        assert started.status_code == 201, started.text
        session_id = started.json()["data"]["id"]

        for index in range(4):
            client.post(
                f"/api/v1/training-sessions/{session_id}/messages/complete",
                headers=headers,
                json={"content": f"第{index + 1}轮：先结论，后依据。"},
            )
        early = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert early.status_code == 422
        assert early.json()["title"] == "PLAN_ROUNDS_INSUFFICIENT"

        for index in range(4, 6):
            client.post(
                f"/api/v1/training-sessions/{session_id}/messages/complete",
                headers=headers,
                json={"content": f"第{index + 1}轮：先结论，后依据。"},
            )
        done = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert done.status_code == 200, done.text

        refreshed = client.get(f"/api/v1/training-plans/{plan['id']}", headers=headers).json()["data"]
        completed = next(item for item in refreshed["tasks"] if item["key"] == task["key"])
        assert completed["completed"] is True, "结束时应当自动勾掉计划任务"

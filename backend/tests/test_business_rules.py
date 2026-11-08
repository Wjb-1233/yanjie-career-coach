"""业务规则回归：计划任务必须由真实训练支撑，报告只与同场景历史比较。"""

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


def _login(client: TestClient) -> dict[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": f"rules-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "规则"},
    )
    return {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}


def _finish(client: TestClient, headers: dict[str, str], scene_id: str, rounds: int, plan: bool) -> str:
    created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id})
    session_id = created.json()["data"]["id"]
    for index in range(rounds):
        client.post(
            f"/api/v1/training-sessions/{session_id}/messages/complete",
            headers=headers,
            json={"content": f"第{index + 1}轮：我先说结论，再给一条可核对依据，最后说明下一步安排。"},
        )
    response = client.post(
        f"/api/v1/training-sessions/{session_id}/finish?create_plan={'true' if plan else 'false'}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return session_id


def test_scene_task_requires_finished_training(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, _user: str, **_kwargs):
        if "提升计划" in system_prompt:
            return PLAN_DRAFT
        if "微课教练" in system_prompt:
            return {"passed": True, "feedback": "回答完整。"}
        return {
            "scores": {"logic": 2, "correctness": 2, "relevance": 3, "concision": 3},
            "summary": "结论与依据都需要补全。",
            "suggestions": [{"roundNo": 1, "problem": "缺少依据", "original": "我会处理", "rewrite": "我先修数据一致性。"}],
            "styleTags": ["务实"],
        }

    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)

    with TestClient(app, client=(f"rules-{uuid4().hex}", 50001)) as client:
        headers = _login(client)
        _finish(client, headers, "scene-interview-03", 2, True)
        plan = client.get("/api/v1/training-plans", headers=headers).json()["data"][0]
        key = add_scene_task(plan["id"], "scene-interview-03")
        scene_task = {"key": key, "sceneId": "scene-interview-03"}

        without_evidence = client.post(
            f"/api/v1/training-plans/{plan['id']}/tasks/{scene_task['key']}/complete",
            headers=headers,
            json={"evidence": None},
        )
        assert without_evidence.status_code == 422
        assert without_evidence.json()["title"] == "TRAINING_NOT_COMPLETED"

        short = _finish(client, headers, scene_task["sceneId"], 2, False)
        too_short = client.post(
            f"/api/v1/training-plans/{plan['id']}/tasks/{scene_task['key']}/complete",
            headers=headers,
            json={"evidence": short},
        )
        assert too_short.status_code == 422
        assert too_short.json()["title"] == "TRAINING_ROUNDS_INSUFFICIENT"

        valid = _finish(client, headers, scene_task["sceneId"], 6, False)
        accepted = client.post(
            f"/api/v1/training-plans/{plan['id']}/tasks/{scene_task['key']}/complete",
            headers=headers,
            json={"evidence": valid},
        )
        assert accepted.status_code == 200, accepted.text


def test_report_compares_only_same_scene(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, _user: str, **_kwargs):
        return {
            "scores": {"logic": 3, "correctness": 3, "relevance": 3, "concision": 3},
            "summary": "稳定发挥。",
            "suggestions": [],
            "styleTags": ["平稳"],
        }

    monkeypatch.setattr(llm_gateway, "complete_json", fake_complete)

    with TestClient(app, client=(f"rules-{uuid4().hex}", 50002)) as client:
        headers = _login(client)
        first = _finish(client, headers, "scene-interview-03", 2, False)
        other = _finish(client, headers, "scene-interview-05", 2, False)

        other_report = client.get(f"/api/v1/evaluations/{other}", headers=headers).json()["data"]
        assert other_report["previousScores"] is None, "不同场景之间不应互相比较"

        again = _finish(client, headers, "scene-interview-03", 2, False)
        report = client.get(f"/api/v1/evaluations/{again}", headers=headers).json()["data"]
        assert report["previousScores"] is not None
        assert report["previousScores"]["logic"] >= 1
        assert first != again

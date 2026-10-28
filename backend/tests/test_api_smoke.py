from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.llm import llm_gateway


def send_rounds(client: TestClient, headers: dict[str, str], session_id: str, count: int) -> None:
    for index in range(count):
        reply = client.post(
            f"/api/v1/training-sessions/{session_id}/messages",
            headers=headers,
            json={"content": f"第 {index + 1} 轮：我会先回应问题，再给出事实依据和明确的下一步。"},
        )
        assert reply.status_code == 200
        assert "event: done" in reply.text


def test_complete_turn_endpoint_supports_phone_flow() -> None:
    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": f"phone-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "手机测试学员"},
        )
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        scene_id = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        created = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id})
        session_id = created.json()["data"]["id"]
        for number in (1, 2):
            reply = client.post(
                f"/api/v1/training-sessions/{session_id}/messages/complete",
                headers=headers,
                json={"content": f"第{number}轮，我先说明真实经历，再解释行动和结果。"},
            )
            assert reply.status_code == 200
            turn = reply.json()["data"]
            assert turn["roundNo"] == number
            assert turn["messageId"]
            assert turn["content"]
        finished = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert finished.status_code == 200
        assert finished.json()["data"]["overallScore"] > 0
        assert client.get("/api/v1/scripts", headers=headers).json()["data"] == []


def test_health_auth_and_scene_flow() -> None:
    email = f"student-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["data"]["status"] == "ok"
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"
        assert health.headers["x-request-id"]

        ready = client.get("/api/v1/ready")
        assert ready.status_code == 200
        assert ready.json()["data"]["checks"]["database"] == "ok"

        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "GraduateDesign123!",
                "displayName": "测试学员",
            },
        )
        assert registered.status_code == 201
        token = registered.json()["data"]["accessToken"]

        scenes = client.get(
            "/api/v1/scenes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert scenes.status_code == 200
        assert len(scenes.json()["data"]) >= 4
        sample = scenes.json()["data"][0]
        filtered = client.get(
            "/api/v1/scenes",
            headers={"Authorization": f"Bearer {token}"},
            params={"industry": sample["industry"], "position": sample["position"], "difficulty": sample["difficulty"]},
        )
        assert filtered.status_code == 200
        assert all(item["industry"] == sample["industry"] and item["position"] == sample["position"] and item["difficulty"] == sample["difficulty"] for item in filtered.json()["data"])

        courses = client.get("/api/v1/courses", headers={"Authorization": f"Bearer {token}"})
        course_id = courses.json()["data"][0]["id"]
        progress = client.post(f"/api/v1/courses/{course_id}/progress", headers={"Authorization": f"Bearer {token}"}, json={"progress": 25})
        assert progress.status_code == 200
        refreshed = client.get("/api/v1/courses", headers={"Authorization": f"Bearer {token}"})
        assert next(item for item in refreshed.json()["data"] if item["id"] == course_id)["progress"] == 25

        profile = client.patch("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}, json={"displayName": "资料维护测试", "bio": "正在准备面试"})
        assert profile.status_code == 200
        assert profile.json()["data"]["bio"] == "正在准备面试"


def test_training_plan_can_be_opened_and_checked_in() -> None:
    email = f"plan-{uuid4().hex[:8]}@example.com"

    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "GraduateDesign123!",
                "displayName": "计划测试学员",
            },
        )
        token = registered.json()["data"]["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}

        scenes = client.get("/api/v1/scenes", headers=headers).json()["data"]
        created = client.post(
            "/api/v1/training-sessions",
            headers=headers,
            json={"sceneId": scenes[0]["id"]},
        )
        session_id = created.json()["data"]["id"]
        assert client.get("/api/v1/dashboard", headers=headers).json()["data"]["trainingCount"] == 0
        insufficient = client.post(
            f"/api/v1/training-sessions/{session_id}/finish", headers=headers
        )
        assert insufficient.status_code == 422
        send_rounds(client, headers, session_id, 2)
        finished = client.post(
            f"/api/v1/training-sessions/{session_id}/finish",
            headers=headers,
        )
        assert finished.status_code == 200
        assert client.get("/api/v1/dashboard", headers=headers).json()["data"]["trainingCount"] == 1

        plans = client.get("/api/v1/training-plans", headers=headers)
        assert plans.status_code == 200
        plan = plans.json()["data"][0]
        assert plan["progress"] == 0
        assert len(plan["tasks"]) == 4
        assert [item["actionType"] for item in plan["tasks"]] == ["COURSE", "TRAINING", "REWRITE", "RETEST"]
        practice_task = plan["tasks"][1]
        assert practice_task["sceneId"].startswith("scene-foundation-")
        assert practice_task["sourceSessionId"] == session_id
        premature = client.post(
            f"/api/v1/training-plans/{plan['id']}/tasks/{practice_task['key']}/complete",
            headers=headers,
            json={"evidence": session_id},
        )
        assert premature.status_code == 422
        # 四步计划中复练排在微课之后，未完成课程时先被顺序校验拦下
        assert premature.json()["title"] == "PREVIOUS_TASK_INCOMPLETE"
        locked = client.post(
            f"/api/v1/training-plans/{plan['id']}/tasks/retest/complete",
            headers=headers,
            json={"evidence": session_id},
        )
        assert locked.status_code == 422
        assert locked.json()["title"] == "PREVIOUS_TASK_INCOMPLETE"


def test_login_rate_limit_returns_retry_after() -> None:
    with TestClient(app) as client:
        responses = [
            client.post(
                "/api/v1/auth/login",
                json={"email": "missing@example.com", "password": "NotThePassword123!"},
            )
            for _ in range(11)
        ]

        assert all(response.status_code == 401 for response in responses[:10])
        assert responses[10].status_code == 429
        assert int(responses[10].headers["retry-after"]) >= 1


def test_evaluation_degraded_status_survives_reload(monkeypatch) -> None:
    async def unavailable_model(*_args, **_kwargs):
        raise TimeoutError("synthetic model timeout")

    monkeypatch.setattr(llm_gateway, "complete_json", unavailable_model)
    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"degraded-{uuid4().hex[:8]}@example.com",
                "password": "GraduateDesign123!",
                "displayName": "降级报告测试",
            },
        )
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        scene_id = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        created = client.post(
            "/api/v1/training-sessions",
            headers=headers,
            json={"sceneId": scene_id},
        )
        session_id = created.json()["data"]["id"]
        send_rounds(client, headers, session_id, 2)

        finished = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert finished.status_code == 200
        assert finished.json()["data"]["degraded"] is True

        reloaded = client.get(f"/api/v1/evaluations/{session_id}", headers=headers)
        assert reloaded.status_code == 200
        assert reloaded.json()["data"]["degraded"] is True

        repeated = client.post(f"/api/v1/training-sessions/{session_id}/finish", headers=headers)
        assert repeated.status_code == 200
        assert repeated.json()["data"]["degraded"] is True

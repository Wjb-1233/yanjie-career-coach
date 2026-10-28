from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_early_finish_waits_for_the_current_answer_and_does_not_ask_again() -> None:
    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": f"closure-{uuid4().hex[:8]}@example.com", "password": "GraduateDesign123!", "displayName": "收尾测试"},
        )
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        created = client.post(
            "/api/v1/training-sessions", headers=headers,
            json={"sceneId": "scene-interview-03"},
        )
        session_id = created.json()["data"]["id"]
        endpoint = f"/api/v1/training-sessions/{session_id}/messages/complete"

        first = client.post(endpoint, headers=headers, json={"content": "我负责后端接口与数据库设计。"})
        second = client.post(endpoint, headers=headers, json={"content": "我通过日志核对请求链路与错误原因。"})
        assert first.status_code == second.status_code == 200
        assert second.json()["data"]["finished"] is False

        closing = client.post(
            endpoint, headers=headers,
            json={"content": "最后，我会记录排查结果并回归测试。", "finishAfterReply": True},
        )
        assert closing.status_code == 200
        reply = closing.json()["data"]
        assert reply["finished"] is True
        assert reply["roundNo"] == 3
        assert "？" not in reply["content"]
        assert client.get(f"/api/v1/training-sessions/{session_id}", headers=headers).json()["data"]["status"] == "FINISHED"

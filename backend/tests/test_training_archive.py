from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_finished_session_archive_restore_and_replay() -> None:
    with TestClient(app, client=("198.51.100.78", 50124)) as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": f"archive-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!", "displayName": "归档测试",
        })
        headers = {"Authorization": f"Bearer {registered.json()['data']['accessToken']}"}
        scene_id = client.get("/api/v1/scenes", headers=headers).json()["data"][0]["id"]
        training_id = client.post("/api/v1/training-sessions", headers=headers, json={"sceneId": scene_id}).json()["data"]["id"]
        for index in range(2):
            response = client.post(f"/api/v1/training-sessions/{training_id}/messages", headers=headers, json={"content": f"回答第{index + 1}轮，我会说明事实依据和接下来的行动计划。"})
            assert response.status_code == 200
        assert client.post(f"/api/v1/training-sessions/{training_id}/finish", headers=headers).status_code == 200

        archived = client.post(f"/api/v1/training-sessions/{training_id}/archive", headers=headers)
        assert archived.status_code == 200
        assert archived.json()["data"]["archivedAt"]
        assert all(item["id"] != training_id for item in client.get("/api/v1/training-sessions", headers=headers).json()["data"])
        archived_items = client.get("/api/v1/training-sessions?archived=true", headers=headers).json()["data"]
        assert any(item["id"] == training_id for item in archived_items)
        replay = client.get(f"/api/v1/training-sessions/{training_id}", headers=headers)
        assert replay.status_code == 200
        assert len(replay.json()["data"]["messages"]) == 5
        assert client.post(f"/api/v1/training-sessions/{training_id}/restore", headers=headers).status_code == 200
        assert any(item["id"] == training_id for item in client.get("/api/v1/training-sessions", headers=headers).json()["data"])

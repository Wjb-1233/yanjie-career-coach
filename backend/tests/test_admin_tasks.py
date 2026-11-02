"""后台任务管理接口测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _admin(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def test_list_tasks_returns_rows() -> None:
    with TestClient(app) as client:
        headers = _admin(client)
        response = client.get("/api/v1/admin/tasks?limit=5", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)


def test_retry_missing_task_returns_404() -> None:
    with TestClient(app) as client:
        headers = _admin(client)
        response = client.post(f"/api/v1/admin/tasks/{uuid4()}/retry", headers=headers)
        assert response.status_code == 404

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_admin_can_manage_catalog_users_and_export_reports() -> None:
    with TestClient(app, client=("198.51.100.77", 50123)) as client:
        admin_login = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "Admin123!"})
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['accessToken']}"}

        student = client.post("/api/v1/auth/register", json={
            "email": f"admin-test-{uuid4().hex[:8]}@example.com",
            "password": "GraduateDesign123!", "displayName": "管理测试学员",
        })
        student_data = student.json()["data"]
        student_headers = {"Authorization": f"Bearer {student_data['accessToken']}"}
        assert client.get("/api/v1/admin/overview", headers=student_headers).status_code == 403

        scene_payload = {
            "category": "交叉面 / 总监面", "title": "管理测试场景", "industry": "互联网",
            "position": "产品经理", "roleName": "业务面试官", "difficulty": "中级",
            "background": "测试管理员创建面试场景所需背景内容。", "goal": "验证用户能完成场景训练。",
            "tags": ["管理测试"], "openingLine": "请介绍一次你推动项目的经历。", "active": True,
        }
        scene = client.post("/api/v1/admin/scenes", headers=admin_headers, json=scene_payload)
        assert scene.status_code == 201
        scene_id = scene.json()["data"]["id"]
        assert any(item["id"] == scene_id for item in client.get("/api/v1/admin/scenes", headers=admin_headers).json()["data"])
        assert client.delete(f"/api/v1/admin/scenes/{scene_id}", headers=admin_headers).json()["data"]["active"] is False
        assert all(item["id"] != scene_id for item in client.get("/api/v1/scenes", headers=student_headers).json()["data"])

        course_payload = {
            "title": "管理测试微课", "dimension": "逻辑性", "minutes": 10,
            "description": "用于验证课程管理功能的描述文本。", "content": "课程正文至少二十个字符，用于测试管理端创建和维护微课内容。", "active": True,
        }
        course = client.post("/api/v1/admin/courses", headers=admin_headers, json=course_payload)
        assert course.status_code == 201
        course_id = course.json()["data"]["id"]
        assert client.patch(f"/api/v1/admin/courses/{course_id}", headers=admin_headers, json={**course_payload, "title": "已更新的微课"}).status_code == 200

        updated = client.patch(f"/api/v1/admin/users/{student_data['user']['id']}", headers=admin_headers, json={"active": False})
        assert updated.status_code == 200
        assert client.get("/api/v1/auth/me", headers=student_headers).status_code == 401
        assert client.post("/api/v1/auth/login", json={"email": student_data["user"]["email"], "password": "GraduateDesign123!"}).status_code == 401

        sessions = client.get("/api/v1/admin/sessions", headers=admin_headers)
        assert sessions.status_code == 200
        export = client.get("/api/v1/admin/reports/export", headers=admin_headers)
        assert export.status_code == 200
        assert "text/csv" in export.headers["content-type"]


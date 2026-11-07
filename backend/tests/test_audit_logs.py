"""管理台审计日志：管理操作留痕，普通用户不可见。"""

from uuid import uuid4

from sqlalchemy import select

from fastapi.testclient import TestClient

from app.main import app


def test_admin_mutation_is_audited() -> None:
    with TestClient(app, client=(f"audit-{uuid4().hex}", 50120)) as client:
        email = f"audit-{uuid4().hex[:8]}@example.com"
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "AuditTest123!", "displayName": "审计"},
        )
        token = registered.json()["data"]["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}

        # 普通用户不能读审计日志
        denied = client.get("/api/v1/admin/audit-logs", headers=headers)
        assert denied.status_code in (401, 403)

        # 把该用户提升为管理员（测试库隔离）
        from app.db.base import session_factory
        from app.db.models import User

        async def promote() -> None:
            async with session_factory() as session:
                user = await session.scalar(select(User).where(User.email == email))
                assert user is not None
                user.role = "ADMIN"
                await session.commit()

        client.portal.call(promote)

        created = client.post(
            "/api/v1/admin/scenes",
            headers=headers,
            json={
                "category": "技术一面",
                "title": f"审计测试场景-{uuid4().hex[:6]}",
                "industry": "互联网",
                "position": "后端开发",
                "roleName": "面试官",
                "difficulty": "中级",
                "background": "用于审计测试的场景背景。",
                "goal": "验证管理操作是否留痕。",
                "openingLine": "你好，我们开始。",
                "tags": [],
                "questions": [],
            },
        )
        assert created.status_code in (201, 422), created.text

        logs = client.get("/api/v1/admin/audit-logs", headers=headers)
        assert logs.status_code == 200, logs.text
        payload = logs.json()["data"]
        assert payload["total"] >= 1
        assert any(item["method"] == "POST" and "/admin/" in item["route"] for item in payload["items"])
        assert all(item["status"] < 400 for item in payload["items"])

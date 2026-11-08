import asyncio

import pytest
"""成本治理：每日模型调用配额、用量计数与管理台用量汇总。"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, prefix: str) -> tuple[dict[str, str], str]:
    email = f"{prefix}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "QuotaTest123!", "displayName": "配额"},
    )
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}, email


LONG_JD = """岗位职责：
1. 负责后端服务的设计与开发，保证接口性能与稳定性；
2. 熟悉 MySQL、Redis，能够独立完成数据模型设计；
3. 参与线上故障排查与性能优化，推动问题闭环；
4. 具备良好的沟通能力，能与产品和前端协作推进项目。"""


def test_daily_quota_blocks_after_limit(monkeypatch) -> None:
    from app.infrastructure import rate_limit as module

    monkeypatch.setattr(module.settings, "model_daily_quota", 2, raising=False)

    with TestClient(app, client=(f"quota-{uuid4().hex}", 50150)) as client:
        headers, _ = _register(client, "quota")
        payload = {"jd": LONG_JD, "position": "后端开发工程师"}

        first = client.post("/api/v1/my-scenes/draft-from-jd", headers=headers, json=payload)
        second = client.post("/api/v1/my-scenes/draft-from-jd", headers=headers, json=payload)
        third = client.post("/api/v1/my-scenes/draft-from-jd", headers=headers, json=payload)

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert third.status_code == 429, third.text
        assert third.json()["title"] == "MODEL_QUOTA_EXCEEDED"

        # 配额被拒不计入用量（只统计当前用户，避免受其他测试影响）
        me = client.get("/api/v1/auth/me", headers=headers).json()["data"]
        from app.db.base import session_factory
        from app.db.models import ModelUsageDaily

        async def calls() -> int:
            async with session_factory() as session:
                rows = (
                    await session.scalars(
                        select(ModelUsageDaily).where(ModelUsageDaily.user_id == me["id"])
                    )
                ).all()
                return sum(row.calls for row in rows)

        total = client.portal.call(calls)
        assert total == 2


def test_usage_endpoint_lists_top_users() -> None:
    with TestClient(app, client=(f"quota-{uuid4().hex}", 50151)) as client:
        headers, email = _register(client, "usage")
        client.post(
            "/api/v1/my-scenes/draft-from-jd",
            headers=headers,
            json={"jd": LONG_JD, "position": "后端开发"},
        )

        denied = client.get("/api/v1/admin/model-usage", headers=headers)
        assert denied.status_code in (401, 403)

        from app.db.base import session_factory
        from app.db.models import User

        async def promote() -> None:
            async with session_factory() as session:
                user = await session.scalar(select(User).where(User.email == email))
                user.role = "ADMIN"
                await session.commit()

        client.portal.call(promote)

        response = client.get("/api/v1/admin/model-usage?days=7", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["totalCalls"] >= 1
        assert any(item["calls"] >= 1 for item in data["items"])
        assert data["since"] <= datetime.now(timezone.utc).date().isoformat()


@pytest.fixture
async def factory(tmp_path):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.base import Base

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_concurrent_usage_recording_is_atomic(factory, monkeypatch) -> None:
    """同一用户并发调用不能因为主键冲突报 500。"""
    from app.infrastructure import rate_limit

    monkeypatch.setattr("app.db.base.session_factory", factory)

    async with factory() as session:
        from app.db.models import User

        user = User(email="race@example.com", password_hash="x", display_name="并发")
        session.add(user)
        await session.commit()
        user_id = user.id

    # 并发调用不抛主键冲突（此前会 500），且之后仍能继续累加
    await asyncio.gather(*[rate_limit._record_usage(user_id) for _ in range(6)])

    from sqlalchemy import select

    from app.db.models import ModelUsageDaily

    async with factory() as session:
        rows = (await session.scalars(select(ModelUsageDaily))).all()
        assert sum(row.calls for row in rows) >= 1
        before = sum(row.calls for row in rows)

    await rate_limit._record_usage(user_id)

    async with factory() as session:
        rows = (await session.scalars(select(ModelUsageDaily))).all()
        assert sum(row.calls for row in rows) == before + 1

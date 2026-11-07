"""后台任务：只回收过期 RUNNING，正常运行的不会被别的实例抢走。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AnalysisTask, User


@pytest.fixture
async def factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    from app.features.tasks import service

    monkeypatch.setattr(service, "session_factory", session_factory)
    yield session_factory
    await engine.dispose()


async def test_requeue_only_stale_running_tasks(factory) -> None:
    from app.features.tasks.service import requeue_stale

    async with factory() as session:
        user = User(email="worker@example.com", password_hash="x", display_name="任务测试")
        session.add(user)
        await session.flush()
        stale = AnalysisTask(
            user_id=user.id,
            kind="video_interview",
            payload={},
            status="RUNNING",
            progress=10,
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        fresh = AnalysisTask(
            user_id=user.id,
            kind="video_interview",
            payload={},
            status="RUNNING",
            progress=40,
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        session.add_all([stale, fresh])
        await session.commit()
        stale_id, fresh_id = stale.id, fresh.id

    requeued = await requeue_stale(minutes=15)
    assert requeued == 1

    async with factory() as session:
        assert (await session.get(AnalysisTask, stale_id)).status == "PENDING"
        assert (await session.get(AnalysisTask, fresh_id)).status == "RUNNING"

"""任务队列的单元测试（不跑真实模型）。"""
import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AnalysisTask, User
from app.features.tasks import service


@pytest.fixture
async def factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(service, "session_factory", maker)
    async with maker() as db:
        db.add(User(email="task@example.com", password_hash="x", display_name="任务测试"))
        await db.commit()
        user = await db.scalar(select(User))
    yield maker, user.id
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_claim_task(factory) -> None:
    maker, user_id = factory
    task = await service.create_task(user_id, "VIDEO_INTERVIEW", {"sceneId": "s"})
    assert task.status == "PENDING"

    claimed = await service._claim_next()
    assert claimed is not None
    assert claimed.status == "RUNNING"

    again = await service._claim_next()
    assert again is None


@pytest.mark.asyncio
async def test_unknown_kind_marks_failed(factory) -> None:
    maker, user_id = factory
    await service.create_task(user_id, "UNKNOWN", {})
    await service._run_once()
    async with maker() as db:
        rows = (await db.scalars(select(AnalysisTask))).all()
    assert rows[0].status == "FAILED"
    assert rows[0].error

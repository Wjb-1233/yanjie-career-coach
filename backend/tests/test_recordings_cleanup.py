"""录制保留策略的单元测试。"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.models import Scene, TrainingSession, User
from app.features.recordings import storage
from app.features.recordings.cleanup import purge_expired, usage


@pytest.fixture
async def isolated_recordings(tmp_path, monkeypatch):
    """把录制目录指向临时路径，避免测试误删真实文件。"""
    target = tmp_path / "recordings"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "recording_dir", str(target))
    return target


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rec.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _make_session(factory, *, days_ago: int, recording: str | None) -> str:
    async with factory() as db:
        user = User(email=f"rec-{days_ago}@example.com", password_hash="x", display_name="录制测试")
        db.add(user)
        await db.flush()
        existing = await db.get(Scene, "scene-rec-test")
        if existing is not None:
            scene = existing
        else:
            scene = Scene(
            id="scene-rec-test",
            category="HR 初面",
            title="录制测试场景",
            industry="综合",
            position="通用",
            role_name="招聘 HR",
            difficulty="中级",
            background="测试",
            goal="测试",
            tags=[],
            opening_line="你好",
            question_bank=[],
            active=True,
            )
            db.add(scene)
            await db.flush()
        session = TrainingSession(
            user_id=user.id,
            scene_id=scene.id,
            status="FINISHED",
            channel="VOICE",
            started_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            recording_path=recording,
        )
        db.add(session)
        await db.commit()
        return session.id


@pytest.mark.asyncio
async def test_purge_removes_expired_and_keeps_recent(session_factory, isolated_recordings) -> None:
    old_path = settings.recording_dir_path / "expired-test.webm"
    old_path.write_bytes(b"old")
    new_path = settings.recording_dir_path / "recent-test.webm"
    new_path.write_bytes(b"new")

    await _make_session(session_factory, days_ago=40, recording="expired-test.webm")
    await _make_session(session_factory, days_ago=1, recording="recent-test.webm")

    async with session_factory() as db:
        result = await purge_expired(db, days=30)
        assert result["removed"] == 1
        rows = (await db.scalars(select(TrainingSession))).all()
        kept = [row for row in rows if row.recording_path]

    assert not old_path.exists()
    assert new_path.exists()
    assert len(kept) == 1
    storage.remove("recent-test.webm")


@pytest.mark.asyncio
async def test_purge_removes_orphan_files(session_factory, isolated_recordings) -> None:
    orphan = settings.recording_dir_path / "orphan-test.webm"
    orphan.write_bytes(b"orphan")

    async with session_factory() as db:
        result = await purge_expired(db, days=30)
        assert result["orphans"] >= 1
    assert not orphan.exists()


@pytest.mark.asyncio
async def test_usage_reports_counts(session_factory, isolated_recordings) -> None:
    async with session_factory() as db:
        info = await usage()
    assert info["count"] >= 0
    assert info["retentionDays"] == settings.recording_retention_days

"""删除训练会话时同步清理录像文件。"""

from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.db.base import Base
from app.db.models import Scene, TrainingSession, User
from app.features.recordings import storage
from app.features.training.service import delete_training_session


@pytest.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cleanup.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_session_removes_recording(factory, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "recording_dir", str(tmp_path / "recordings"))

    async with factory() as db:
        user = User(email="del@example.com", password_hash="x", display_name="删除测试")
        scene = Scene(
            id="scene-del", category="HR 初面", title="删除场景", industry="综合",
            position="通用", role_name="HR", difficulty="中级", background="b", goal="g",
            tags=[], opening_line="你好", question_bank=[], active=True,
        )
        db.add_all([user, scene])
        await db.flush()
        recording = storage.save_upload(UploadFile(file=BytesIO(b"video"), filename="clip.webm"))
        training = TrainingSession(
            user_id=user.id, scene_id=scene.id, status="FINISHED",
            channel="VIDEO", recording_path=recording,
        )
        db.add(training)
        await db.commit()
        session_id, user_id = training.id, user.id

    path = settings.recording_dir_path / recording
    assert path.exists()

    async with factory() as db:
        await delete_training_session(db, user_id, session_id)
        rows = (await db.scalars(select(TrainingSession))).all()

    assert not path.exists(), "录像文件应随会话一起删除"
    assert rows == []

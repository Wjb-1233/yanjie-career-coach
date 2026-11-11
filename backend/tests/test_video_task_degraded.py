"""静音 / 无人声录像的任务必须降级出报告，不能把整条任务判成 FAILED。

用户录了像、切题片段与人脸指标都在，只是没转写出作答：这种情况下仍然要建会话、
出降级评分，并把可读原因写进 delivery 与任务结果。
"""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import AppError
from app.db.base import Base
from app.db.models import AnalysisTask, Evaluation, Message, Scene, TrainingSession, User

QUESTIONS = [
    {"text": "请先做个自我介绍", "start": 0, "end": 6},
    {"text": "介绍一个你负责的项目", "start": 6, "end": 12},
]
REASON = "录像里没有识别到作答内容"


@pytest.fixture
async def store(tmp_path, monkeypatch):
    """独立 sqlite 库 + 一个 public 场景，避免污染其它测试的数据。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'video.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    from app.features.tasks import service

    monkeypatch.setattr(service, "session_factory", maker)

    recording = tmp_path / "silent.mp4"
    recording.write_bytes(b"\x00" * 64)

    async with maker() as db:
        user = User(email="degraded@example.com", password_hash="x", display_name="降级测试")
        db.add(user)
        await db.flush()
        # 评分后会顺带生成提升计划，计划要挂到对应维度上的基础场景
        for scene_id in [
            "scene-degraded",
            "scene-foundation-logic",
            "scene-foundation-correctness",
            "scene-foundation-relevance",
            "scene-foundation-concision",
        ]:
            db.add(
                Scene(
                    id=scene_id,
                    category="HR 初面",
                    title=f"降级测试场景 {scene_id}",
                    industry="综合",
                    position="通用",
                    role_name="招聘 HR",
                    difficulty="中级",
                    background="测试背景",
                    goal="测试目标",
                    tags=[],
                    opening_line="你好",
                    question_bank=[],
                    active=True,
                )
            )
        await db.commit()
        user_id = user.id

    yield maker, user_id, recording
    await engine.dispose()


def _silent_recording(monkeypatch, recording: Path) -> None:
    """模拟静音录像：一句人话都没转写出来，但画面指标与切题片段算得出来。"""
    from app.features.evaluations import delivery as delivery_module
    from app.features.recordings import storage
    from app.features.video import metrics as metrics_module
    from app.features.video import segments as segments_module

    monkeypatch.setattr(delivery_module, "analyze", lambda _path: {"words": []})
    monkeypatch.setattr(
        metrics_module, "analyze_video", lambda _path: {"tips": [], "averageConfidence": 0.82}
    )
    monkeypatch.setattr(
        segments_module,
        "split_segments",
        lambda *_args, **_kwargs: [{"index": 1, "start": 0, "end": 6, "url": "seg-1.mp4"}],
    )
    monkeypatch.setattr(storage, "path_of", lambda _name: recording)


async def test_silent_video_degrades_to_done_report(store, monkeypatch) -> None:
    maker, user_id, recording = store
    _silent_recording(monkeypatch, recording)

    from app.features.tasks import service

    await service.create_task(
        user_id,
        "VIDEO_INTERVIEW",
        {
            "sceneId": "scene-degraded",
            "questions": QUESTIONS,
            "durationSeconds": 12.0,
            "recording": "silent.mp4",
        },
    )
    assert await service._run_once() is True

    async with maker() as db:
        task = await db.scalar(select(AnalysisTask))
        # FAILED 会被管理台算进错误率：这类用户可见的失败必须是 DONE
        assert task.status == "DONE", task.error
        assert not task.error
        assert task.progress == 100
        assert task.result["transcriptReason"] == REASON
        assert task.result["degraded"] is True
        session_id = task.result["sessionId"]

        training = await db.get(TrainingSession, session_id)
        assert training is not None
        assert training.status == "FINISHED"
        assert training.channel == "VIDEO"
        assert training.current_round >= 2

        delivery = training.delivery
        assert delivery["transcriptReason"] == REASON
        assert delivery["vision"] == {"tips": [], "averageConfidence": 0.82}
        assert [mark["text"] for mark in delivery["marks"]] == [item["text"] for item in QUESTIONS]
        assert delivery["segments"], "切题片段必须保留"
        assert delivery["transcript"] == []

        messages = (await db.scalars(select(Message).where(Message.session_id == session_id))).all()
        assert any(message.speaker == "USER" for message in messages)

        evaluation = await db.scalar(select(Evaluation).where(Evaluation.session_id == session_id))
        assert evaluation is not None, "降级也要有评分报告"
        assert evaluation.overall_score > 0


async def test_degraded_session_without_marks_still_has_two_rounds(store) -> None:
    """连题目标记都缺时也要凑够两轮，否则评分链路会拒绝生成报告。"""
    maker, user_id, _recording = store
    from app.features.voice.session import create_voice_session

    async with maker() as db:
        session_id = await create_voice_session(
            db,
            user_id,
            "scene-degraded",
            [],
            delivery={"marks": []},
            engine="video",
            channel="VIDEO",
            degraded_reason=REASON,
        )

    async with maker() as db:
        training = await db.get(TrainingSession, session_id)
        assert training is not None
        assert training.current_round >= 2
        assert training.delivery["transcriptReason"] == REASON


async def test_empty_turns_still_rejected_without_degraded_reason(store) -> None:
    """没带降级原因时保持原有 422 契约，别把语音对练的空会话也放进来。"""
    maker, user_id, _recording = store
    from app.features.voice.session import create_voice_session

    async with maker() as db:
        with pytest.raises(AppError):
            await create_voice_session(db, user_id, "scene-degraded", [])

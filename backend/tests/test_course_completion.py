"""微课只要求看完视频：一次调用完成课程任务。"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import TrainingPlan, User
from app.features.plans.service import complete_course_task


@pytest.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'plan.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_complete_course_task_marks_done(factory) -> None:
    async with factory() as session:
        user = User(email="course@example.com", password_hash="x", display_name="课程")
        session.add(user)
        await session.flush()
        plan = TrainingPlan(
            user_id=user.id,
            focus_dimension="贴合问题",
            title="贴合问题训练",
            sequence=1,
            status="ACTIVE",
            tasks=[
                {
                    "key": "course",
                    "day": 1,
                    "task": "看一节微课",
                    "actionType": "COURSE",
                    "completed": False,
                    "completedSteps": [0, 1, 2],
                    "lesson": {
                        "title": "精准回应：从回避到贴合",
                        "intro": "学会先听懂问题，再直接回应，并用事实支撑答案。",
                        "steps": [
                            {"title": "先复述问题", "explanation": "先用一句话确认对方真正关心的问题是什么。", "example": "您是想了解我为什么选这个岗位，对吗？"},
                            {"title": "先给结论", "explanation": "先给结论，再解释理由，避免绕圈子。", "example": "我的答案是：这个岗位和我过去两年做的事高度一致。"},
                            {"title": "补一条事实", "explanation": "补一条可核实的事实或数据来支撑结论。", "example": "当时我把接口延迟从 800ms 降到 200ms，降了 75%。"},
                        ],
                        "exercise": "用一句话回应：你为什么选择这个岗位？",
                    },
                }
            ],
        )
        session.add(plan)
        await session.commit()
        plan_id = plan.id

    async with factory() as session:
        view = await complete_course_task(session, user.id, plan_id, "course")
        task = next(item for item in view.tasks if item.key == "course")
        assert task.completed is True
        assert task.evidence == "已看完微课视频"

    async with factory() as session:
        saved = await session.get(TrainingPlan, plan_id)
        assert saved.status == "COMPLETED"

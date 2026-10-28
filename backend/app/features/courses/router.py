from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.responses import ok
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import Course, CourseProgress
from app.features.courses.schemas import CourseView, ProgressRequest

router = APIRouter(prefix="/courses", tags=["课程学习"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_courses(user: CurrentUser, session: DbSession) -> dict:
    rows = (
        await session.execute(
            select(Course, CourseProgress)
            .outerjoin(
                CourseProgress,
                and_(CourseProgress.course_id == Course.id, CourseProgress.user_id == user.id),
            )
            .where(Course.active.is_(True))
            .order_by(Course.dimension)
        )
    ).all()
    data = []
    for course, progress in rows:
        view = CourseView.model_validate(course).model_copy(
            update={
                "progress": progress.progress if progress else 0,
                "completed": progress.completed if progress else False,
            }
        )
        data.append(view.model_dump(by_alias=True))
    return ok(data)


@router.post("/{course_id}/progress")
async def update_progress(
    course_id: str, body: ProgressRequest, user: CurrentUser, session: DbSession
) -> dict:
    if await session.get(Course, course_id) is None:
        raise not_found("课程")
    key = {"user_id": user.id, "course_id": course_id}
    progress = await session.get(CourseProgress, key)
    if progress is None:
        progress = CourseProgress(**key)
        session.add(progress)
    progress.progress = body.progress
    progress.completed = body.progress == 100
    await session.commit()
    return ok({"courseId": course_id, "progress": progress.progress, "completed": progress.completed})


import csv
from io import StringIO
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.core.responses import ok
from app.core.security import AdminUser
from app.db.base import get_session
from app.db.models import Course, Evaluation, RefreshToken, Scene, TrainingSession, User
from app.features.admin.schemas import CourseAdminInput, SceneAdminInput, UserAdminUpdate

router = APIRouter(prefix="/admin", tags=["后台管理"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("/overview")
async def overview(_: AdminUser, session: DbSession) -> dict:
    async def count(model: type) -> int:
        return int((await session.scalar(select(func.count()).select_from(model))) or 0)

    average = await session.scalar(select(func.avg(Evaluation.overall_score)))
    return ok({
        "users": await count(User),
        "activeUsers": int((await session.scalar(select(func.count()).select_from(User).where(User.active.is_(True)))) or 0),
        "scenes": await count(Scene),
        "activeScenes": int((await session.scalar(select(func.count()).select_from(Scene).where(Scene.active.is_(True)))) or 0),
        "courses": await count(Course),
        "activeCourses": int((await session.scalar(select(func.count()).select_from(Course).where(Course.active.is_(True)))) or 0),
        "sessions": await count(TrainingSession),
        "averageScore": round(float(average or 0), 1),
    })


@router.get("/users")
async def users(
    _: AdminUser,
    session: DbSession,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: str | None = None,
) -> dict:
    statement = select(User).order_by(User.created_at.desc())
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        statement = statement.where(func.lower(User.email).like(term) | func.lower(User.display_name).like(term))
    rows = (await session.scalars(statement.offset(page * size).limit(size))).all()
    return ok([{
        "id": item.id, "email": item.email, "displayName": item.display_name,
        "role": item.role, "active": item.active, "bio": item.bio,
        "createdAt": item.created_at.isoformat(),
    } for item in rows])


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserAdminUpdate, admin: AdminUser, session: DbSession) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("用户")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise AppError(422, "EMPTY_UPDATE", "请至少提交一个要修改的字段")
    if user.id == admin.id and changes.get("active") is False:
        raise AppError(422, "CANNOT_DISABLE_SELF", "不能停用当前管理员账号")
    if user.role == "ADMIN" and (changes.get("role") == "STUDENT" or changes.get("active") is False):
        admins = await session.scalar(select(func.count()).select_from(User).where(User.role == "ADMIN", User.active.is_(True)))
        if admins <= 1:
            raise AppError(422, "LAST_ADMIN", "系统至少需要保留一个启用的管理员")
    for key, value in changes.items():
        setattr(user, key, value)
    if changes.get("active") is False:
        await session.execute(
            RefreshToken.__table__.delete().where(RefreshToken.user_id == user.id)
        )
    await session.commit()
    return ok({"id": user.id, "role": user.role, "active": user.active})


@router.get("/scenes")
async def scenes(_: AdminUser, session: DbSession) -> dict:
    rows = (await session.scalars(select(Scene).order_by(Scene.created_at.desc()))).all()
    return ok([{
        "id": item.id, "category": item.category, "title": item.title,
        "industry": item.industry, "position": item.position, "roleName": item.role_name,
        "difficulty": item.difficulty, "background": item.background, "goal": item.goal,
        "tags": item.tags, "openingLine": item.opening_line, "active": item.active,
    } for item in rows])


@router.post("/scenes", status_code=201)
async def create_scene(body: SceneAdminInput, _: AdminUser, session: DbSession) -> dict:
    scene = Scene(id=f"scene-{uuid4().hex}", **body.model_dump())
    session.add(scene)
    await session.commit()
    return ok({"id": scene.id})


@router.patch("/scenes/{scene_id}")
async def update_scene(scene_id: str, body: SceneAdminInput, _: AdminUser, session: DbSession) -> dict:
    scene = await session.get(Scene, scene_id)
    if scene is None:
        raise not_found("面试场景")
    for key, value in body.model_dump().items():
        setattr(scene, key, value)
    await session.commit()
    return ok({"id": scene.id, "active": scene.active})


@router.delete("/scenes/{scene_id}")
async def deactivate_scene(scene_id: str, _: AdminUser, session: DbSession) -> dict:
    scene = await session.get(Scene, scene_id)
    if scene is None:
        raise not_found("面试场景")
    scene.active = False
    await session.commit()
    return ok({"id": scene.id, "active": False})


@router.get("/courses")
async def courses(_: AdminUser, session: DbSession) -> dict:
    rows = (await session.scalars(select(Course).order_by(Course.created_at.desc()))).all()
    return ok([{
        "id": item.id, "title": item.title, "dimension": item.dimension,
        "minutes": item.minutes, "description": item.description,
        "content": item.content, "active": item.active,
    } for item in rows])


@router.post("/courses", status_code=201)
async def create_course(body: CourseAdminInput, _: AdminUser, session: DbSession) -> dict:
    course = Course(id=f"course-{uuid4().hex}", **body.model_dump())
    session.add(course)
    await session.commit()
    return ok({"id": course.id})


@router.patch("/courses/{course_id}")
async def update_course(course_id: str, body: CourseAdminInput, _: AdminUser, session: DbSession) -> dict:
    course = await session.get(Course, course_id)
    if course is None:
        raise not_found("微课")
    for key, value in body.model_dump().items():
        setattr(course, key, value)
    await session.commit()
    return ok({"id": course.id, "active": course.active})


@router.get("/sessions")
async def sessions(
    _: AdminUser, session: DbSession,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
) -> dict:
    statement = select(TrainingSession, Scene, User, Evaluation).join(Scene, Scene.id == TrainingSession.scene_id).join(User, User.id == TrainingSession.user_id).outerjoin(Evaluation, Evaluation.session_id == TrainingSession.id)
    if status in {"ACTIVE", "FINISHED"}:
        statement = statement.where(TrainingSession.status == status)
    rows = (await session.execute(statement.order_by(TrainingSession.started_at.desc()).offset(page * size).limit(size))).all()
    return ok([{
        "id": training.id, "userId": user.id, "sceneTitle": scene.title, "userName": user.display_name,
        "email": user.email, "status": training.status, "rounds": training.current_round,
        "startedAt": training.started_at.isoformat(),
        "overallScore": evaluation.overall_score if evaluation else None,
    } for training, scene, user, evaluation in rows])


@router.get("/reports/export")
async def export_reports(_: AdminUser, session: DbSession) -> StreamingResponse:
    rows = (await session.execute(
        select(TrainingSession, Scene, User, Evaluation)
        .join(Scene, Scene.id == TrainingSession.scene_id)
        .join(User, User.id == TrainingSession.user_id)
        .outerjoin(Evaluation, Evaluation.session_id == TrainingSession.id)
        .order_by(TrainingSession.started_at.desc()).limit(5000)
    )).all()
    output = StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["学员", "邮箱", "场景", "状态", "轮次", "综合分", "逻辑性", "得体性", "感染力", "针对性", "简洁度", "评分摘要", "开始时间"])
    for training, scene, user, evaluation in rows:
        writer.writerow([
            user.display_name, user.email, scene.title, training.status,
            training.current_round, evaluation.overall_score if evaluation else "",
            evaluation.logic_score if evaluation else "",
            evaluation.appropriateness_score if evaluation else "",
            evaluation.impact_score if evaluation else "",
            evaluation.relevance_score if evaluation else "",
            evaluation.concision_score if evaluation else "",
            evaluation.summary if evaluation else "尚未生成评分",
            training.started_at.isoformat(),
        ])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="learner_training_reports.csv"'})


@router.get("/learners/{user_id}/report")
async def learner_report(user_id: str, _: AdminUser, session: DbSession) -> dict:
    learner = await session.get(User, user_id)
    if learner is None:
        raise not_found("学员")
    evaluations = (await session.scalars(select(Evaluation).where(Evaluation.user_id == user_id).order_by(Evaluation.created_at.desc()).limit(100))).all()
    keys = ("logic", "appropriateness", "impact", "relevance", "concision")
    dimensions = {key: round(sum(getattr(item, f"{key}_score") for item in evaluations) / len(evaluations), 2) for key in keys} if evaluations else {}
    return ok({
        "learner": {"id": learner.id, "name": learner.display_name, "email": learner.email, "active": learner.active},
        "trainingCount": int((await session.scalar(select(func.count()).select_from(TrainingSession).where(TrainingSession.user_id == user_id))) or 0),
        "evaluationCount": len(evaluations), "averageScore": round(sum(item.overall_score for item in evaluations) / len(evaluations), 1) if evaluations else 0,
        "dimensions": dimensions,
        "weakestDimension": min(dimensions, key=dimensions.get) if dimensions else None,
        "styleTags": [tag for item in evaluations for tag in (item.style_tags or [])],
        "trends": [{"date": item.created_at.date().isoformat(), "score": item.overall_score, "dimensions": {key: getattr(item, f"{key}_score") for key in keys}} for item in reversed(evaluations)],
    })


@router.get("/learners/{user_id}/report/export")
async def export_learner_report(user_id: str, _: AdminUser, session: DbSession) -> StreamingResponse:
    learner = await session.get(User, user_id)
    if learner is None:
        raise not_found("学员")
    rows = (await session.execute(select(TrainingSession, Scene, Evaluation).join(Scene, Scene.id == TrainingSession.scene_id).outerjoin(Evaluation, Evaluation.session_id == TrainingSession.id).where(TrainingSession.user_id == user_id).order_by(TrainingSession.started_at.desc()))).all()
    output = StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["学员", "场景", "轮次", "综合分", "逻辑性", "得体性", "感染力", "针对性", "简洁度", "评分摘要", "时间"])
    for training, scene, evaluation in rows:
        writer.writerow([learner.display_name, scene.title, training.current_round, evaluation.overall_score if evaluation else "", evaluation.logic_score if evaluation else "", evaluation.appropriateness_score if evaluation else "", evaluation.impact_score if evaluation else "", evaluation.relevance_score if evaluation else "", evaluation.concision_score if evaluation else "", evaluation.summary if evaluation else "尚未生成评分", training.started_at.isoformat()])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="learner_{user_id}_report.csv"'})

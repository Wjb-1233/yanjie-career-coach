import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.core.responses import ok
from app.core.security import AdminUser, hash_password
from app.db.base import get_session
from app.db.models import (
    PasswordResetRequest,
    Course,
    Evaluation,
    EvaluationEvidence,
    MistakeState,
    RefreshToken,
    Scene,
    TrainingSession,
    User,
)
from app.features.admin.schemas import CourseAdminInput, SceneAdminInput, UserAdminUpdate
from app.features.scenes.taxonomy import normalize_bank

DEFAULT_RESET_PASSWORD = "123456789"

router = APIRouter(prefix="/admin", tags=["后台管理"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("/overview")
async def overview(_: AdminUser, session: DbSession) -> dict:
    async def count(model: type) -> int:
        return int((await session.scalar(select(func.count()).select_from(model))) or 0)

    average = await session.scalar(select(func.avg(Evaluation.overall_score)))
    return ok({
        "users": int((await session.scalar(
            select(func.count()).select_from(User).where(User.role == "STUDENT")
        )) or 0),
        "activeUsers": int((await session.scalar(
            select(func.count()).select_from(User).where(User.active.is_(True), User.role == "STUDENT")
        )) or 0),
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


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, _: AdminUser, session: DbSession) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("用户")
    if user.role == "ADMIN":
        raise AppError(422, "CANNOT_RESET_ADMIN", "管理员密码请在本人的个人资料页修改")
    temporary = DEFAULT_RESET_PASSWORD
    user.password_hash = hash_password(temporary)
    await session.execute(
        RefreshToken.__table__.delete().where(RefreshToken.user_id == user.id)
    )
    await session.commit()
    return ok({"temporaryPassword": temporary})


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
    if user.role == "ADMIN" and changes.get("active") is False:
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


async def scene_coverage_stats(session: DbSession) -> dict[str, tuple[int, int]]:
    rows = (
        await session.execute(
            select(TrainingSession.scene_id, TrainingSession.covered_count)
        )
    ).all()
    stats: dict[str, tuple[int, int]] = {}
    for scene_id, covered in rows:
        total, with_cover = stats.get(scene_id, (0, 0))
        stats[scene_id] = (total + 1, with_cover + (1 if (covered or 0) > 0 else 0))
    return stats


@router.get("/scenes")
async def scenes(_: AdminUser, session: DbSession) -> dict:
    rows = (await session.scalars(select(Scene).order_by(Scene.created_at.desc()))).all()
    stats = await scene_coverage_stats(session)
    return ok([{
        "id": item.id, "category": item.category, "title": item.title,
        "industry": item.industry, "position": item.position, "roleName": item.role_name,
        "difficulty": item.difficulty, "background": item.background, "goal": item.goal,
        "tags": item.tags, "openingLine": item.opening_line,
        "coreIdea": item.core_idea or "", "questionBank": normalize_bank(item.question_bank), "active": item.active,
        "sessionCount": stats.get(item.id, (0, 0))[0],
        "coveredSessionCount": stats.get(item.id, (0, 0))[1],
    } for item in rows])


@router.post("/scenes", status_code=201)
async def create_scene(body: SceneAdminInput, _: AdminUser, session: DbSession) -> dict:
    payload = body.model_dump()
    payload["question_bank"] = [item.model_dump() for item in body.question_bank]
    scene = Scene(id=f"scene-{uuid4().hex}", **payload)
    session.add(scene)
    await session.commit()
    return ok({"id": scene.id})


@router.patch("/scenes/{scene_id}")
async def update_scene(scene_id: str, body: SceneAdminInput, _: AdminUser, session: DbSession) -> dict:
    scene = await session.get(Scene, scene_id)
    if scene is None:
        raise not_found("面试场景")
    payload = body.model_dump()
    payload["question_bank"] = [item.model_dump() for item in body.question_bank]
    for key, value in payload.items():
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
    writer.writerow(["学员", "邮箱", "场景", "状态", "轮次", "综合分", "逻辑性", "得体性", "正确性", "针对性", "简洁度", "评分摘要", "开始时间"])
    for training, scene, user, evaluation in rows:
        writer.writerow([
            user.display_name, user.email, scene.title, training.status,
            training.current_round, evaluation.overall_score if evaluation else "",
            evaluation.logic_score if evaluation else "",
            evaluation.appropriateness_score if evaluation else "",
            evaluation.correctness_score if evaluation else "",
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
    keys = ("logic", "appropriateness", "correctness", "relevance", "concision")
    dimensions = {key: round(sum(getattr(item, f"{key}_score") for item in evaluations) / len(evaluations), 2) for key in keys} if evaluations else {}
    return ok({
        "learner": {
            "id": learner.id,
            "name": learner.display_name,
            "email": learner.email,
            "active": learner.active,
            "bio": learner.bio or "",
            "avatar": learner.avatar,
            "createdAt": learner.created_at.isoformat() if learner.created_at else None,
        },
        "trainingCount": int((await session.scalar(
            select(func.count()).select_from(TrainingSession).where(
                TrainingSession.user_id == user_id, TrainingSession.current_round > 0
            )
        )) or 0),
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
    writer.writerow(["学员", "场景", "轮次", "综合分", "逻辑性", "得体性", "正确性", "针对性", "简洁度", "评分摘要", "时间"])
    for training, scene, evaluation in rows:
        writer.writerow([learner.display_name, scene.title, training.current_round, evaluation.overall_score if evaluation else "", evaluation.logic_score if evaluation else "", evaluation.appropriateness_score if evaluation else "", evaluation.correctness_score if evaluation else "", evaluation.relevance_score if evaluation else "", evaluation.concision_score if evaluation else "", evaluation.summary if evaluation else "尚未生成评分", training.started_at.isoformat()])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="learner_{user_id}_report.csv"'})

@router.get("/question-coverage")
async def question_coverage(_: AdminUser, session: DbSession) -> dict:
    rows = (await session.scalars(select(Scene))).all()
    stats = await scene_coverage_stats(session)
    items = []
    for scene in rows:
        bank = normalize_bank(scene.question_bank)
        total, with_cover = stats.get(scene.id, (0, 0))
        items.append({
            "sceneId": scene.id,
            "title": scene.title,
            "category": scene.category,
            "questions": len(bank),
            "sessions": total,
            "coveredSessions": with_cover,
        })
    with_bank = [item for item in items if item["questions"] > 0]
    return ok({
        "totalScenes": len(items),
        "scenesWithBank": len(with_bank),
        "scenesWithoutBank": len(items) - len(with_bank),
        "totalQuestions": sum(item["questions"] for item in items),
        "neverTrained": len([item for item in items if item["sessions"] == 0]),
        "items": sorted(items, key=lambda x: (x["sessions"], -x["questions"])),
    })

DIMENSION_SCORE_FIELD = {
    "logic": "logic_score",
    "appropriateness": "appropriateness_score",
    "correctness": "correctness_score",
    "relevance": "relevance_score",
    "concision": "concision_score",
}

DIMENSION_NAMES = {
    "logic": "逻辑性",
    "appropriateness": "得体性",
    "correctness": "正确性",
    "relevance": "针对性",
    "concision": "简洁度",
}


@router.get("/mistake-stats")
async def mistake_stats(_: AdminUser, session: DbSession) -> dict:
    evaluations = (await session.scalars(select(Evaluation))).all()
    if not evaluations:
        return ok({"total": 0, "byDimension": [], "byScene": [], "resolvedRate": 0})
    by_id = {item.id: item for item in evaluations}
    evidence_rows = (
        await session.scalars(
            select(EvaluationEvidence).where(
                EvaluationEvidence.evaluation_id.in_(list(by_id))
            )
        )
    ).all()
    sessions = {
        row.id: row
        for row in (
            await session.scalars(
                select(TrainingSession).where(
                    TrainingSession.id.in_([item.session_id for item in evaluations])
                )
            )
        ).all()
    }
    scenes = {
        row.id: row
        for row in (
            await session.scalars(
                select(Scene).where(Scene.id.in_([item.scene_id for item in sessions.values()]))
            )
        ).all()
    }

    dimension_counts: dict[str, int] = {name: 0 for name in DIMENSION_NAMES.values()}
    scene_counts: dict[str, int] = {}
    total = 0
    for row in evidence_rows:
        evaluation = by_id.get(row.evaluation_id)
        if evaluation is None:
            continue
        score = getattr(evaluation, DIMENSION_SCORE_FIELD.get(row.dimension, "logic_score"), 5)
        if score > 3:
            continue
        total += 1
        label = DIMENSION_NAMES.get(row.dimension, row.dimension)
        dimension_counts[label] = dimension_counts.get(label, 0) + 1
        training = sessions.get(evaluation.session_id)
        scene = scenes.get(training.scene_id) if training else None
        title = scene.title if scene else "历史场景"
        scene_counts[title] = scene_counts.get(title, 0) + 1

    states = (await session.scalars(select(MistakeState))).all()
    resolved_rate = 0.0
    if states:
        resolved_rate = round(
            len([item for item in states if item.status == "RESOLVED"]) / max(len(states), 1), 3
        )

    return ok({
        "total": total,
        "byDimension": [
            {"name": name, "count": count}
            for name, count in sorted(dimension_counts.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "byScene": [
            {"name": name, "count": count}
            for name, count in sorted(scene_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ],
        "resolvedRate": resolved_rate,
    })

@router.get("/password-requests")
async def password_requests(_: AdminUser, session: DbSession) -> dict:
    rows = (
        await session.scalars(
            select(PasswordResetRequest)
            .where(PasswordResetRequest.status == "PENDING")
            .order_by(PasswordResetRequest.created_at.desc())
        )
    ).all()
    if not rows:
        return ok([])
    users = {
        user.id: user
        for user in (
            await session.scalars(select(User).where(User.id.in_([row.user_id for row in rows])))
        ).all()
    }
    return ok([
        {
            "id": row.id,
            "userId": row.user_id,
            "name": users[row.user_id].display_name if row.user_id in users else "已删除学员",
            "email": users[row.user_id].email if row.user_id in users else "",
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ])


@router.post("/password-requests/{request_id}/resolve")
async def resolve_password_request(request_id: str, _: AdminUser, session: DbSession) -> dict:
    row = await session.get(PasswordResetRequest, request_id)
    if row is None:
        raise not_found("重置申请")
    user = await session.get(User, row.user_id)
    if user is None:
        row.status = "DISMISSED"
        await session.commit()
        raise not_found("学员")
    temporary = DEFAULT_RESET_PASSWORD
    user.password_hash = hash_password(temporary)
    await session.execute(
        RefreshToken.__table__.delete().where(RefreshToken.user_id == user.id)
    )
    row.status = "DONE"
    row.handled_at = datetime.now(timezone.utc)
    await session.commit()
    return ok({"temporaryPassword": temporary, "name": user.display_name})


@router.post("/password-requests/{request_id}/dismiss")
async def dismiss_password_request(request_id: str, _: AdminUser, session: DbSession) -> dict:
    row = await session.get(PasswordResetRequest, request_id)
    if row is None:
        raise not_found("重置申请")
    row.status = "DISMISSED"
    row.handled_at = datetime.now(timezone.utc)
    await session.commit()
    return ok({"ok": True})


@router.get("/learners")
async def learners(_: AdminUser, session: DbSession) -> dict:
    users = (await session.scalars(select(User).where(User.role == "STUDENT"))).all()
    sessions = (
        await session.execute(
            select(
                TrainingSession.user_id,
                TrainingSession.status,
                TrainingSession.current_round,
                TrainingSession.started_at,
                TrainingSession.finished_at,
            )
        )
    ).all()
    evaluations = (
        await session.execute(
            select(Evaluation.user_id, Evaluation.overall_score, Evaluation.created_at)
        )
    ).all()

    stat: dict[str, dict] = {}
    for user_id, status, rounds, started_at, finished_at in sessions:
        if not rounds:
            continue
        item = stat.setdefault(user_id, {"sessions": 0, "finished": 0, "last": None})
        item["sessions"] += 1
        if status == "FINISHED":
            item["finished"] += 1
        moment = finished_at or started_at
        if moment and (item["last"] is None or moment > item["last"]):
            item["last"] = moment

    scores: dict[str, list[float]] = {}
    scored_at: dict[str, object] = {}
    for user_id, overall, created_at in evaluations:
        scores.setdefault(user_id, []).append(overall)
        moment = scored_at.get(user_id)
        if moment is None or (created_at and created_at > moment):
            scored_at[user_id] = created_at

    rows = []
    for user in users:
        item = stat.get(user.id, {"sessions": 0, "finished": 0, "last": None})
        values = scores.get(user.id, [])
        rows.append(
            {
                "userId": user.id,
                "name": user.display_name,
                "email": user.email,
                "active": user.active,
                "sessions": item["sessions"],
                "finished": item["finished"],
                "averageScore": round(sum(values) / len(values), 1) if values else None,
                "lastTrainedAt": (
                    (item["last"] or scored_at.get(user.id)).isoformat()
                    if (item["last"] or scored_at.get(user.id))
                    else None
                ),
            }
        )
    rows.sort(key=lambda row: row["lastTrainedAt"] or "", reverse=True)
    return ok(rows)

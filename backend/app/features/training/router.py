import csv
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi import Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser, StreamingUser
from app.db.base import get_session
from app.db.models import Evaluation, Scene, TrainingSession
from app.features.training.schemas import CreateSessionRequest, SendMessageRequest
from app.features.training.service import (
    create_training_session,
    delete_training_session,
    delete_resume_context,
    finish_session,
    get_training_session,
    list_training_sessions,
    stream_reply,
    complete_reply,
    set_session_archived,
)
from app.features.evaluations.service import evaluate_session
from app.infrastructure.rate_limit import limit_model_user
from app.features.training.resume import MAX_RESUME_BYTES, parse_resume
from app.db.models import ResumeContext

router = APIRouter(prefix="/training-sessions", tags=["情景训练"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=201)
async def create(body: CreateSessionRequest, user: CurrentUser, session: DbSession) -> dict:
    result = await create_training_session(session, user.id, body.scene_id)
    return ok(result.model_dump(by_alias=True))


@router.post("/with-resume", status_code=201)
async def create_with_resume(
    user: CurrentUser,
    session: DbSession,
    scene_id: Annotated[str, Form(alias="sceneId")],
    file: Annotated[UploadFile, File()],
) -> dict:
    try:
        content = await file.read(MAX_RESUME_BYTES + 1)
    finally:
        await file.close()
    filename, resume_text = parse_resume(file.filename or "", content)
    await limit_model_user(user.id)
    result = await create_training_session(session, user.id, scene_id, filename, resume_text)
    return ok(result.model_dump(by_alias=True))


@router.get("")
async def history(
    user: CurrentUser,
    session: DbSession,
    q: str | None = None,
    status: str | None = None,
    archived: bool = False,
) -> dict:
    items = await list_training_sessions(session, user.id, q, status, archived)
    return ok([item.model_dump(by_alias=True) for item in items])


@router.get("/export")
async def export_reports(user: CurrentUser, session: DbSession) -> StreamingResponse:
    rows = (
        await session.execute(
            select(TrainingSession, Scene, Evaluation)
            .join(Scene, Scene.id == TrainingSession.scene_id)
            .outerjoin(Evaluation, Evaluation.session_id == TrainingSession.id)
            .where(TrainingSession.user_id == user.id)
            .order_by(TrainingSession.started_at.desc())
            .limit(500)
        )
    ).all()
    output = StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "场景", "状态", "开始时间", "完成时间", "训练轮次", "综合分",
        "逻辑性", "得体性", "感染力", "针对性", "简洁度", "评分摘要", "建议",
    ])
    for training, scene, evaluation in rows:
        writer.writerow([
            scene.title,
            "已完成" if training.status == "FINISHED" else "进行中",
            training.started_at.isoformat(),
            training.finished_at.isoformat() if training.finished_at else "",
            training.current_round,
            evaluation.overall_score if evaluation else "",
            evaluation.logic_score if evaluation else "",
            evaluation.appropriateness_score if evaluation else "",
            evaluation.impact_score if evaluation else "",
            evaluation.relevance_score if evaluation else "",
            evaluation.concision_score if evaluation else "",
            evaluation.summary if evaluation else "尚未生成报告",
            "；".join(item.get("rewrite", "") for item in (evaluation.suggestions or [])) if evaluation else "",
        ])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="training_reports.csv"'},
    )


@router.get("/{session_id}")
async def get_one(session_id: str, user: CurrentUser, session: DbSession) -> dict:
    result = await get_training_session(session, user.id, session_id)
    return ok(result.model_dump(by_alias=True))


@router.delete("/{session_id}", status_code=204)
async def delete_one(session_id: str, user: CurrentUser, session: DbSession) -> Response:
    await delete_training_session(session, user.id, session_id)
    return Response(status_code=204)


@router.delete("/{session_id}/resume", status_code=204)
async def delete_resume(session_id: str, user: CurrentUser, session: DbSession) -> Response:
    await delete_resume_context(session, user.id, session_id)
    return Response(status_code=204)


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str, body: SendMessageRequest, user: StreamingUser
) -> StreamingResponse:
    await limit_model_user(user.id)
    return StreamingResponse(
        stream_reply(session_id, user.id, body.content, body.finish_after_reply),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/messages/complete")
async def send_message_complete(
    session_id: str, body: SendMessageRequest, user: CurrentUser
) -> dict:
    await limit_model_user(user.id)
    result = await complete_reply(session_id, user.id, body.content, body.finish_after_reply)
    return ok(result.model_dump(by_alias=True))


@router.post("/{session_id}/finish")
async def finish(
    session_id: str,
    user: CurrentUser,
    session: DbSession,
    create_plan: bool = True,
) -> dict:
    await limit_model_user(user.id)
    await finish_session(session, user.id, session_id)
    evaluation = await evaluate_session(session, user.id, session_id, create_plan=create_plan)
    return ok(evaluation.model_dump(by_alias=True))


@router.post("/{session_id}/restart", status_code=201)
async def restart(session_id: str, user: CurrentUser, session: DbSession) -> dict:
    old = await get_training_session(session, user.id, session_id)
    resume = await session.get(ResumeContext, session_id)
    if resume:
        await limit_model_user(user.id)
    result = await create_training_session(
        session, user.id, old.scene_id,
        resume.filename if resume else None,
        resume.content if resume else None,
    )
    return ok(result.model_dump(by_alias=True))


@router.post("/{session_id}/archive")
async def archive(session_id: str, user: CurrentUser, session: DbSession) -> dict:
    training = await set_session_archived(session, user.id, session_id, True)
    return ok({"id": training.id, "archivedAt": training.archived_at})


@router.post("/{session_id}/restore")
async def restore(session_id: str, user: CurrentUser, session: DbSession) -> dict:
    training = await set_session_archived(session, user.id, session_id, False)
    return ok({"id": training.id, "archivedAt": None})


import csv
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.core.schemas import ApiModel
from fastapi import Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ok
from app.core.security import CurrentUser, StreamingUser
from app.db.base import get_session
from app.db.models import Evaluation, Scene, TrainingSession
from app.features.training.schemas import (
    CreateSessionRequest,
    SelfReviewRequest,
    SendMessageRequest,
    TranscriptEditRequest,
)
from app.features.auth.email_verify import require_verified
from app.features.training.service import (
    create_training_session,
    delete_training_session,
    delete_resume_context,
    finish_session,
    get_training_session,
    list_training_sessions,
    stream_reply,
    complete_reply,
    rewrite_flagged_message,
    set_job_description,
    clear_job_description,
    set_session_archived,
)
from app.features.evaluations.service import evaluate_session, list_mistakes, set_mistake_state
from app.infrastructure.rate_limit import limit_model_user
from app.features.training.resume import MAX_RESUME_BYTES, parse_resume
from app.db.models import ResumeContext

router = APIRouter(prefix="/training-sessions", tags=["情景训练"])


class JobDescriptionRequest(BaseModel):
    jd_text: str = Field(min_length=20, max_length=4000)
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("/mistakes")
async def mistakes(
    user: CurrentUser, session: DbSession, page: int = 1, size: int = 8, include_resolved: bool = False
) -> dict:
    page = max(1, min(page, 500))
    size = max(1, min(size, 50))
    return ok(
        await list_mistakes(
            session,
            user.id,
            limit=size,
            offset=(page - 1) * size,
            include_resolved=include_resolved,
        )
    )


class MistakeStateRequest(ApiModel):
    session_id: str = Field(min_length=8, max_length=36)
    round_no: int = Field(ge=0, le=12)
    dimension: str = Field(min_length=1, max_length=20)
    status: str = Field(pattern="^(PENDING|RESOLVED)$")


@router.patch("/mistakes/state")
async def update_mistake_state(body: MistakeStateRequest, user: CurrentUser, session: DbSession) -> dict:
    result = await set_mistake_state(
        session, user.id, body.session_id, body.round_no, body.dimension, body.status
    )
    return ok(result)


@router.post("", status_code=201)
async def create(body: CreateSessionRequest, user: CurrentUser, session: DbSession) -> dict:
    require_verified(user)
    result = await create_training_session(
        session, user.id, body.scene_id, mode=body.mode, plan_id=body.plan_id, task_key=body.task_key,
        depth=body.depth,
    )
    return ok(result.model_dump(by_alias=True))


@router.post("/with-resume", status_code=201)
async def create_with_resume(
    user: CurrentUser,
    session: DbSession,
    scene_id: Annotated[str, Form(alias="sceneId")],
    file: Annotated[UploadFile, File()],
    depth: Annotated[str, Form()] = "STANDARD",
) -> dict:
    try:
        content = await file.read(MAX_RESUME_BYTES + 1)
    finally:
        await file.close()
    require_verified(user)
    filename, resume_text = parse_resume(file.filename or "", content)
    await limit_model_user(user.id)
    result = await create_training_session(
        session, user.id, scene_id, filename, resume_text,
        depth=depth if depth in {"STANDARD", "THREE_LAYER", "PRESSURE"} else "STANDARD",
    )
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
        "内容与逻辑", "贴合问题", "信息完整", "表达干净", "评分摘要", "建议",
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
            evaluation.relevance_score if evaluation else "",
            evaluation.correctness_score if evaluation else "",
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
    training = await finish_session(session, user.id, session_id)
    evaluation = await evaluate_session(session, user.id, session_id, create_plan=create_plan)
    await auto_complete_plan_task(session, user.id, training, evaluation)
    return ok(evaluation.model_dump(by_alias=True))


async def auto_complete_plan_task(session: DbSession, user_id: str, training, evaluation) -> None:
    """从计划任务发起的训练，结束后自动勾掉任务；不满足条件时静默跳过。"""
    if not training.plan_id or not training.task_key:
        return
    from app.core.errors import AppError

    from app.features.plans.service import complete_training_task

    try:
        await complete_training_task(session, user_id, training.plan_id, training.task_key, training.id)
    except AppError:
        # 轮次不足或已有更好记录时，保持任务未完成，前端会给出提示
        return


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


@router.post("/{session_id}/messages/{round_no}/rewrite")
async def rewrite_message(session_id: str, round_no: int, user: CurrentUser, session: DbSession) -> dict:
    await limit_model_user(user.id)
    result = await rewrite_flagged_message(session, user.id, session_id, round_no)
    return ok(result.model_dump(by_alias=True))


@router.post("/{session_id}/jd")
async def apply_job_description(
    session_id: str, body: JobDescriptionRequest, user: CurrentUser, session: DbSession
) -> dict:
    await limit_model_user(user.id)
    result = await set_job_description(session, user.id, session_id, body.jd_text.strip())
    return ok(result.model_dump(by_alias=True))


@router.delete("/{session_id}/jd")
async def remove_job_description(session_id: str, user: CurrentUser, session: DbSession) -> dict:
    result = await clear_job_description(session, user.id, session_id)
    return ok(result.model_dump(by_alias=True))


@router.put("/{session_id}/self-review")
async def save_self_review(
    session_id: str, body: SelfReviewRequest, user: CurrentUser, session: DbSession
) -> dict:
    """视频面试的逐题自评清单（V-06 的自评部分），存到会话 delivery 里。"""
    from sqlalchemy.orm.attributes import flag_modified

    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user.id:
        raise not_found("训练会话")
    delivery = dict(training.delivery or {})
    delivery["selfReview"] = [item.model_dump(by_alias=True) for item in body.items]
    training.delivery = delivery
    flag_modified(training, "delivery")
    await session.commit()
    return ok({"selfReview": delivery["selfReview"]})


@router.patch("/{session_id}/transcript/{round_no}")
async def edit_transcript(
    session_id: str,
    round_no: int,
    body: TranscriptEditRequest,
    user: CurrentUser,
    session: DbSession,
) -> dict:
    """A-02：人工修正某一轮转写，标记需重新评分。"""
    from sqlalchemy.orm.attributes import flag_modified

    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user.id:
        raise not_found("训练会话")
    if training.status != "FINISHED":
        raise AppError(422, "TRANSCRIPT_NOT_READY", "训练结束后才能修正转写")

    delivery = dict(training.delivery or {})
    transcript = [dict(item) for item in (delivery.get("transcript") or [])]
    target = next((item for item in transcript if item.get("roundNo") == round_no), None)
    if target is None:
        raise not_found("该轮转写")

    target["text"] = body.text.strip()
    target["edited"] = True
    delivery["transcript"] = transcript
    delivery["rescoreRequired"] = True
    training.delivery = delivery
    flag_modified(training, "delivery")

    message = await session.scalar(
        select(Message).where(
            Message.session_id == session_id,
            Message.speaker == "USER",
            Message.round_no == round_no,
        )
    )
    if message is not None:
        message.content = target["text"]

    await session.commit()
    return ok({"transcript": transcript, "rescoreRequired": True})


@router.get("/{session_id}/same-question/{round_no}")
async def same_question(
    session_id: str, round_no: int, user: CurrentUser, session: DbSession
) -> dict:
    """同一道题在不同场次的回答，用于横向对比结构差异。"""
    from app.features.training.comparison import same_question_attempts

    attempts = await same_question_attempts(session, user.id, session_id, round_no)
    return ok({"attempts": attempts})

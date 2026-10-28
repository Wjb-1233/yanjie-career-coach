import asyncio
import json
import logging
from collections.abc import AsyncIterator

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, not_found
from app.db.base import session_factory
from app.db.models import Evaluation, EvaluationEvidence, Message, ResumeContext, Scene, TrainingPlan, TrainingSession
from app.features.scenes.service import get_scene
from app.features.training.graph import conversation_graph
from app.features.training.resume import opening_question
from app.features.training.schemas import MessageView, SessionView, TrainingHistoryItem, TurnReplyView
from app.infrastructure.knowledge import knowledge_store
from app.infrastructure.llm import llm_gateway
from app.infrastructure.state_store import state_store

logger = logging.getLogger(__name__)


async def create_training_session(
    session: AsyncSession,
    user_id: str,
    scene_id: str,
    resume_filename: str | None = None,
    resume_text: str | None = None,
) -> SessionView:
    scene = await get_scene(session, scene_id)
    if resume_text and scene.category == "基础能力提升":
        raise AppError(422, "RESUME_NOT_APPLICABLE", "五维基础练习不需要上传简历，请直接开始训练")
    opening_line = scene.opening_line
    opening_degraded = False
    if resume_filename and resume_text:
        opening_line, opening_degraded = await opening_question(scene, resume_text)
    training = TrainingSession(
        user_id=user_id,
        scene_id=scene.id,
        max_rounds=settings.max_training_rounds,
    )
    session.add(training)
    await session.flush()
    opening = Message(
        session_id=training.id,
        round_no=0,
        speaker="AI",
        content=opening_line,
    )
    session.add(opening)
    if resume_filename and resume_text:
        session.add(ResumeContext(
            session_id=training.id,
            filename=resume_filename,
            content=resume_text,
            opening_degraded=opening_degraded,
        ))
    await session.commit()
    await state_store.set(
        training.id,
        {"stage": training.stage, "roundNo": 0, "maxRounds": training.max_rounds},
    )
    return SessionView(
        id=training.id,
        scene_id=scene.id,
        scene_title=scene.title,
        status=training.status,
        stage=training.stage,
        current_round=training.current_round,
        max_rounds=training.max_rounds,
        started_at=training.started_at,
        finished_at=training.finished_at,
        resume_filename=resume_filename,
        resume_opening_degraded=opening_degraded,
        messages=[MessageView.model_validate(opening)],
    )


async def get_training_session(
    session: AsyncSession, user_id: str, session_id: str
) -> SessionView:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")
    scene = await session.get(Scene, training.scene_id)
    resume = await session.get(ResumeContext, training.id)
    messages = (
        await session.scalars(
            select(Message)
            .where(Message.session_id == training.id)
            .order_by(Message.created_at, Message.speaker)
        )
    ).all()
    return SessionView(
        id=training.id,
        scene_id=training.scene_id,
        scene_title=scene.title if scene else None,
        status=training.status,
        stage=training.stage,
        current_round=training.current_round,
        max_rounds=training.max_rounds,
        started_at=training.started_at,
        finished_at=training.finished_at,
        archived_at=training.archived_at,
        resume_filename=resume.filename if resume else None,
        resume_opening_degraded=resume.opening_degraded if resume else False,
        messages=[MessageView.model_validate(item) for item in messages],
    )


async def list_training_sessions(
    session: AsyncSession,
    user_id: str,
    query: str | None = None,
    status: str | None = None,
    archived: bool = False,
) -> list[TrainingHistoryItem]:
    statement = (
        select(TrainingSession, Scene, Evaluation)
        .join(Scene, Scene.id == TrainingSession.scene_id)
        .outerjoin(Evaluation, Evaluation.session_id == TrainingSession.id)
        .where(TrainingSession.user_id == user_id)
    )
    statement = statement.where(
        TrainingSession.archived_at.is_not(None) if archived else TrainingSession.archived_at.is_(None)
    )
    if status in {"ACTIVE", "FINISHED"}:
        statement = statement.where(TrainingSession.status == status)
    if query and query.strip():
        term = f"%{query.strip().lower()}%"
        statement = statement.where(func.lower(Scene.title).like(term))
    rows = (
        await session.execute(
            statement.order_by(TrainingSession.started_at.desc()).limit(100)
        )
    ).all()
    return [
        TrainingHistoryItem(
            id=training.id,
            scene_id=training.scene_id,
            scene_title=scene.title,
            status=training.status,
            current_round=training.current_round,
            max_rounds=training.max_rounds,
            started_at=training.started_at,
            finished_at=training.finished_at,
            overall_score=evaluation.overall_score if evaluation else None,
            evaluation_degraded=evaluation.degraded if evaluation else False,
            archived_at=training.archived_at,
        )
        for training, scene, evaluation in rows
    ]


async def set_session_archived(
    session: AsyncSession, user_id: str, session_id: str, archived: bool
) -> TrainingSession:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")
    if archived and training.status != "FINISHED":
        raise AppError(422, "SESSION_NOT_FINISHED", "请先完成训练，再归档这条记录")
    from app.db.models import now

    training.archived_at = now() if archived else None
    await session.commit()
    return training


async def delete_training_session(session: AsyncSession, user_id: str, session_id: str) -> None:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")

    plans = (
        await session.scalars(select(TrainingPlan).where(TrainingPlan.user_id == user_id))
    ).all()
    for plan in plans:
        tasks = [dict(task) for task in (plan.tasks or [])]
        if any(task.get("sourceSessionId") == session_id for task in tasks):
            await session.delete(plan)
            continue
        affected = next(
            (index for index, task in enumerate(tasks)
             if task.get("actionType") in {"TRAINING", "RETEST"}
             and task.get("evidence") == session_id),
            None,
        )
        if affected is not None:
            for task in tasks[affected:]:
                task.update(completed=False, completedAt=None, evidence=None)
                if task.get("actionType") == "REWRITE":
                    task.update(rewriteFeedback=None, rewritePassed=False, rewriteDegraded=False)
            plan.tasks = tasks
            plan.status = "ACTIVE"

    evaluation = await session.scalar(select(Evaluation).where(Evaluation.session_id == session_id))
    if evaluation is not None:
        await session.execute(delete(EvaluationEvidence).where(EvaluationEvidence.evaluation_id == evaluation.id))
    await session.execute(delete(ResumeContext).where(ResumeContext.session_id == session_id))
    await session.execute(delete(Message).where(Message.session_id == session_id))
    await session.execute(delete(Evaluation).where(Evaluation.session_id == session_id))
    await session.delete(training)
    await session.commit()
    try:
        await state_store.delete(session_id)
    except Exception as exc:
        logger.warning("training.state_cleanup_failed error_type=%s", type(exc).__name__)


async def delete_resume_context(session: AsyncSession, user_id: str, session_id: str) -> None:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")
    await session.execute(delete(ResumeContext).where(ResumeContext.session_id == session_id))
    await session.commit()


async def finish_session(session: AsyncSession, user_id: str, session_id: str) -> TrainingSession:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")
    if training.status == "ACTIVE":
        if training.current_round < 2:
            raise AppError(422, "TRAINING_ROUNDS_INSUFFICIENT", "至少完成 2 轮对话才能生成有效评分和训练计划")
        from app.db.models import now

        training.status = "FINISHED"
        training.finished_at = now()
        await session.commit()
    await state_store.delete(session_id)
    return training


async def stream_reply(session_id: str, user_id: str, user_text: str, finish_after_reply: bool = False) -> AsyncIterator[str]:
    async with session_factory() as db:
        training = await db.get(TrainingSession, session_id)
        if training is None or training.user_id != user_id:
            yield sse("error", {"message": "训练会话不存在"})
            return
        if training.status != "ACTIVE" or training.current_round >= training.max_rounds:
            yield sse("error", {"message": "本次训练已结束，请查看评分报告"})
            return
        if finish_after_reply and training.current_round < 1:
            yield sse("error", {"message": "至少回答 2 轮后才能提前结束"})
            return
        scene = await db.get(Scene, training.scene_id)
        resume = await db.get(ResumeContext, training.id)
        history_rows = (
            await db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at)
            )
        ).all()
        graph_state = await conversation_graph.ainvoke(
            {
                "round_no": training.current_round,
                "max_rounds": training.max_rounds,
                "user_text": user_text,
                "scene_title": scene.title,
                "scene_id": scene.id,
                "scene_category": scene.category,
                "scene_difficulty": scene.difficulty,
                "role_name": scene.role_name,
                "scene_background": scene.background,
                "scene_goal": scene.goal,
                "resume_text": resume.content if resume else "",
                "stage": training.stage,
                "flags": [],
                "should_finish": False,
                "finish_after_reply": finish_after_reply,
                "prompt": "",
            }
        )
        user_message = Message(
            session_id=session_id,
            round_no=graph_state["round_no"],
            speaker="USER",
            content=user_text,
            flagged=bool(graph_state["flags"]),
            flags=graph_state["flags"],
        )
        db.add(user_message)
        training.current_round = graph_state["round_no"]
        training.stage = graph_state["stage"]
        await db.commit()
        await state_store.set(
            session_id,
            {
                "stage": training.stage,
                "roundNo": training.current_round,
                "maxRounds": training.max_rounds,
                "flags": graph_state["flags"],
            },
        )
        yield sse(
            "meta",
            {
                "roundNo": training.current_round,
                "maxRounds": training.max_rounds,
                "stage": training.stage,
                "flags": graph_state["flags"],
            },
        )
        references = await knowledge_store.search(scene.title + user_text, 2)
        reference_text = "\n".join(f"{item.title}：{item.content}" for item in references)
        system_prompt = graph_state["prompt"] + f"\n可参考但不要直接复述的沟通原则：\n{reference_text}"
        messages = [
            {
                "role": "assistant" if item.speaker == "AI" else "user",
                "content": item.content,
            }
            for item in history_rows[-10:]
        ] + [{"role": "user", "content": user_text}]
        full_text = ""
        degraded = False
        if graph_state["should_finish"]:
            full_text = "谢谢你的回答。本场模拟到这里结束，现在可以查看五维评分和具体改进建议。"
            yield sse("token", {"content": full_text})
        else:
            try:
                stream = llm_gateway.stream_text(system_prompt, messages).__aiter__()
                first = await asyncio.wait_for(
                    anext(stream), timeout=settings.first_token_timeout_seconds
                )
                full_text += first
                yield sse("token", {"content": first})
                async for chunk in stream:
                    full_text += chunk
                    yield sse("token", {"content": chunk})
            except Exception as exc:
                logger.warning("training.llm_degraded error_type=%s", type(exc).__name__)
                degraded = True
                recovery_text = (
                    "\n（模型回复中断，请重新提问或继续训练。）"
                    if full_text else fallback_reply(graph_state["stage"], user_text, graph_state["flags"])
                )
                full_text += recovery_text
                for chunk in split_chunks(recovery_text):
                    yield sse("token", {"content": chunk})
                    await asyncio.sleep(0.025)
        assistant = Message(
            session_id=session_id,
            round_no=training.current_round,
            speaker="AI",
            content=full_text,
        )
        db.add(assistant)
        if graph_state["should_finish"]:
            from app.db.models import now

            training.status = "FINISHED"
            training.finished_at = now()
            await state_store.delete(session_id)
        await db.commit()
        yield sse(
            "done",
            {
                "messageId": assistant.id,
                "finished": training.status == "FINISHED",
                "degraded": degraded,
            },
        )


async def complete_reply(session_id: str, user_id: str, user_text: str, finish_after_reply: bool = False) -> TurnReplyView:
    """Collect the existing turn generator for clients that cannot consume SSE."""
    meta: dict = {}
    done: dict = {}
    chunks: list[str] = []
    async for block in stream_reply(session_id, user_id, user_text, finish_after_reply):
        lines = block.strip().splitlines()
        event = next((line[6:].strip() for line in lines if line.startswith("event:")), "")
        raw = next((line[5:].strip() for line in lines if line.startswith("data:")), "")
        if not event or not raw:
            continue
        payload = json.loads(raw)
        if event == "error":
            raise AppError(422, "TRAINING_TURN_FAILED", payload.get("message", "本轮训练未完成"))
        if event == "meta":
            meta = payload
        elif event == "token":
            chunks.append(payload.get("content", ""))
        elif event == "done":
            done = payload
    if not meta or not done:
        raise AppError(502, "TRAINING_TURN_INCOMPLETE", "面试官回复未完成，请刷新会话查看")
    return TurnReplyView(
        round_no=meta["roundNo"],
        stage=meta["stage"],
        flags=meta.get("flags", []),
        message_id=done["messageId"],
        content="".join(chunks),
        finished=done["finished"],
        degraded=done["degraded"],
    )


def fallback_reply(stage: str, user_text: str, flags: list[str]) -> str:
    if flags:
        return "我理解你的意思。请结合一个真实经历，说明当时的事实、你的具体行动和最终结果；不需要夸大或编造。"
    if stage == "OPENING":
        return "谢谢介绍。请选一个与你应聘岗位相关的真实经历，说明当时的背景、你的任务和承担的责任。"
    if stage == "DISCOVERY":
        return "你提到了采取的做法。请再说说最终结果是什么，如何判断结果有效，以及你从中学到了什么。"
    if stage == "CHALLENGE":
        return "如果团队成员不同意你的做法，或者结果没有达到预期，你会如何处理？请结合真实行动说明。"
    return "最后，请用几句话总结你与这个岗位的匹配点，并说说你希望进一步了解什么。"


def split_chunks(text: str, size: int = 8) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


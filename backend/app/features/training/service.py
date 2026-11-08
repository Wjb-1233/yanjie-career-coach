import asyncio
import json
import logging
from collections.abc import AsyncIterator

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, not_found
from app.db.base import session_factory
from app.features.recordings import storage
from app.db.models import Evaluation, EvaluationEvidence, Message, ResumeContext, Scene, TrainingPlan, TrainingSession
from app.features.scenes.service import get_scene
from app.features.scenes.taxonomy import normalize_bank
from app.features.training.job_match import build_match
from app.features.training.graph import conversation_graph
from app.features.training.resume import opening_question
from app.features.training.schemas import (
    MessageRewriteView,
    MessageView,
    SessionView,
    TrainingHistoryItem,
    TurnReplyView,
)
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
    mode: str = "STANDARD",
    plan_id: str | None = None,
    task_key: str | None = None,
    depth: str = "STANDARD",
    language: str = "zh",
) -> SessionView:
    scene = await get_scene(session, scene_id)
    if mode == "DRILL" and scene.difficulty != "进阶":
        raise AppError(422, "DRILL_REQUIRES_ADVANCED", "深挖模式只在进阶难度场景开放")
    if resume_text and scene.category == "基础能力提升":
        raise AppError(422, "RESUME_NOT_APPLICABLE", "四维基础练习不需要上传简历，请直接开始训练")
    opening_line = (scene.opening_line or "").strip()
    opening_degraded = False
    if language == "en":
        opening_line = "Hello, I'm your interviewer today. Please start with a brief self-introduction."
        opening_degraded = False
    elif resume_filename and resume_text:
        opening_line, opening_degraded = await opening_question(scene, resume_text)
    elif not opening_line:
        # 场景没有预设开场白时用确定性文案，不再请求模型，创建会话保持毫秒级
        opening_line = f"你好，我是{scene.role_name}，今天这场是{scene.category}，请先做个自我介绍。"
    if plan_id:
        plan = await session.get(TrainingPlan, plan_id)
        if plan is None or plan.user_id != user_id:
            raise not_found("训练计划")
        task = next((item for item in (plan.tasks or []) if item.get("key") == task_key), None)
        if task is None:
            raise not_found("计划任务")
        if task.get("completed"):
            raise AppError(409, "TASK_COMPLETED", "这项任务已经完成过了")

    training = TrainingSession(
        user_id=user_id,
        scene_id=scene.id,
        plan_id=plan_id,
        task_key=task_key,
        mode=mode if mode in {"STANDARD", "DRILL"} else "STANDARD",
        depth=depth if depth in {"STANDARD", "THREE_LAYER", "PRESSURE"} else "STANDARD",
        language=language if language in {"zh", "en"} else "zh",
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
        channel=training.channel,
        mode=training.mode or "STANDARD",
        depth=training.depth or "STANDARD",
        language=training.language or "zh",
        duration_seconds=training.duration_seconds,
        delivery=training.delivery,
        recording_url=storage.url_of(training.recording_path),
        started_at=training.started_at,
        finished_at=training.finished_at,
        resume_filename=resume_filename,
        resume_opening_degraded=opening_degraded,
        jd_text=training.jd_text,
        job_match=training.job_match,
        question_plan=normalize_bank(scene.question_bank),
        question_total=len(scene.question_bank or []),
        question_covered=training.covered_count,
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
        channel=training.channel,
        mode=training.mode or "STANDARD",
        depth=training.depth or "STANDARD",
        language=training.language or "zh",
        duration_seconds=training.duration_seconds,
        delivery=training.delivery,
        recording_url=storage.url_of(training.recording_path),
        started_at=training.started_at,
        finished_at=training.finished_at,
        archived_at=training.archived_at,
        resume_filename=resume.filename if resume else None,
        resume_opening_degraded=resume.opening_degraded if resume else False,
        jd_text=training.jd_text,
        job_match=training.job_match,
        question_plan=normalize_bank(training.question_plan or scene.question_bank),
        question_total=len((training.question_plan or scene.question_bank or [])),
        question_covered=training.covered_count,
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
            channel=training.channel,
            duration_seconds=training.duration_seconds,
            delivery={"engine": (training.delivery or {}).get("engine", "doubao")} if training.delivery else None,
            recording_url=storage.url_of(training.recording_path),
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
        # 计划由这次评分生成：保留计划，只断开来源，避免删一条记录连带毁掉整份计划
        if any(task.get("sourceSessionId") == session_id for task in tasks):
            for task in tasks:
                if task.get("sourceSessionId") == session_id:
                    task["sourceSessionId"] = None
            plan.tasks = tasks
        # SCENE / VIDEO 任务同样以会话为证据，删除后一并回退
        affected = next(
            (index for index, task in enumerate(tasks)
             if task.get("actionType") in {"TRAINING", "RETEST", "SCENE", "VIDEO"}
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
    recording = training.recording_path
    await session.delete(training)
    await session.commit()
    # 删除记录时同步清理录像，避免磁盘泄漏
    try:
        storage.remove(recording)
    except Exception as exc:  # noqa: BLE001
        logger.warning("training.recording_cleanup_failed error_type=%s", type(exc).__name__)
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
        if training.plan_id and training.channel != "VIDEO" and training.current_round < 6:
            raise AppError(
                422,
                "PLAN_ROUNDS_INSUFFICIENT",
                f"计划任务需要完成 6 轮对话，当前 {training.current_round} 轮",
            )
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
        bank = normalize_bank(training.question_plan) or normalize_bank(scene.question_bank)
        planned_question = ""
        if training.covered_count < len(bank):
            item = bank[training.covered_count]
            extra = " · ".join(x for x in [item.get("dimension"), item.get("difficulty")] if x)
            planned_question = f"{item['text']}（考察：{extra}）" if extra else item['text']
        graph_state = await conversation_graph.ainvoke(
            {
                "round_no": training.current_round,
                "max_rounds": training.max_rounds,
                "user_text": user_text,
                "scene_title": scene.title,
                "scene_id": scene.id,
                "scene_category": scene.category,
                "scene_difficulty": scene.difficulty,
                "mode": training.mode or "STANDARD",
                "depth": training.depth or "STANDARD",
                "language": training.language or "zh",
                "role_name": scene.role_name,
                "scene_background": scene.background,
                "scene_goal": scene.goal,
                "resume_text": resume.content if resume else "",
                "stage": training.stage,
                "flags": [],
                "should_finish": False,
                "finish_after_reply": finish_after_reply,
                "planned_question": planned_question,
                "core_idea": (scene.core_idea or scene.goal or ""),
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
        if planned_question:
            training.covered_count = min(training.covered_count + 1, len(bank))
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
            full_text = "谢谢你的回答。本场模拟到这里结束，现在可以结束训练并查看四维评分与改进建议。"
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


REWRITE_SYSTEM_PROMPT = """你是中文面试表达教练。用户这句话在模拟面试中被系统标记为需要改进的表达。
请在保留原意和真实事实的前提下，把这一句改写成更得体、更专业的面试说法；不得增加用户没有提供的经历、数据或成果。
只输出 JSON：{"rewrite":"改写后的完整句子","reason":"一句话说明改了哪里、为什么"}。"""

REWRITE_FALLBACK: dict[str, dict[str, str]] = {
    "命令式表达": {
        "你必须": "可以参考这个方向",
        "少废话": "我先说结论",
        "照我说的做": "可以按这个方案推进",
    },
    "推卸责任": {
        "不关我的事": "这部分我可以先确认一下",
        "都是他们的问题": "主要是协作环节上的问题",
        "我没办法": "我可以再去争取一下",
    },
    "绝对化表达": {
        "绝对不可能": "可能性不大",
        "你总是": "你平时",
        "你从来不": "你这次没有",
    },
}


def _fallback_rewrite(text: str, flags: list[str]) -> tuple[str, str]:
    rewritten = text
    changed: list[str] = []
    for label in flags:
        for source, target in REWRITE_FALLBACK.get(label, {}).items():
            if source in rewritten:
                rewritten = rewritten.replace(source, target)
                changed.append(label)
    if not changed:
        return f"我想换一种更稳妥的说法：{text}", "把语气改得更可协商，保留原有信息。"
    return rewritten, f"调整了{'、'.join(dict.fromkeys(changed))}，让表达更可推进。"


async def rewrite_flagged_message(
    session: AsyncSession, user_id: str, session_id: str, round_no: int
) -> MessageRewriteView:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")
    message = await session.scalar(
        select(Message).where(
            Message.session_id == session_id,
            Message.round_no == round_no,
            Message.speaker == "USER",
        )
    )
    if message is None:
        raise not_found("该轮回答")
    if not message.flags:
        raise AppError(422, "NO_RISK_FLAG", "这一轮没有被标记的表达，不需要改写")

    degraded = False
    try:
        raw = await llm_gateway.complete_json(
            REWRITE_SYSTEM_PROMPT,
            f"被标记的问题：{'、'.join(message.flags)}\n用户原话：{message.content}",
            temperature=0.4,
        )
        rewrite = str(raw.get("rewrite") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        if len(rewrite) < 4:
            raise ValueError("empty rewrite")
    except Exception as exc:
        logger.warning("training.rewrite_degraded error_type=%s", type(exc).__name__)
        degraded = True
        rewrite, reason = _fallback_rewrite(message.content, message.flags)

    return MessageRewriteView(
        round_no=message.round_no,
        original=message.content,
        rewrite=rewrite,
        reason=reason or "保留原意，语气更可协商。",
        flags=list(message.flags),
        degraded=degraded,
    )


JD_PLAN_PROMPT = """你是面试教练。根据岗位描述（JD）和候选人简历，同时完成两件事：

一、出 3~6 道针对本岗位的必问题：
- text：口语化的问题，20~60 字；
- dimension：只能是 内容与逻辑 / 信息完整 / 表达干净 / 贴合问题；
- difficulty：入门 / 中级 / 进阶。

二、给出匹配分析：
- score：0-100，衡量简历与 JD 的匹配程度；
- strengths：2~3 条，简历里能对上 JD 的具体优势；
- gaps：0~4 条未覆盖要求，每条含 requirement（JD 里的原要求）、why（为什么算缺口）、drill（一个可执行的准备动作）；
- followUps：2~3 个面试官很可能追问的问题。

只输出 JSON：
{"plan":[{"text":"...","dimension":"内容与逻辑","difficulty":"中级"}],
"match":{"score":72,"strengths":["..."],"gaps":[{"requirement":"...","why":"...","drill":"..."}],"followUps":["..."]}}。
不要编造简历里没有的经历。"""


def fallback_plan_from_scene(scene: Scene) -> list[dict]:
    bank = normalize_bank(scene.question_bank)
    if bank:
        return bank
    return [{"text": scene.opening_line, "dimension": None, "difficulty": scene.difficulty}]


async def set_job_description(
    session: AsyncSession, user_id: str, session_id: str, jd_text: str
) -> SessionView:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")
    scene = await session.get(Scene, training.scene_id)
    if scene is None:
        raise not_found("面试场景")
    resume = await session.get(ResumeContext, training.id)
    plan: list[dict] = []
    degraded = False
    raw: dict = {}
    try:
        raw = await llm_gateway.complete_json(
            JD_PLAN_PROMPT,
            f"岗位描述：{jd_text[:2000]}\n简历摘要：{(resume.content if resume else '未提供')[:1500]}\n面试阶段：{scene.category}\n岗位：{scene.position}",
            temperature=0.3,
        )
        plan = normalize_bank(raw.get("plan"))
        if not plan:
            raise ValueError("empty plan")
    except Exception as exc:
        logger.warning("training.jd_plan_degraded error_type=%s", type(exc).__name__)
        degraded = True
        plan = fallback_plan_from_scene(scene)
    training.jd_text = jd_text
    training.question_plan = plan
    training.job_match = build_match(
        training,
        scene,
        resume,
        None if degraded else raw.get("match"),
    )
    training.covered_count = 0
    await session.commit()
    view = await get_training_session(session, user_id, session_id)
    return view


async def clear_job_description(session: AsyncSession, user_id: str, session_id: str) -> SessionView:
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user_id:
        raise not_found("训练会话")
    training.jd_text = None
    training.question_plan = None
    training.job_match = None
    training.covered_count = 0
    await session.commit()
    return await get_training_session(session, user_id, session_id)

"""教练查看链接：带过期签名的只读访问 + 时间点批注 + 可撤销 + 打印版报告页。

链接本身是 HMAC 令牌，不需要登录；只能读取一次会话的报告摘要，
可以追加时间点批注，不能修改评分或访问其他会话。
学员本人可以把令牌签名写入数据库撤销，撤销后所有链接入口（含打印版报告）一律 410。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.errors import AppError, not_found
from app.core.responses import ok
from app.core.schemas import ApiModel
from app.core.security import CurrentUser
from app.db.base import get_session
from app.db.models import (
    Evaluation,
    EvaluationEvidence,
    Message,
    Scene,
    ShareRevocation,
    TrainingSession,
)
from app.features.recordings import storage

router = APIRouter(prefix="/share", tags=["教练查看"])
DbSession = Annotated[AsyncSession, Depends(get_session)]

DEFAULT_TTL_SECONDS = 7 * 24 * 3600
MAX_ANNOTATIONS = 50


def _secret() -> bytes:
    return (settings.jwt_secret or "career-coach-share").encode("utf-8")


def issue_token(session_id: str, ttl: int = DEFAULT_TTL_SECONDS) -> tuple[str, int]:
    expires = int(time.time()) + ttl
    payload = json.dumps({"sid": session_id, "exp": expires}, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{signature}", expires


def verify_token(token: str) -> tuple[str, str]:
    """校验签名与过期时间，返回 (会话 ID, 令牌签名)。"""
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        raise not_found("链接")
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature, expected):
        raise not_found("链接")
    padded = body + "=" * (-len(body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:  # noqa: BLE001
        raise not_found("链接")
    if int(payload.get("exp") or 0) < int(time.time()):
        raise AppError(410, "SHARE_EXPIRED", "这个链接已过期，请让学员重新生成")
    return str(payload.get("sid")), signature


async def load_shared_token(session: AsyncSession, token: str) -> tuple[str, TrainingSession]:
    """令牌 → 训练会话：签名、过期、撤销三道关都过才放行。"""
    session_id, signature = verify_token(token)
    if await session.get(ShareRevocation, signature) is not None:
        raise AppError(410, "SHARE_REVOKED", "这个链接已被学员撤销")
    training = await session.get(TrainingSession, session_id)
    if training is None:
        raise not_found("训练会话")
    return session_id, training


class AnnotationRequest(ApiModel):
    at_ms: int = Field(default=0, ge=0, le=3_600_000)
    comment: str = Field(min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=40)


@router.post("/training-sessions/{session_id}")
async def create_share_link(
    session_id: str, user: CurrentUser, session: DbSession
) -> dict:
    """学员本人生成教练查看链接（默认 7 天）。"""
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user.id:
        raise not_found("训练会话")
    token, expires = issue_token(session_id)
    return ok({"url": f"/share/{token}", "expiresAt": expires})


@router.get("/{token}")
async def read_shared(token: str, session: DbSession) -> dict:
    """教练打开链接：返回摘要、转写和批注，不含其他个人信息。"""
    session_id, training = await load_shared_token(session, token)
    scene = await session.get(Scene, training.scene_id)
    evaluation = await session.scalar(select_evaluation(session_id))
    delivery = training.delivery or {}
    # 文字/语音会话结束时不写 delivery.transcript，这里回退到消息表重建
    transcript = delivery.get("transcript") or await transcript_from_messages(
        session, session_id
    )
    return ok(
        {
            "sceneTitle": scene.title if scene else "历史场景",
            "channel": training.channel,
            "startedAt": training.started_at.isoformat(),
            "overallScore": evaluation.overall_score if evaluation else None,
            "scores": {
                "logic": evaluation.logic_score,
                "relevance": evaluation.relevance_score,
                "correctness": evaluation.correctness_score,
                "concision": evaluation.concision_score,
            }
            if evaluation
            else None,
            "summary": evaluation.summary if evaluation else None,
            "recordingUrl": storage.signed_url(training.recording_path),
            "transcript": transcript,
            "annotations": delivery.get("annotations") or [],
            "expiresIn": 0,
        }
    )


@router.delete("/{token}")
async def revoke_share_link(token: str, user: CurrentUser, session: DbSession) -> dict:
    """学员本人撤销教练查看链接：签名入库后立即失效，不是本人一律 404。"""
    session_id, signature = verify_token(token)
    training = await session.get(TrainingSession, session_id)
    if training is None or training.user_id != user.id:
        raise not_found("训练会话")
    if await session.get(ShareRevocation, signature) is None:
        session.add(ShareRevocation(token_sig=signature, session_id=session_id))
        await session.commit()
    return ok({"revoked": True, "sessionId": session_id})


@router.get("/{token}/report", response_class=HTMLResponse)
async def shared_report(token: str, session: DbSession) -> HTMLResponse:
    """服务端渲染的独立报告页：内联样式、无外部资源、无 JS，可直接 Ctrl+P 存成 PDF。"""
    session_id, training = await load_shared_token(session, token)
    scene = await session.get(Scene, training.scene_id)
    evaluation = await session.scalar(select_evaluation(session_id))
    evidence = (
        list((await session.scalars(select_evidence(evaluation.id))).all())
        if evaluation is not None
        else []
    )
    page = render_report(
        scene_title=scene.title if scene else "历史场景",
        channel=training.channel,
        started_at=training.started_at,
        rounds=await round_summaries(session, session_id),
        evaluation=evaluation,
        evidence=evidence,
    )
    return HTMLResponse(content=page, headers={"Cache-Control": "no-store"})


@router.post("/{token}/annotations")
async def add_annotation(
    token: str, body: AnnotationRequest, session: DbSession
) -> dict:
    """教练在某个时间点留一条批注。"""
    session_id, training = await load_shared_token(session, token)
    delivery = dict(training.delivery or {})
    annotations = list(delivery.get("annotations") or [])
    if len(annotations) >= MAX_ANNOTATIONS:
        raise AppError(422, "ANNOTATION_LIMIT", "这条链接的批注数量已达上限")
    annotations.append(
        {
            "atMs": body.at_ms,
            "comment": body.comment.strip(),
            "author": (body.author or "教练").strip()[:40],
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    delivery["annotations"] = annotations
    training.delivery = delivery
    flag_modified(training, "delivery")
    await session.commit()
    return ok({"annotations": annotations})


def select_evaluation(session_id: str):
    from sqlalchemy import select

    return select(Evaluation).where(Evaluation.session_id == session_id)


def select_evidence(evaluation_id: str):
    from sqlalchemy import select

    return (
        select(EvaluationEvidence)
        .where(EvaluationEvidence.evaluation_id == evaluation_id)
        .order_by(EvaluationEvidence.round_no)
    )


async def round_summaries(session: AsyncSession, session_id: str) -> list[dict]:
    """把逐轮问答压成「问题 + 回答」两句话，供打印版报告列举。"""
    from sqlalchemy import select

    rows = (
        await session.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.round_no, Message.created_at)
        )
    ).all()
    rounds: list[dict] = []
    question = ""
    for row in rows:
        if row.speaker == "AI":
            question = row.content
            continue
        if row.speaker != "USER":
            continue
        rounds.append(
            {"roundNo": row.round_no, "question": question, "answer": row.content}
        )
    return rounds


async def transcript_from_messages(session: AsyncSession, session_id: str) -> list[dict]:
    """没有写好的 transcript 时，从逐轮消息还原（结构与视频任务写入的一致）。"""
    return [
        {
            "roundNo": int(row["roundNo"]),
            "question": row["question"],
            "text": row["answer"],
            "startMs": None,
            "endMs": None,
            "confidence": None,
            "edited": False,
        }
        for row in await round_summaries(session, session_id)
    ]


CHANNEL_LABELS = {"TEXT": "文字对练", "VOICE": "语音对练", "VIDEO": "视频面试"}
SCORE_FIELDS = (
    ("logic", "内容与逻辑", "logic_score"),
    ("relevance", "贴合问题", "relevance_score"),
    ("correctness", "信息完整", "correctness_score"),
    ("concision", "表达干净", "concision_score"),
)
DIMENSION_LABELS = {key: label for key, label, _ in SCORE_FIELDS}

PAGE_STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 26px 18px 56px;
  background: #f4f2ec;
  color: #1d1f24;
  font-family: "Microsoft YaHei", "PingFang SC", "Heiti SC", system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.8;
}
.print-hint {
  max-width: 800px;
  margin: 0 auto 16px;
  padding: 9px 14px;
  border: 1px dashed #b9b3a4;
  border-radius: 6px;
  background: #fbfaf6;
  color: #5b564c;
  font-size: 12.5px;
  letter-spacing: .04em;
}
.sheet {
  max-width: 800px;
  margin: 0 auto;
  padding: 44px 48px 52px;
  border: 1px solid #e0dcd1;
  border-radius: 4px;
  background: #fff;
}
.head { padding-bottom: 18px; border-bottom: 2px solid #1d1f24; }
.eyebrow { margin: 0; color: #7b766b; font-size: 11.5px; letter-spacing: .28em; }
h1 { margin: 12px 0 0; font-size: 27px; font-weight: 600; letter-spacing: .01em; }
.meta { margin: 12px 0 0; display: flex; flex-wrap: wrap; gap: 8px 18px; color: #6c6659; font-size: 12.5px; }
.meta span + span::before { content: "·"; margin-right: 18px; color: #c3bcac; }
section { margin-top: 34px; }
section > h2 {
  margin: 0 0 14px;
  color: #7b766b;
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: .24em;
}
.overall { display: flex; align-items: baseline; gap: 12px; margin: 0; }
.overall b { font-size: 52px; font-weight: 300; line-height: 1; letter-spacing: -.02em; }
.overall i { color: #8b8578; font-size: 13px; font-style: normal; }
table { width: 100%; border-collapse: collapse; margin-top: 18px; }
th, td { padding: 8px 0; border-bottom: 1px solid #eceae3; text-align: left; font-weight: 400; font-size: 13.5px; }
th { width: 108px; color: #7b766b; }
td.num { width: 54px; font-variant-numeric: tabular-nums; font-size: 15px; }
.bar { display: block; height: 3px; border-radius: 2px; background: #ecebe5; }
.bar b { display: block; height: 3px; border-radius: 2px; background: #4a4d55; }
.summary { margin: 0; color: #2c2f36; font-size: 14.5px; }
ol.rounds, ol.evidence, ol.plans { margin: 0; padding: 0; list-style: none; }
ol.rounds li, ol.evidence li, ol.plans li { padding: 12px 0; border-bottom: 1px solid #f0eee7; break-inside: avoid; }
ol.rounds li:last-child, ol.evidence li:last-child, ol.plans li:last-child { border-bottom: 0; }
.q { margin: 0; color: #6c6659; font-size: 12.5px; }
.a { margin: 5px 0 0; color: #1d1f24; font-size: 13.5px; }
ol.evidence h3 { margin: 0 0 8px; color: #1d1f24; font-size: 13.5px; font-weight: 600; }
blockquote {
  margin: 0 0 8px;
  padding: 2px 0 2px 14px;
  border-left: 2px solid #b9b3a4;
  color: #3d4149;
  font-size: 13.5px;
}
ol.evidence p { margin: 0; color: #4a4d55; font-size: 13px; }
ol.evidence p.next { margin-top: 6px; color: #7b766b; font-size: 12.5px; }
ol.plans .problem { margin: 0 0 6px; font-size: 13.5px; }
ol.plans .pair { margin: 0; font-size: 13px; color: #4a4d55; }
ol.plans .pair span { color: #7b766b; }
.empty { color: #7b766b; font-size: 13.5px; }
.foot { margin-top: 40px; padding-top: 14px; border-top: 1px solid #eceae3; color: #8b8578; font-size: 11.5px; }
@media print {
  body { padding: 0; background: #fff; font-size: 12pt; }
  .print-hint { border-style: solid; background: #fff; }
  .sheet { max-width: none; padding: 0; border: 0; }
  section { break-inside: auto; }
  @page { margin: 16mm; }
}
"""


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _brief(text: object, limit: int = 200) -> str:
    clean = " ".join(str(text or "").split())
    return clean if len(clean) <= limit else f"{clean[:limit]}…"


def render_report(
    *,
    scene_title: str,
    channel: str,
    started_at: object,
    rounds: list[dict],
    evaluation: Evaluation | None,
    evidence: list[EvaluationEvidence],
) -> str:
    """拼一页自带样式的 HTML：不引用任何外部资源，也不依赖脚本。"""
    stamp = started_at.strftime("%Y-%m-%d %H:%M") if hasattr(started_at, "strftime") else ""
    blocks: list[str] = []

    if evaluation is None:
        blocks.append(
            '<section><h2>成绩</h2><p class="empty">这一场还没有评分报告，稍后再打开这个链接。</p></section>'
        )
    else:
        rows = "".join(
            f'<tr><th>{label}</th><td class="num">{_esc(getattr(evaluation, field))}</td>'
            f'<td><span class="bar"><b style="width:{max(0.0, min(100.0, float(getattr(evaluation, field)) * 20)):.0f}%"></b></span></td></tr>'
            for _, label, field in SCORE_FIELDS
        )
        blocks.append(
            "<section><h2>综合成绩</h2>"
            f'<p class="overall"><b>{_esc(round(float(evaluation.overall_score), 1))}</b><i>/ 100</i></p>'
            f"<table>{rows}</table></section>"
        )
        blocks.append(
            '<section><h2>教练总评</h2><p class="summary">'
            f"{_esc(_brief(evaluation.summary, 900))}</p></section>"
        )

    if rounds:
        items = "".join(
            f'<li><p class="q">第 {int(row["roundNo"])} 题 · {_esc(_brief(row["question"], 120))}</p>'
            f'<p class="a">{_esc(_brief(row["answer"], 220))}</p></li>'
            for row in rounds
        )
        blocks.append(f'<section><h2>逐题问答摘要</h2><ol class="rounds">{items}</ol></section>')

    if evidence:
        items = "".join(
            f'<li><h3>{_esc(DIMENSION_LABELS.get(row.dimension, row.dimension))} · 第 {int(row.round_no)} 题</h3>'
            f"<blockquote>{_esc(_brief(row.quote, 260))}</blockquote>"
            f"<p>{_esc(_brief(row.reason, 320))}</p>"
            f'<p class="next">下一步：{_esc(_brief(row.next_action, 240))}</p></li>'
            for row in evidence
        )
        blocks.append(f'<section><h2>证据与整改（引原话）</h2><ol class="evidence">{items}</ol></section>')
    elif evaluation is not None:
        blocks.append(
            '<section><h2>证据与整改（引原话）</h2><p class="empty">'
            "本场由本地评分规则生成，没有逐维引用原话，可从下面的改写建议里挑一句重写。</p></section>"
        )

    suggestions = list((evaluation.suggestions or []) if evaluation is not None else [])
    if suggestions:
        items = "".join(
            f'<li><p class="problem">{_esc(_brief(item.get("problem"), 160))}</p>'
            f'<p class="pair"><span>原表达：</span>{_esc(_brief(item.get("original"), 200))}</p>'
            f'<p class="pair"><span>建议改写：</span>{_esc(_brief(item.get("rewrite"), 240))}</p></li>'
            for item in suggestions[:8]
        )
        blocks.append(f'<section><h2>改写建议</h2><ol class="plans">{items}</ol></section>')

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_esc(scene_title)} · 训练报告</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
<p class="print-hint">如需存档可按 Ctrl+P 另存为 PDF</p>
<main class="sheet">
<header class="head">
<p class="eyebrow">教练查看 · 训练报告</p>
<h1>{_esc(scene_title)}</h1>
<p class="meta"><span>{_esc(CHANNEL_LABELS.get(channel, channel))}</span><span>{_esc(stamp)}</span><span>{len(rounds)} 轮对话</span></p>
</header>
{"".join(blocks)}
<footer class="foot">本页由训练报告自动生成，只含这一场的场景、分数与对话摘要，不含其他个人信息。</footer>
</main>
</body>
</html>
"""

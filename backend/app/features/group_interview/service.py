"""无领导小组讨论：主持人 + 两位虚拟候选人，与用户轮流发言。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.errors import AppError
from app.db.models import GroupInterview, now
from app.infrastructure.llm import llm_gateway

def _find_topic_file() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "content" / "group-topics.json"
        if candidate.is_file():
            return candidate
    return None


TOPIC_FILE = _find_topic_file()
TOPICS: list[dict] = json.loads(TOPIC_FILE.read_text(encoding="utf-8")) if TOPIC_FILE else []

SPEAKERS = ("候选人 A", "候选人 B")

FALLBACK_REPLIES = {
    "候选人 A": [
        "我先回应一下你的观点：方向我认同，但我担心一次性投入太大。能不能先选一个高确定性的点做验证？",
        "补充一个不同角度：如果资源只够做两件事，我会优先保证交付节奏，其次才是覆盖面。",
        "我同意你的排序，不过想确认一下判断依据：你说的高收益，有具体数据支撑吗？",
    ],
    "候选人 B": [
        "我理解你的出发点，但团队执行成本也要算进去。我的建议是设一个四周验证期，指标不达标就回退。",
        "刚才你提到风险，我觉得可以再加一条兜底：先小范围灰度，再决定是否全量。",
        "我没有反对意见，只补充一点：方案落地时谁负责、什么时候复盘，最好现在就定下来。",
    ],
}

EVAL_DIMENSIONS = ("观点质量", "倾听与回应", "协作推进", "表达清晰")


def list_topics() -> list[dict]:
    return [
        {"id": item["id"], "category": item.get("category", ""), "title": item["title"], "prompt": item["prompt"]}
        for item in TOPICS
    ]


def get_topic(topic_id: str) -> dict:
    for item in TOPICS:
        if item["id"] == topic_id:
            return item
    raise AppError(404, "GROUP_TOPIC_NOT_FOUND", "群面题目不存在")


def _opening(topic: dict) -> str:
    return (
        f"本场是无领导小组讨论，题目是：{topic['prompt']} "
        "在座有候选人 A、候选人 B 和你，我是主持人。请先用 60 秒说说你的思路。"
    )


def _user_turn_count(turns: list[dict]) -> int:
    return sum(1 for item in turns if item.get("role") == "user")


def _fallback_reply(speaker: str, round_no: int) -> str:
    options = FALLBACK_REPLIES[speaker]
    return options[(round_no - 1) % len(options)]


async def _ai_reply(topic: dict, turns: list[dict], speaker: str, round_no: int) -> str:
    transcript = "\n".join(
        f"{item['role']}：{item['text']}" for item in turns[-8:]
    )
    system = (
        "你在模拟一场中文无领导小组讨论。你是候选人之一，不是主持人，不要总结全场、不要评价候选人。"
        "根据讨论记录回应用户的最后一个观点：先简短回应，再补充一个具体角度或追问，不超过 90 字。"
        '返回 JSON：{"reply":"你的发言"}'
    )
    user = f"讨论题目：{topic['prompt']}\n你是：{speaker}\n最近发言：\n{transcript}\n请发言。"
    try:
        data = await llm_gateway.complete_json(system, user, temperature=0.7, max_tokens=200)
        text = str(data.get("reply") or "").strip()
        if text:
            return text[:160]
    except Exception:  # noqa: BLE001
        pass
    return _fallback_reply(speaker, round_no)


def _fallback_result(user_texts: list[str]) -> dict:
    joined = "".join(user_texts)
    chars = len(re.sub(r"\s", "", joined))
    agree = len(re.findall(r"(同意|认同|补充|赞同|理解|回应)", joined))
    questions = len(re.findall(r"[?？]", joined))
    numbers = len(set(re.findall(r"\d+", joined)))
    base = 55
    scores = {
        "观点质量": min(95, base + min(chars, 600) // 20 + numbers * 2),
        "倾听与回应": min(95, base + agree * 6),
        "协作推进": min(95, base + agree * 3 + questions * 4),
        "表达清晰": min(95, base + min(chars, 600) // 25 + questions * 2),
    }
    dimensions = [
        {
            "name": name,
            "score": scores[name],
            "comment": "有回应他人观点" if agree else "可以更多回应其他候选人的观点，再给出自己的判断",
        }
        for name in EVAL_DIMENSIONS
    ]
    overall = round(sum(scores.values()) / len(scores))
    return {
        "score": overall,
        "dimensions": dimensions,
        "summary": f"共发言 {len(user_texts)} 轮、约 {chars} 字；回应他人 {agree} 次、提问 {questions} 次。",
        "suggestions": [
            "先明确说出你支持或反对哪一位候选人的哪一点，再补充自己的依据。",
            "讨论收尾时主动做一次小结：达成什么共识、还剩什么分歧、下一步谁负责。",
        ],
    }


async def _evaluate(turns: list[dict]) -> dict:
    user_texts = [item["text"] for item in turns if item.get("role") == "user"]
    if not user_texts:
        raise AppError(422, "GROUP_NO_SPEECH", "至少发言一次才能生成评估")
    transcript = "\n".join(f"{item['role']}：{item['text']}" for item in turns[-16:])
    system = (
        "你是无领导小组讨论的评估者。根据讨论记录评估用户（角色 user）的表现，"
        "四个维度：观点质量、倾听与回应、协作推进、表达清晰，每项 0-100。"
        '只输出 JSON：{"dimensions":[{"name":"观点质量","score":80,"comment":"..."}],"summary":"...","suggestions":["...","..."]}'
    )
    try:
        data = await llm_gateway.complete_json(system, f"讨论记录：\n{transcript}", temperature=0.3, max_tokens=600)
        dimensions = [
            {"name": str(item.get("name")), "score": int(item.get("score") or 60), "comment": str(item.get("comment") or "")}
            for item in data.get("dimensions") or []
            if item.get("name")
        ]
        if len(dimensions) >= 3:
            names = [item["name"] for item in dimensions]
            for name in EVAL_DIMENSIONS:
                if name not in names:
                    dimensions.append({"name": name, "score": 60, "comment": ""})
            overall = round(sum(item["score"] for item in dimensions) / len(dimensions))
            return {
                "score": overall,
                "dimensions": dimensions,
                "summary": str(data.get("summary") or ""),
                "suggestions": [str(item) for item in (data.get("suggestions") or [])][:4],
            }
    except Exception:  # noqa: BLE001
        pass
    return _fallback_result(user_texts)


async def create_group(session, user_id: str, topic_id: str) -> GroupInterview:
    topic = get_topic(topic_id)
    row = GroupInterview(
        user_id=user_id,
        topic_id=topic["id"],
        topic_title=topic["title"],
        topic_prompt=topic["prompt"],
        turns=[{"role": "host", "text": _opening(topic)}],
    )
    session.add(row)
    await session.commit()
    return row


async def append_user_message(session, user_id: str, group_id: str, text: str) -> GroupInterview:
    row = await session.get(GroupInterview, group_id)
    if row is None or row.user_id != user_id:
        raise AppError(404, "GROUP_NOT_FOUND", "群面记录不存在")
    if row.status != "ACTIVE":
        raise AppError(409, "GROUP_FINISHED", "这场讨论已经结束")
    content = (text or "").strip()
    if not content:
        raise AppError(422, "GROUP_EMPTY", "请先输入你的发言")
    turns = list(row.turns or [])
    turns.append({"role": "user", "text": content[:600]})
    round_no = _user_turn_count(turns)
    speaker = SPEAKERS[(round_no - 1) % len(SPEAKERS)]
    reply = await _ai_reply(
        {"prompt": row.topic_prompt}, turns, speaker, round_no
    )
    turns.append({"role": speaker, "text": reply})
    row.turns = turns
    await session.commit()
    return row


async def finish_group(session, user_id: str, group_id: str) -> GroupInterview:
    row = await session.get(GroupInterview, group_id)
    if row is None or row.user_id != user_id:
        raise AppError(404, "GROUP_NOT_FOUND", "群面记录不存在")
    if row.status == "ACTIVE":
        row.result = await _evaluate(list(row.turns or []))
        row.status = "FINISHED"
        row.finished_at = now()
        await session.commit()
    return row

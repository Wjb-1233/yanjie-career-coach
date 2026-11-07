"""从 JD 起草场景：只根据 JD 里的要求生成问题，不编造公司事实。"""

from __future__ import annotations

import logging
import re

from app.core.errors import AppError
from app.infrastructure.llm import llm_gateway

logger = logging.getLogger(__name__)

MIN_JD_CHARS = 80
MAX_JD_CHARS = 4000

SYSTEM_PROMPT = """你是面试题设计助手。根据用户提供的岗位 JD，生成一场模拟面试的场景草稿。

硬性约束：
1. 只能依据 JD 中出现的要求出题，不得虚构公司业务、团队规模、产品细节。
2. 不生成「公司文化好不好」「团队氛围如何」这类无法核实的断言。
3. 每个问题必须能对应 JD 里的一条要求，问题以考察点形式给出，不直接给答案。
4. 输出 4 到 8 个问题，维度只能是：内容与逻辑、贴合问题、信息完整、表达干净。
5. 只输出 JSON，不要解释。

JSON 结构：
{
  "title": "岗位-阶段（不超过 30 字）",
  "industry": "行业",
  "position": "岗位名",
  "roleName": "面试官角色名",
  "category": "HR 初面|技术一面|技术二面/复面|交叉面/总监面|HRBP/HR 终面|大老板/高管终面|基础能力提升|自定义",
  "difficulty": "入门|中级|进阶",
  "background": "一句话交代岗位与业务背景，只能来自 JD",
  "goal": "这场面试要考察什么，2 句以内",
  "openingLine": "面试官开场白",
  "competency": "技术深度|沟通表达|协作与影响力|求职动机与稳定性|表达基本功",
  "questions": [{"text": "问题", "dimension": "内容与逻辑"}]
}"""

CATEGORY_HINTS = [
    ("HR", "HR 初面"),
    ("人力", "HR 初面"),
    ("技术", "技术一面"),
    ("开发", "技术一面"),
    ("算法", "技术一面"),
    ("总监", "交叉面/总监面"),
    ("主管", "交叉面/总监面"),
    ("实习", "基础能力提升"),
]


def _fallback_draft(jd: str, position: str, category: str, difficulty: str) -> dict:
    """模型不可用时，用 JD 里的职责句拼一份可用草稿，并标记降级。"""
    lines = [line.strip(" -•\t") for line in jd.splitlines()]
    lines = [line for line in lines if 8 <= len(line) <= 80]
    duties = [line for line in lines if any(word in line for word in ("负责", "熟悉", "掌握", "具备", "参与", "了解", "要求"))]
    picked = duties[:6] or lines[:6]
    questions = []
    for item in picked:
        text = f"围绕「{item[:40]}」，说说你的实际经历和做法"
        questions.append({"text": text[:120], "dimension": "内容与逻辑"})
    while len(questions) < 4:
        questions.append({"text": "介绍一下你和这个岗位最相关的一段经历", "dimension": "贴合问题"})
    return {
        "title": f"{position}-{category}"[:60],
        "industry": "综合行业",
        "position": position,
        "roleName": "面试官",
        "category": category,
        "difficulty": difficulty,
        "background": f"{position}岗位面试，具体要求来自 JD。",
        "goal": "按 JD 要求逐条核对经历与做法。",
        "openingLine": f"你好，我是今天的面试官，今天围绕{position}这个岗位聊一聊。",
        "competency": "沟通表达",
        "questions": questions[:8],
        "degraded": True,
    }


def _clean_draft(raw: dict, position: str, category: str, difficulty: str, jd: str) -> dict:
    categories = {
        "HR 初面", "技术一面", "技术二面/复面", "交叉面/总监面",
        "HRBP/HR 终面", "大老板/高管终面", "基础能力提升", "自定义",
    }
    dimensions = {"内容与逻辑", "贴合问题", "信息完整", "表达干净"}
    questions = []
    for item in raw.get("questions") or []:
        if isinstance(item, str):
            text, dimension = item, "内容与逻辑"
        else:
            text = str(item.get("text") or "")
            dimension = str(item.get("dimension") or "")
        text = text.strip()
        if len(text) < 4:
            continue
        # 问题里不能出现答案式断言，过长也截断
        questions.append({"text": text[:120], "dimension": dimension if dimension in dimensions else "内容与逻辑"})
        if len(questions) >= 8:
            break
    if len(questions) < 2:
        return _fallback_draft(jd, position, category, difficulty)

    chosen_category = str(raw.get("category") or category)
    if chosen_category not in categories:
        chosen_category = category
    chosen_difficulty = str(raw.get("difficulty") or difficulty)
    if chosen_difficulty not in {"入门", "中级", "进阶"}:
        chosen_difficulty = difficulty

    return {
        "title": str(raw.get("title") or f"{position}-{chosen_category}")[:60],
        "industry": str(raw.get("industry") or "综合行业")[:30],
        "position": str(raw.get("position") or position)[:40],
        "roleName": str(raw.get("roleName") or "面试官")[:30],
        "category": chosen_category,
        "difficulty": chosen_difficulty,
        "background": str(raw.get("background") or "")[:500],
        "goal": str(raw.get("goal") or "")[:300],
        "openingLine": str(raw.get("openingLine") or "")[:200],
        "competency": str(raw.get("competency") or "")[:30] or None,
        "questions": questions,
        "degraded": False,
    }


async def draft_from_jd(
    jd: str,
    position: str,
    category: str = "自定义",
    difficulty: str = "中级",
) -> dict:
    jd = (jd or "").strip()
    if len(jd) < MIN_JD_CHARS:
        raise AppError(422, "JD_TOO_SHORT", f"JD 至少 {MIN_JD_CHARS} 字，太短的话生成的问题会太空")
    if len(jd) > MAX_JD_CHARS:
        jd = jd[:MAX_JD_CHARS]

    position = (position or "").strip()[:40] or "目标岗位"
    category = category if category else "自定义"
    difficulty = difficulty if difficulty else "中级"

    if not llm_gateway.configured:
        return _fallback_draft(jd, position, category, difficulty)

    try:
        raw = await llm_gateway.complete_json(
            SYSTEM_PROMPT,
            f"岗位：{position}\n面试阶段：{category}\n难度：{difficulty}\n\nJD 原文：\n{jd}",
            temperature=0.3,
            max_tokens=1800,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("scene.draft_failed error_type=%s", type(exc).__name__)
        return _fallback_draft(jd, position, category, difficulty)

    return _clean_draft(raw, position, category, difficulty, jd)

"""JD × 简历匹配分析：在提交岗位描述时与题目计划一起生成。

结果存在 training_sessions.job_match，用于：
1. 对练页展示「匹配度 + 缺口」，提示这轮重点考什么；
2. 报告页给出「岗位匹配」面板；
3. 生成训练计划时把缺口当作选题依据。
"""

from __future__ import annotations

import re

from app.db.models import ResumeContext, Scene, TrainingSession

POSITIVE = ["负责", "主导", "搭建", "优化", "提升", "降低", "上线", "落地", "设计", "解决"]
QUANTITY = re.compile(r"\d+(?:\.\d+)?\s*(?:%|ms|万|千|人|天|倍|qps|QPS)")


def fallback_match(jd_text: str, resume_text: str | None, scene: Scene | None) -> dict:
    """模型不可用时的规则估算：按关键词与量化程度粗算匹配度。"""
    jd = (jd_text or "").strip()
    resume = (resume_text or "").strip()
    if not jd:
        return {}

    requirements = [item for item in re.split(r"[；;。\n]", jd) if len(item.strip()) >= 4][:6]
    resume_lower = resume.lower()
    hits = 0
    gaps: list[dict] = []
    for item in requirements:
        keywords = [word for word in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", item)][:4]
        matched = any(word.lower() in resume_lower for word in keywords) if keywords else False
        if matched:
            hits += 1
        else:
            gaps.append(
                {
                    "requirement": item.strip()[:40],
                    "why": "简历里没有对应经历的直接证据",
                    "drill": f"针对「{item.strip()[:20]}」准备一个具体例子：背景、做法、结果各一句",
                }
            )

    base = 45 + (35 * hits / max(1, len(requirements))) if requirements else 50
    if QUANTITY.search(resume):
        base += 8
    if any(word in resume for word in POSITIVE):
        base += 5

    return {
        "score": int(max(20, min(95, base))),
        "strengths": [
            f"简历里有 {hits} 条要求能找到对应经历"
            if hits
            else "简历暂时没能对上 JD 的硬性要求"
        ],
        "gaps": gaps[:4],
        "followUps": [gap["requirement"] for gap in gaps[:3]],
        "degraded": True,
        "requirementCount": len(requirements),
    }


def normalize_match(raw: dict, fallback: dict) -> dict:
    """校验模型输出，缺失字段用规则结果补位。"""
    if not isinstance(raw, dict) or not raw:
        return fallback

    try:
        score = int(float(raw.get("score", fallback.get("score", 50))))
    except (TypeError, ValueError):
        score = int(fallback.get("score", 50))

    strengths = [str(item)[:80] for item in (raw.get("strengths") or []) if str(item).strip()][:3]
    gaps: list[dict] = []
    for item in (raw.get("gaps") or [])[:4]:
        if isinstance(item, dict):
            requirement = str(item.get("requirement") or "").strip()
            if not requirement:
                continue
            gaps.append(
                {
                    "requirement": requirement[:60],
                    "why": str(item.get("why") or "简历缺少对应证据")[:80],
                    "drill": str(item.get("drill") or f"准备一个关于「{requirement[:16]}」的具体例子")[:100],
                }
            )
        elif str(item).strip():
            gaps.append({"requirement": str(item)[:60], "why": "简历缺少对应证据", "drill": "准备一个具体例子"})

    follow_ups = [str(item)[:60] for item in (raw.get("followUps") or []) if str(item).strip()][:3]

    return {
        "score": max(0, min(100, score)),
        "strengths": strengths or fallback.get("strengths", []),
        "gaps": gaps or fallback.get("gaps", []),
        "followUps": follow_ups or fallback.get("followUps", []),
        "degraded": bool(raw.get("degraded", False)),
        "requirementCount": int(raw.get("requirementCount") or fallback.get("requirementCount", 0)),
    }


def build_match(training: TrainingSession, scene: Scene | None, resume: ResumeContext | None, llm_match: dict | None) -> dict:
    fallback = fallback_match(training.jd_text or "", resume.content if resume else None, scene)
    if not llm_match:
        return fallback
    merged = normalize_match(llm_match, fallback)
    merged["degraded"] = bool(llm_match.get("degraded", False))
    return merged

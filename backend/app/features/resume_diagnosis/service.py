"""简历诊断：用确定性规则做 JD 关键词覆盖与结构打分，不依赖模型。"""

from __future__ import annotations

import re

STOPWORDS = {
    "岗位职责", "任职要求", "任职资格", "工作职责", "职位描述", "岗位要求", "要求", "负责", "参与",
    "熟悉", "了解", "掌握", "具备", "优先", "以上", "相关", "能力", "经验", "工作", "公司", "团队",
    "以及", "或者", "能够", "具有", "良好", "较强", "优秀", "我们", "你的", "你将", "任职",
    "and", "the", "with", "for", "you", "will", "our", "are", "job", "team", "work", "experience",
}

SECTION_WORDS = ("项目", "技能", "教育", "实习", "工作", "证书", "奖项")


def _terms(text: str) -> list[str]:
    parts = re.split(r"[\n\r、，,；;。.：:｜|/／·•\-—()（）\[\]【】]+", text or "")
    seen: set[str] = set()
    terms: list[str] = []
    for part in parts:
        term = re.sub(r"^\s*\d+[.、)]?\s*", "", part).strip(" \t")
        for prefix in ("熟练掌握", "熟练使用", "熟悉", "了解", "掌握", "精通", "具备", "使用", "会用", "有", "负责", "参与", "主导", "推动"):
            if term.startswith(prefix):
                term = term[len(prefix):].strip(" ：:，,、")
        term = term.strip()
        if not (2 <= len(term) <= 24):
            continue
        pieces = [term]
        for suffix in ("优先", "经验"):
            if term.endswith(suffix) and len(term) > len(suffix) + 2:
                term = term[: -len(suffix)].strip()
        if len(term) > 12:
            pieces = [piece for piece in re.split(r"[\s的等与和及]+", term) if len(piece) >= 2]
        for piece in pieces:
            lowered = piece.lower()
            if not (2 <= len(piece) <= 12):
                continue
            if lowered in STOPWORDS or piece in STOPWORDS:
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            terms.append(piece)
            if len(terms) >= 40:
                break
        if len(terms) >= 40:
            break
    return terms


def analyze(resume_text: str, jd_text: str) -> dict:
    resume = (resume_text or "").strip()
    jd = (jd_text or "").strip()
    terms = _terms(jd)
    lowered = resume.lower()
    matched = [term for term in terms if term.lower() in lowered]
    missing = [term for term in terms if term.lower() not in lowered]
    coverage = round(len(matched) / len(terms), 3) if terms else 0.0

    digits = len(set(re.findall(r"\d+(?:\.\d+)?%?", resume)))
    sections = [word for word in SECTION_WORDS if word in resume]
    chars = len(re.sub(r"\s", "", resume))

    coverage_score = 45 * coverage
    result_score = 20 * min(digits / 5, 1)
    length_score = 15 * min(chars / 1200, 1)
    structure_score = 20 * min(len(sections) / 4, 1)
    score = round(max(0.0, min(100.0, coverage_score + result_score + length_score + structure_score)))

    suggestions: list[dict] = []
    if missing:
        suggestions.append(
            {
                "title": f"补上 JD 明确要求但简历里没有的词（{len(missing)} 个）",
                "detail": "、".join(missing[:8]) + "；补的时候要落到具体项目或职责里，不要只堆关键词。",
            }
        )
    if digits < 3:
        suggestions.append(
            {
                "title": "结果缺数字",
                "detail": "至少给 3 个可验证的数字（规模、耗时、提升比例、覆盖人数），面试官才有追问的抓手。",
            }
        )
    if chars < 800:
        suggestions.append(
            {
                "title": "简历偏短",
                "detail": f"正文约 {chars} 字，建议把最相关的 2 段经历补齐到「背景—动作—结果」，控制在 1 页内。",
            }
        )
    if len(sections) < 3:
        suggestions.append(
            {
                "title": "结构不完整",
                "detail": f"检测到的板块：{'、'.join(sections) or '无'}；建议至少包含 项目 / 技能 / 教育 三块。",
            }
        )
    if coverage >= 0.6:
        suggestions.append(
            {
                "title": "关键词覆盖不错",
                "detail": "接下来把匹配上的关键词逐一对应到真实经历，避免面试被追问时说不清。",
            }
        )

    return {
        "score": score,
        "coverage": coverage,
        "resumeChars": chars,
        "jdTerms": len(terms),
        "matched": matched,
        "missing": missing,
        "signals": {"digits": digits, "sections": sections},
        "suggestions": suggestions,
        "summary": f"JD 关键词覆盖 {round(coverage * 100)}%，检测到 {digits} 个数字、{len(sections)} 个板块，综合 {score} 分。",
    }

"""客观可复现的子指标：不依赖大模型，纯规则计算。

输出的 0–1 分数会与模型评分加权，并对模型给出「已算指标」提示，
让评分有可核查的锚点，而不是全凭模型主观判断。
"""

from __future__ import annotations

import re
from collections import Counter

FILLERS = ["然后", "就是", "那个", "其实", "反正", "所以说", "嗯", "额", "这个", "的话"]
STRUCTURE_MARKERS = ["首先", "其次", "然后", "最后", "因此", "所以", "因为", "例如", "举个例子", "总结", "一是", "二是"]
NUMBERS = re.compile(r"\d+(?:\.\d+)?\s*(?:%|ms|s|万|千|个|人|天|小时|年|月|k|K)?")
# 常见「答非所问」信号：完全不给结论的回避词
EVASIVE = ["不知道", "没想过", "无所谓", "看情况", "都行", "随便"]


def _split_sentences(text: str) -> list[str]:
    return [item for item in re.split(r"[。！？!?\n]", text) if item.strip()]


def _keywords(text: str) -> set[str]:
    """粗粒度关键词：2 字以上的中文片段与英文词。"""
    words = set(re.findall(r"[\u4e00-\u9fff]{2,}", text))
    words.update(word.lower() for word in re.findall(r"[A-Za-z]{3,}", text))
    stop = {"什么", "怎么", "这个", "那个", "可以", "我们", "你们", "他们", "因为", "所以", "如果", "就是"}
    return {word for word in words if word not in stop}


def _bigrams(text: str) -> set[str]:
    clean = re.sub(r"[\s，。！？、,.!?]", "", text)
    return {clean[index:index + 2] for index in range(len(clean) - 1)}


QUESTION_SIGNALS = {
    "为什么": ["因为", "考虑到", "希望", "看重", "觉得"],
    "怎么": ["先", "然后", "首先", "其次", "通过", "用", "步骤"],
    "如何": ["先", "然后", "首先", "通过", "用", "方法"],
    "多少": ["k", "元", "万", "%", "左右", "期望"],
    "什么": ["是", "指", "包括", "意思是"],
    "能不能": ["可以", "能", "能够"],
}


def answer_relevance(question: str | None, answer: str) -> float:
    """问题与回答的贴合度：关键词/二元组重合 + 问句类型是否被回应。"""
    if not answer.strip():
        return 0.0
    if not question:
        return 0.5

    asked = _keywords(question)
    hit_keywords = sum(1 for word in asked if word in answer) / max(1, len(asked))
    question_grams, answer_grams = _bigrams(question), _bigrams(answer)
    overlap = len(question_grams & answer_grams) / max(1, len(question_grams))

    type_score = 0.5
    for marker, expected in QUESTION_SIGNALS.items():
        if marker in question:
            type_score = 1.0 if any(word in answer for word in expected) else 0.2
            break

    length_score = min(1.0, len(answer) / 40)
    if any(word in answer for word in EVASIVE) and len(answer) < 30:
        length_score *= 0.4

    score = 0.3 * hit_keywords + 0.2 * overlap + 0.35 * type_score + 0.15 * length_score
    return round(min(1.0, score), 2)


def structure_ratio(text: str) -> float:
    """连接词密度：每 100 字出现几个结构标记。"""
    length = max(1, len(re.sub(r"\s", "", text)))
    hits = sum(text.count(marker) for marker in STRUCTURE_MARKERS)
    return min(1.0, hits / (length / 100) / 3) if length >= 40 else 0.0


def redundancy_ratio(text: str) -> float:
    """重复度：重复 4-gram 占全部 4-gram 的比例（越高越啰嗦）。"""
    clean = re.sub(r"\s", "", text)
    if len(clean) < 8:
        return 0.0
    grams = [clean[index:index + 4] for index in range(len(clean) - 3)]
    counts = Counter(grams)
    repeated = sum(count for gram, count in counts.items() if count > 1)
    return round(repeated / len(grams), 2)


def filler_density(text: str) -> float:
    length = max(1, len(re.sub(r"\s", "", text)))
    hits = sum(text.count(word) for word in FILLERS)
    return round(hits / length * 100, 2)


def number_consistency(answers: list[str], resume_text: str | None) -> float:
    """回答中的数字是否与简历中存在冲突（粗检）。无数字或无简历返回 0.5 中性。"""
    numbers = [match.group(0).strip() for match in NUMBERS.finditer(" ".join(answers))]
    numbers = [item for item in numbers if len(item) >= 2]
    if not numbers:
        return 0.5
    if not resume_text:
        return 0.5
    resume_numbers = {match.group(0).strip() for match in NUMBERS.finditer(resume_text)}
    if not resume_numbers:
        return 0.5
    conflicts = [item for item in set(numbers) if item not in resume_numbers]
    return round(1 - min(1.0, len(conflicts) / len(set(numbers))), 2)


def evasive_ratio(answers: list[str]) -> float:
    text = " ".join(answers)
    hits = sum(text.count(word) for word in EVASIVE)
    return round(min(1.0, hits / max(1, len(answers))), 2)


def completeness(answers: list[str]) -> float:
    """信息完整度：覆盖「背景/做法/结果/数字」四个槽位的比例。"""
    text = " ".join(answers)
    slots = 0
    if re.search(r"(做过|负责|参与|实习|项目|岗位|专业|学校)", text):
        slots += 1
    if re.search(r"(用了|通过|先|然后|实现|设计|方案|方法|步骤)", text):
        slots += 1
    if re.search(r"(结果|提升|降低|完成|上线|达到|减少|增长)", text):
        slots += 1
    if NUMBERS.search(text):
        slots += 1
    return round(slots / 4, 2)


def compute(questions: list[str | None], answers: list[str], resume_text: str | None = None) -> dict:
    """返回四个维度的客观分（0–1）与原始指标。"""
    if not answers:
        return {}
    text = " ".join(answers)
    coverage = [answer_relevance(question, answer) for question, answer in zip(questions, answers)] or [0.5]
    content = round(0.45 * structure_ratio(text) + 0.35 * number_consistency(answers, resume_text) + 0.2 * (1 - evasive_ratio(answers)), 2)
    relevance = round(sum(coverage) / len(coverage), 2)
    clarity = round(max(0.0, 1 - redundancy_ratio(text) * 1.5 - filler_density(text) / 20), 2)
    complete = completeness(answers)
    return {
        "content": content,
        "relevance": relevance,
        "clarity": clarity,
        "completeness": complete,
        "metrics": {
            "structure": structure_ratio(text),
            "redundancy": redundancy_ratio(text),
            "fillerDensity": filler_density(text),
            "keywordCoverage": relevance,
            "evasive": evasive_ratio(answers),
        },
    }

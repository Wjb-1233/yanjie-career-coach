"""场景与四维能力的匹配度。

场景没有显式标注训练维度，这里用两条证据估计：
1. 标题 / 沟通目标 / 背景里的关键词；
2. 历史评分里，该场景上哪个维度平均分最低（真实行为证据）。
结果写回 scene_fit 字段，推荐时按「最弱维度 × 难度匹配」排序。
"""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation, Scene, TrainingSession

DIMENSIONS = ["logic", "relevance", "correctness", "concision"]
LABELS = {
    "logic": "内容与逻辑",
    "relevance": "贴合问题",
    "correctness": "信息完整",
    "concision": "表达干净",
}

# 关键词 → 该场景最能练到的维度
KEYWORDS: dict[str, list[str]] = {
    "logic": ["逻辑", "结构", "顺序", "因果", "思路", "方案", "分析", "为什么", "取舍", "优先级"],
    "relevance": ["动机", "为什么选择", "追问", "质疑", "压力", "反问", "意向", "离职", "跳槽"],
    "correctness": ["薪资", "时间", "到岗", "数据", "业绩", "简历", "经历", "项目", "自我介绍", "信息"],
    "concision": ["自我介绍", "开场", "一分钟", "简洁", "概括", "总结", "汇报"],
}

DEFAULT_FIT = {"logic": 0.25, "relevance": 0.25, "correctness": 0.25, "concision": 0.25}


def heuristic_fit(scene: Scene) -> dict[str, float]:
    text = f"{scene.title} {scene.goal} {scene.background} {' '.join(scene.tags or [])}"
    scores = {key: 0.0 for key in DIMENSIONS}
    for key, words in KEYWORDS.items():
        hits = sum(text.count(word) for word in words)
        scores[key] += hits
    total = sum(scores.values())
    if total == 0:
        return dict(DEFAULT_FIT)
    return {key: round(0.2 + 0.8 * value / total, 2) for key, value in scores.items()}


async def historical_fit(session: AsyncSession) -> dict[str, dict[str, float]]:
    """按场景统计各维度平均分，越低说明该场景越能暴露这个维度。"""
    rows = (
        await session.execute(
            select(
                TrainingSession.scene_id,
                Evaluation.logic_score,
                Evaluation.relevance_score,
                Evaluation.correctness_score,
                Evaluation.concision_score,
            ).join(Evaluation, Evaluation.session_id == TrainingSession.id)
        )
    ).all()
    buckets: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for scene_id, logic, relevance, correctness, concision in rows:
        buckets[scene_id]["logic"].append(logic)
        buckets[scene_id]["relevance"].append(relevance)
        buckets[scene_id]["correctness"].append(correctness)
        buckets[scene_id]["concision"].append(concision)
    result: dict[str, dict[str, float]] = {}
    for scene_id, dimensions in buckets.items():
        averages = {key: sum(values) / len(values) for key, values in dimensions.items()}
        # 分数低 → 这个场景更需要练该维度
        weakness = {key: max(0.0, 5 - value) for key, value in averages.items()}
        total = sum(weakness.values())
        result[scene_id] = (
            {key: round(value / total, 2) for key, value in weakness.items()} if total else {}
        )
    return result


def merge_fit(heuristic: dict[str, float], history: dict[str, float] | None) -> dict[str, float]:
    if not history:
        return heuristic
    merged = {
        key: round(0.55 * heuristic.get(key, 0.25) + 0.45 * history.get(key, 0.25), 2)
        for key in DIMENSIONS
    }
    return merged


async def refresh_scene_fit(session: AsyncSession) -> int:
    """重算所有场景的 fit 并落库，返回更新数量。"""
    history = await historical_fit(session)
    scenes = (await session.scalars(select(Scene))).all()
    for scene in scenes:
        scene.scene_fit = merge_fit(heuristic_fit(scene), history.get(scene.id))
    await session.commit()
    return len(scenes)


def affinity(scene: Scene, target_dimensions: list[str]) -> float:
    fit = scene.scene_fit or heuristic_fit(scene)
    if not target_dimensions:
        return 0.5
    return round(sum(fit.get(dimension, 0.25) for dimension in target_dimensions) / len(target_dimensions), 2)

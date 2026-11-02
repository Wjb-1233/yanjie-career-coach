"""评分一致性统计：模型分与人工标注的对照。

只依赖标准库：手写 Spearman 秩相关，避免为此引入 scipy。
"""

from __future__ import annotations

from statistics import fmean


def _rank(values: list[float]) -> list[float]:
    """平均秩（处理并列值）。"""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index
        while end + 1 < len(order) and values[order[end + 1]] == values[order[index]]:
            end += 1
        average = (index + end) / 2 + 1
        for position in range(index, end + 1):
            ranks[order[position]] = average
        index = end + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman 秩相关系数；样本不足或方差为 0 时返回 None。"""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _rank(xs), _rank(ys)
    mx, my = fmean(rx), fmean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denominator = (
        sum((a - mx) ** 2 for a in rx) ** 0.5 * sum((b - my) ** 2 for b in ry) ** 0.5
    )
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def summarize(pairs: list[tuple[float, float]]) -> dict:
    """pairs = [(模型分, 人工分)]，返回相关性、误差与一致率。"""
    if not pairs:
        return {"count": 0}
    model = [pair[0] for pair in pairs]
    human = [pair[1] for pair in pairs]
    diffs = [abs(a - b) for a, b in pairs]
    return {
        "count": len(pairs),
        "spearman": spearman(model, human),
        "mae": round(fmean(diffs), 2),
        "exactAgreement": round(sum(1 for diff in diffs if diff == 0) / len(diffs), 3),
        "withinOne": round(sum(1 for diff in diffs if diff <= 1) / len(diffs), 3),
        "meanModel": round(fmean(model), 2),
        "meanHuman": round(fmean(human), 2),
        "bias": round(fmean(model) - fmean(human), 2),
    }


def by_dimension(rows: list[dict]) -> dict[str, dict]:
    """按维度分组统计；rows 需含 dimension/model/human。"""
    buckets: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        buckets.setdefault(str(row["dimension"]), []).append((float(row["model"]), float(row["human"])))
    return {dimension: summarize(pairs) for dimension, pairs in buckets.items()}


def render_markdown(overall: dict, per_dimension: dict[str, dict], sample_size: int) -> str:
    lines = [
        "# 评分一致性实验报告",
        "",
        f"- 样本数：{sample_size} 条（人工标注与模型评分逐条对照）",
        f"- 总体 Spearman 秩相关：{overall['spearman']}",
        f"- 总体平均绝对误差：{overall['mae']} 分",
        f"- 完全一致率：{round(overall['exactAgreement'] * 100)}%",
        f"- 一档内一致率：{round(overall['withinOne'] * 100)}%",
        f"- 模型整体偏差：{overall['bias']} 分（正数表示模型偏高）",
        "",
        "## 分维度",
        "",
        "| 维度 | 样本 | Spearman | MAE | 完全一致 | 一档内 | 偏差 |",
        "|---|---|---|---|---|---|---|",
    ]
    for dimension, stats in sorted(per_dimension.items()):
        lines.append(
            f"| {dimension} | {stats['count']} | {stats['spearman']} | {stats['mae']} | "
            f"{round(stats['exactAgreement'] * 100)}% | {round(stats['withinOne'] * 100)}% | {stats['bias']} |"
        )
    lines += [
        "",
        "## 说明",
        "",
        "- Spearman 衡量排序一致性，对分数绝对值不敏感；MAE 衡量绝对偏差。",
        "- 一档内一致率指模型分与人工分相差不超过 1 分的比例。",
        "- 偏差为正说明模型倾向于给高分，为负说明偏严。",
    ]
    return "\n".join(lines)

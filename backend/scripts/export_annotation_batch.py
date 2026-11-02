"""导出一批评分证据，供人工标注打分。

用法：

    python scripts/export_annotation_batch.py --size 40 --out annotation.csv

生成的 CSV 每行对应「一条证据（某个维度、某一轮）」，其中 human_score 留空待填，
填好后再跑 scripts/score_agreement.py 计算一致性。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import random
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.base import session_factory  # noqa: E402
from app.db.models import Evaluation, EvaluationEvidence, Message, TrainingSession  # noqa: E402

LABELS = {
    "logic": "内容与逻辑",
    "relevance": "贴合问题",
    "correctness": "信息完整",
    "concision": "表达干净",
}
SCORE_FIELD = {
    "logic": "logic_score",
    "relevance": "relevance_score",
    "correctness": "correctness_score",
    "concision": "concision_score",
}


async def collect(size: int) -> list[dict]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(EvaluationEvidence, Evaluation, Message, TrainingSession)
                .join(Evaluation, Evaluation.id == EvaluationEvidence.evaluation_id)
                .join(Message, Message.id == EvaluationEvidence.answer_message_id)
                .join(TrainingSession, TrainingSession.id == Evaluation.session_id)
                .where(Evaluation.degraded.is_(False))
            )
        ).all()
        question_ids = {row[0].question_message_id for row in rows if row[0].question_message_id}
        questions = {
            message.id: message.content
            for message in (
                await session.scalars(select(Message).where(Message.id.in_(question_ids)))
            ).all()
        } if question_ids else {}

    pool: list[dict] = []
    for evidence, evaluation, message, training in rows:
        dimension = evidence.dimension if evidence.dimension in SCORE_FIELD else None
        if dimension is None:
            continue
        pool.append(
            {
                "session_id": evaluation.session_id,
                "round_no": evidence.round_no,
                "dimension": LABELS[dimension],
                "dimension_key": dimension,
                "question": questions.get(evidence.question_message_id, ""),
                "answer": message.content,
                "quote": evidence.quote,
                "model_score": getattr(evaluation, SCORE_FIELD[dimension]),
                "channel": training.channel,
                "human_score": "",
                "note": "",
            }
        )

    # 按维度轮流抽样，保证四维都有样本
    random.seed(20261102)
    by_dimension: dict[str, list[dict]] = {}
    for row in pool:
        by_dimension.setdefault(row["dimension"], []).append(row)
    selected: list[dict] = []
    keys = list(by_dimension)
    while len(selected) < size and any(by_dimension.values()):
        for key in keys:
            bucket = by_dimension[key]
            if bucket and len(selected) < size:
                selected.append(bucket.pop(random.randrange(len(bucket))))
    return selected


async def main() -> None:
    parser = argparse.ArgumentParser(description="导出人工标注样本")
    parser.add_argument("--size", type=int, default=40)
    parser.add_argument("--out", default="annotation.csv")
    args = parser.parse_args()

    rows = await collect(args.size)
    if not rows:
        print("没有可导出的证据（需要非降级评分记录）")
        return

    target = Path(args.out)
    fields = ["session_id", "round_no", "dimension", "question", "answer", "quote", "model_score", "human_score", "note"]
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})

    print(f"已导出 {len(rows)} 条到 {target.resolve()}")
    print("下一步：用 Excel 打开，填写 human_score（1-5 整数），然后运行：")
    print(f"    python scripts/score_agreement.py --input {target.name}")


if __name__ == "__main__":
    asyncio.run(main())

"""读取人工标注结果，计算与模型评分的一致性。

用法：

    python scripts/score_agreement.py --input annotation.csv --report docs/评分一致性.md
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.features.evaluations.agreement import by_dimension, render_markdown, summarize  # noqa: E402


def load(path: Path) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    problems: list[str] = []
    with path.open(encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=2):
            raw = (row.get("human_score") or "").strip()
            if not raw:
                continue
            try:
                human = float(raw)
            except ValueError:
                problems.append(f"第 {index} 行 human_score 不是数字：{raw}")
                continue
            if not 1 <= human <= 5:
                problems.append(f"第 {index} 行分数超出 1-5：{human}")
                continue
            try:
                model = float(row.get("model_score") or 0)
            except ValueError:
                problems.append(f"第 {index} 行 model_score 异常")
                continue
            rows.append({"dimension": row.get("dimension") or "未知", "model": model, "human": human})
    return rows, problems


def main() -> None:
    parser = argparse.ArgumentParser(description="计算评分一致性")
    parser.add_argument("--input", default="annotation.csv")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.is_file():
        raise SystemExit(f"找不到文件：{path}")

    rows, problems = load(path)
    if not rows:
        raise SystemExit("没有填写的 human_score，无法统计")

    overall = summarize([(row["model"], row["human"]) for row in rows])
    per_dimension = by_dimension(rows)
    markdown = render_markdown(overall, per_dimension, len(rows))

    print(markdown)
    for problem in problems:
        print("  提示:", problem)

    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        print(f"\n报告已写入 {target}")


if __name__ == "__main__":
    main()

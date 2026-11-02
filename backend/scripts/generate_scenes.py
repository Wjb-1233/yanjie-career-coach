"""批量生成面试场景（草稿），生成后默认不对外开放，由管理员审核。

用法示例：

    # 预览 3 个 HR 初面场景，不写库
    python scripts/generate_scenes.py --category "HR 初面" --count 3 --dry-run

    # 生成并入库（active=False，需在后台手动开放）
    python scripts/generate_scenes.py --category "技术一面" --industry 互联网 --count 5

    # 查看待审核的草稿场景
    python scripts/generate_scenes.py --review
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.base import session_factory  # noqa: E402
from app.db.models import Scene  # noqa: E402
from app.features.scenes.taxonomy import normalize_bank  # noqa: E402
from app.infrastructure.llm import llm_gateway  # noqa: E402

CATEGORIES = ["HR 初面", "技术一面", "技术二面 / 复面", "交叉面 / 总监面", "HRBP/HR 终面", "大老板 / 高管终面"]
DIFFICULTIES = ["入门", "中级", "进阶"]
LABELS = {"内容与逻辑", "信息完整", "表达干净", "贴合问题"}

SYSTEM_PROMPT = """你是面试场景设计助手。根据给定类别与行业，输出 JSON：
{"scenes":[{"title":"不超过 18 字","roleName":"面试官身份","difficulty":"入门|中级|进阶",
"background":"两句话以内，说明这一轮考察什么","goal":"一句话沟通目标",
"openingLine":"面试官开场第一句话","tags":["标签1","标签2"],
"questionBank":[{"text":"必问题","dimension":"内容与逻辑|信息完整|表达干净|贴合问题","difficulty":"入门|中级|进阶"}]}]}
要求：每个场景 3 条必问题，覆盖不同维度；场景之间不要重复；只输出 JSON。"""


def _clean_text(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def validate(raw: dict, existing_titles: set[str]) -> tuple[list[dict], list[str]]:
    """校验并规整模型输出，返回 (可用场景, 问题列表)。"""
    problems: list[str] = []
    scenes: list[dict] = []
    for index, item in enumerate(raw.get("scenes") or [], start=1):
        if not isinstance(item, dict):
            problems.append(f"第 {index} 个场景格式不对")
            continue
        title = _clean_text(item.get("title"), 40)
        if not title:
            problems.append(f"第 {index} 个场景缺少标题")
            continue
        if title in existing_titles:
            problems.append(f"标题重复，已跳过：{title}")
            continue
        background = _clean_text(item.get("background"), 300)
        goal = _clean_text(item.get("goal"), 120)
        if not background or not goal:
            problems.append(f"{title} 缺少背景或目标")
            continue

        difficulty = _clean_text(item.get("difficulty"), 10)
        if difficulty not in DIFFICULTIES:
            difficulty = "中级"

        bank = []
        for question in normalize_bank(item.get("questionBank")):
            text = _clean_text(question["text"], 120)
            if not text:
                continue
            dimension = _clean_text(question.get("dimension"), 10)
            bank.append(
                {
                    "text": text,
                    "dimension": dimension if dimension in LABELS else None,
                    "difficulty": question.get("difficulty") if question.get("difficulty") in DIFFICULTIES else difficulty,
                }
            )
        if len(bank) < 2:
            problems.append(f"{title} 必问题不足 2 条")
            continue

        scenes.append(
            {
                "title": title,
                "role_name": _clean_text(item.get("roleName"), 40) or "招聘 HR",
                "difficulty": difficulty,
                "background": background,
                "goal": goal,
                "opening_line": _clean_text(item.get("openingLine"), 120) or f"你好，今天这场面试我们聊聊{title}。",
                "tags": [_clean_text(tag, 12) for tag in (item.get("tags") or [])][:3],
                "question_bank": bank,
            }
        )
        existing_titles.add(title)
    return scenes, problems


async def generate(category: str, industry: str, count: int, difficulty: str) -> dict:
    prompt = (
        f"类别：{category}\n行业：{industry}\n难度倾向：{difficulty}\n数量：{count}\n"
        "请保证场景真实、问题具体，避免空话。"
    )
    return await llm_gateway.complete_json(SYSTEM_PROMPT, prompt, temperature=0.7, max_tokens=2500)


async def save(scenes: list[dict], category: str, industry: str, active: bool) -> list[str]:
    created: list[str] = []
    async with session_factory() as session:
        for scene in scenes:
            row = Scene(
                category=category,
                industry=industry,
                position="通用岗位",
                role_name=scene["role_name"],
                difficulty=scene["difficulty"],
                background=scene["background"],
                goal=scene["goal"],
                tags=scene["tags"],
                opening_line=scene["opening_line"],
                question_bank=scene["question_bank"],
                active=active,
            )
            session.add(row)
            created.append(scene["title"])
        await session.commit()
    return created


async def review() -> None:
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(Scene).where(Scene.active.is_(False)).order_by(Scene.created_at.desc()).limit(30)
            )
        ).all()
    if not rows:
        print("没有待审核的草稿场景")
        return
    print(f"待审核草稿：{len(rows)} 个\n")
    for row in rows:
        print(f"· [{row.category}] {row.title}（{row.difficulty}） 必问题 {len(normalize_bank(row.question_bank))} 条")


async def main() -> None:
    parser = argparse.ArgumentParser(description="批量生成面试场景草稿")
    parser.add_argument("--category", choices=CATEGORIES, default="HR 初面")
    parser.add_argument("--industry", default="互联网")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--difficulty", choices=DIFFICULTIES, default="中级")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    parser.add_argument("--active", action="store_true", help="生成后直接对学员开放")
    parser.add_argument("--review", action="store_true", help="查看待审核草稿")
    args = parser.parse_args()

    if args.review:
        await review()
        return

    if not llm_gateway.configured:
        raise SystemExit("LLM_API_KEY 未配置，无法生成场景")

    raw = await generate(args.category, args.industry, min(args.count, 10), args.difficulty)
    async with session_factory() as session:
        existing = set((await session.scalars(select(Scene.title))).all())

    scenes, problems = validate(raw, existing)
    print(f"生成 {len(scenes)} 个可用场景，{len(problems)} 处问题")
    for problem in problems:
        print("  跳过:", problem)
    for scene in scenes:
        print(f"\n· {scene['title']}（{scene['difficulty']}）  {scene['role_name']}")
        print(f"  背景：{scene['background']}")
        print(f"  目标：{scene['goal']}")
        for question in scene["question_bank"]:
            print(f"  - [{question['dimension'] or '-'}] {question['text']}")

    if args.dry_run:
        print("\n（dry-run，未写库）")
        return
    if not scenes:
        print("没有可写入的场景")
        return

    created = await save(scenes, args.category, args.industry, args.active)
    state = "已开放" if args.active else "草稿（需在后台开放）"
    print(f"\n已写入 {len(created)} 个场景：{state}")


if __name__ == "__main__":
    asyncio.run(main())

"""按场景核心思想重写「必问问题」（每个场景 2 条）。"""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.db.base import session_factory
from app.db.models import Scene
from app.features.scenes.taxonomy import normalize_bank
from app.infrastructure.llm import llm_gateway

SYSTEM_PROMPT = """你是中文面试官，负责为一个面试场景设计「必问问题」。
要求：
1. 恰好输出 2 条问题，第一条是半开场性质的问题（自我介绍或与岗位动机相关），第二条必须直接考察该场景的核心思想。
2. 每条 12–45 字，口语化，像真人面试官开口问的话，不要出现「考察」「核心思想」「候选人」这类元叙述。
3. 不得编造具体公司名或候选人经历；不要给出答案。
4. 只输出 JSON：{"questions":["...","..."]}"""


def review(questions: list[str], scene: Scene) -> list[str]:
    cleaned = [item.strip().strip("？?") + "？" for item in questions if isinstance(item, str)]
    result = [item for item in cleaned if 10 <= len(item) <= 60]
    deduped: list[str] = []
    for item in result:
        if item not in deduped:
            deduped.append(item)
    return deduped[:2]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", type=str, default="")
    args = parser.parse_args()

    async with session_factory() as session:
        query = select(Scene).order_by(Scene.created_at)
        if args.only:
            query = query.where(Scene.id == args.only)
        scenes = (await session.scalars(query)).all()
        if args.limit:
            scenes = scenes[: args.limit]

        changed = 0
        for index, scene in enumerate(scenes, start=1):
            material = {
                "场景": scene.title,
                "分类": scene.category,
                "岗位": scene.position,
                "难度": scene.difficulty,
                "背景": scene.background[:400],
                "训练目标": scene.goal,
                "核心思想": scene.core_idea or scene.goal,
                "现有问题": [item["text"] for item in normalize_bank(scene.question_bank)],
            }
            try:
                raw = await llm_gateway.complete_json(
                    SYSTEM_PROMPT,
                    json.dumps(material, ensure_ascii=False),
                    temperature=0.5,
                    max_tokens=400,
                )
                questions = review(list(raw.get("questions") or []), scene)
            except Exception as exc:  # noqa: BLE001
                print(f"[{index}/{len(scenes)}] FAIL {scene.title}: {type(exc).__name__}")
                continue

            if len(questions) < 2:
                print(f"[{index}/{len(scenes)}] SKIP {scene.title}: 生成不足")
                continue

            print(f"[{index}/{len(scenes)}] {scene.title}")
            for question in questions:
                print("    -", question)
            if not args.dry_run:
                scene.question_bank = [
                    {"text": item, "dimension": None, "difficulty": None} for item in questions
                ]
                changed += 1

        if not args.dry_run:
            await session.commit()
        print(f"updated={changed} dry_run={args.dry_run}")


asyncio.run(main())

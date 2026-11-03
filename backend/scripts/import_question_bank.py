"""从 YAML 导入题库：按标题新建或更新。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.base import session_factory  # noqa: E402
from app.db.models import Scene  # noqa: E402
from app.features.scenes.bank import validate_scene  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="导入题库")
    parser.add_argument("--file", default="content/scene-bank.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update", action="store_true", help="已存在同名场景时更新内容")
    parser.add_argument("--active", action="store_true", help="新建场景直接开放")
    args = parser.parse_args()

    source = Path(args.file)
    if not source.is_file():
        raise SystemExit(f"找不到文件：{source}")

    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    entries = payload.get("scenes") or []
    created, updated, skipped = 0, 0, 0
    problems: list[str] = []

    async with session_factory() as session:
        existing = {scene.title: scene for scene in (await session.scalars(select(Scene))).all()}
        for raw in entries:
            scene_data, issues = validate_scene(raw)
            problems.extend(issues)
            if scene_data is None:
                skipped += 1
                continue

            current = existing.get(scene_data["title"])
            if current is not None:
                if not args.update:
                    skipped += 1
                    problems.append(f"{scene_data['title']} 已存在，跳过（用 --update 覆盖）")
                    continue
                for key in ("category", "difficulty", "role_name", "background", "goal", "opening_line", "tags", "question_bank"):
                    setattr(current, key, scene_data[key])
                updated += 1
                continue

            session.add(
                Scene(
                    category=scene_data["category"],
                    industry="综合行业",
                    position="通用岗位",
                    role_name=scene_data["role_name"],
                    difficulty=scene_data["difficulty"],
                    background=scene_data["background"],
                    goal=scene_data["goal"],
                    tags=scene_data["tags"],
                    opening_line=scene_data["opening_line"],
                    question_bank=scene_data["question_bank"],
                    active=args.active,
                )
            )
            created += 1

        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()

    print(f"新建 {created} 个，更新 {updated} 个，跳过 {skipped} 个{'（dry-run，未写库）' if args.dry_run else ''}")
    for problem in problems[:10]:
        print("  提示:", problem)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

"""把场景题库导出成 YAML，便于版本管理。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.base import session_factory  # noqa: E402
from app.db.models import Scene  # noqa: E402
from app.features.scenes.bank import build_bank  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="导出题库")
    parser.add_argument("--out", default="content/scene-bank.yaml")
    parser.add_argument("--active-only", action="store_true", help="只导出已开放场景")
    args = parser.parse_args()

    async with session_factory() as session:
        query = select(Scene).order_by(Scene.category, Scene.title)
        if args.active_only:
            query = query.where(Scene.active.is_(True))
        scenes = list((await session.scalars(query)).all())

    payload = build_bank(scenes)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"已导出 {payload['count']} 个场景到 {target}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

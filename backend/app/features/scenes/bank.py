"""题库的版本化格式：导出/导入 YAML。

结构：

version: 1
exportedAt: 2026-11-03T...
scenes:
  - id: scene-interview-01
    category: HR 初面
    title: ...
    difficulty: 中级
    roleName: 招聘 HR
    background: ...
    goal: ...
    openingLine: ...
    tags: [标签]
    questions:
      - text: ...
        dimension: 贴合问题
        difficulty: 中级
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import Scene
from app.features.scenes.taxonomy import normalize_bank

BANK_VERSION = 1
DIMENSIONS = {"内容与逻辑", "信息完整", "表达干净", "贴合问题"}
DIFFICULTIES = {"入门", "中级", "进阶"}


def scene_to_dict(scene: Scene) -> dict:
    return {
        "id": scene.id,
        "category": scene.category,
        "title": scene.title,
        "difficulty": scene.difficulty,
        "roleName": scene.role_name,
        "background": scene.background,
        "goal": scene.goal,
        "openingLine": scene.opening_line,
        "tags": list(scene.tags or []),
        "questions": [
            {
                "text": item["text"],
                "dimension": item.get("dimension"),
                "difficulty": item.get("difficulty"),
            }
            for item in normalize_bank(scene.question_bank)
        ],
    }


def build_bank(scenes: list[Scene]) -> dict:
    return {
        "version": BANK_VERSION,
        "exportedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(scenes),
        "scenes": [scene_to_dict(scene) for scene in scenes],
    }


def validate_scene(raw: dict) -> tuple[dict | None, list[str]]:
    """校验导入条目，返回 (规整后的场景, 问题列表)。"""
    problems: list[str] = []
    title = str(raw.get("title") or "").strip()
    if not title:
        return None, ["缺少 title"]
    category = str(raw.get("category") or "").strip()
    if not category:
        problems.append(f"{title} 缺少 category，已跳过")
        return None, problems

    difficulty = str(raw.get("difficulty") or "中级").strip()
    if difficulty not in DIFFICULTIES:
        difficulty = "中级"

    questions = []
    for item in raw.get("questions") or []:
        if isinstance(item, str):
            text = item.strip()
            dimension = None
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            dimension = item.get("dimension")
        else:
            continue
        if not text:
            continue
        questions.append(
            {
                "text": text[:120],
                "dimension": dimension if dimension in DIMENSIONS else None,
                "difficulty": difficulty,
            }
        )
    if len(questions) < 1:
        problems.append(f"{title} 没有可用问题，已跳过")
        return None, problems

    return {
        "id": str(raw.get("id") or "").strip() or None,
        "category": category,
        "title": title[:100],
        "difficulty": difficulty,
        "role_name": str(raw.get("roleName") or "招聘 HR")[:80],
        "background": str(raw.get("background") or "")[:300],
        "goal": str(raw.get("goal") or "")[:120],
        "opening_line": str(raw.get("openingLine") or "")[:120],
        "tags": [str(tag)[:12] for tag in (raw.get("tags") or [])][:3],
        "question_bank": questions,
    }, problems

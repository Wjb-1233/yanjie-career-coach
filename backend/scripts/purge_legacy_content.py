"""清掉库里残留的旧维度文案。

处理三类：
1. 计划里的微课（lesson）含旧维度词 → 重新生成；
2. 评分摘要 / 建议含旧词 → 按新维度做文本替换；
3. 课程维度仍是旧命名 → 映射到四维。

视频缓存由调用方在结束后清理（内容变了，哈希也会变）。
"""

import asyncio
import copy
import json

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.legacy_text import modernize
from app.db.base import session_factory
from app.db.models import Course, Evaluation, TrainingPlan
from app.features.plans.service import personalized_lesson

LEGACY_WORDS = ("逻辑性", "得体性", "正确性", "针对性", "简洁度", "感染力", "五维")

COURSE_DIMENSION_MAP = {
    "逻辑性": "内容与逻辑",
    "针对性": "贴合问题",
    "正确性": "信息完整",
    "感染力": "信息完整",
    "简洁度": "表达干净",
    "得体性": "表达干净",
}


def has_legacy(value) -> bool:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return any(word in text for word in LEGACY_WORDS)


async def main() -> None:
    regenerated = 0
    rewritten = 0
    courses_fixed = 0

    async with session_factory() as session:
        plans = list((await session.scalars(select(TrainingPlan))).all())

        # 第一遍：修正计划自身的维度与文案（提交后再动微课，避免拿着旧副本覆盖结果）
        for plan in plans:
            mapped = COURSE_DIMENSION_MAP.get(plan.focus_dimension)
            if mapped and mapped != plan.focus_dimension:
                plan.focus_dimension = mapped
                courses_fixed += 1
            if plan.title and has_legacy(plan.title):
                plan.title = modernize(plan.title)
                rewritten += 1
            tasks = copy.deepcopy(plan.tasks or [])
            touched = False
            for task in tasks:
                if task.get("task") and has_legacy(task.get("task")):
                    task["task"] = modernize(task["task"])
                    touched = True
                    rewritten += 1
            if touched:
                plan.tasks = tasks
                flag_modified(plan, "tasks")
        await session.commit()

        # 第二遍：重新生成含旧词的微课
        for plan in plans:
            for task in plan.tasks or []:
                lesson = task.get("lesson")
                if lesson and has_legacy(lesson):
                    try:
                        await personalized_lesson(session, plan.user_id, plan.id, task.get("key", "course"), force=True)
                        regenerated += 1
                        print(f"  重生成微课 plan={plan.id[:8]} task={task.get('key')}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"  重生成失败 plan={plan.id[:8]}: {type(exc).__name__}")

        # 第三遍：任务文案与微课标题对齐（历史任务文案里写的是旧标题）
        for plan in plans:
            tasks = copy.deepcopy(plan.tasks or [])
            touched = False
            for task in tasks:
                lesson = task.get("lesson") or {}
                if task.get("actionType") == "COURSE" and lesson.get("title"):
                    expected = f"学习微课《{lesson['title']}》，按三个步骤完成表达练习"
                    if task.get("task") != expected:
                        task["task"] = expected
                        touched = True
            if touched:
                plan.tasks = tasks
                flag_modified(plan, "tasks")
        await session.commit()

        for evaluation in (await session.scalars(select(Evaluation))).all():
            if has_legacy(evaluation.summary or ""):
                evaluation.summary = modernize(evaluation.summary)
                rewritten += 1
            if evaluation.suggestions and has_legacy(evaluation.suggestions):
                evaluation.suggestions = modernize(evaluation.suggestions)
                rewritten += 1

        for course in (await session.scalars(select(Course))).all():
            mapped = COURSE_DIMENSION_MAP.get(course.dimension)
            if mapped and mapped != course.dimension:
                course.dimension = mapped
                courses_fixed += 1

        await session.commit()

    print(f"微课重生成 {regenerated} 门，文本替换 {rewritten} 处，课程维度修正 {courses_fixed} 条")


asyncio.run(main())

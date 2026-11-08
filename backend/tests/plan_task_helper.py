"""测试辅助：给新计划注入一个可训练任务（产品已不再自动生成复练任务）。"""

import json
import os
import sqlite3


def add_scene_task(plan_id: str, scene_id: str, key: str = "manual-retry") -> str:
    url = os.environ["DATABASE_URL"]
    path = url.split("///", 1)[-1]
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT tasks FROM training_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        tasks = json.loads(row[0]) if row and row[0] else []
        tasks.insert(0, {
            "key": key,
            "day": 1,
            "task": "手动注入的训练任务",
            "actionType": "SCENE",
            "sceneId": scene_id,
            "completed": False,
            "completedAt": None,
            "evidence": None,
        })
        connection.execute(
            "UPDATE training_plans SET tasks = ? WHERE id = ?",
            (json.dumps(tasks, ensure_ascii=False), plan_id),
        )
        connection.commit()
    finally:
        connection.close()
    return key

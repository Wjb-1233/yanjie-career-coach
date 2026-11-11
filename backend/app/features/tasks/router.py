"""任务查询接口：前端轮询进度。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_found
from app.core.responses import ok
from app.core.security import CurrentUser
from app.features.tasks.service import get_task, queue_eta

router = APIRouter(prefix="/tasks", tags=["任务"])


@router.get("/{task_id}")
async def read_task(task_id: str, user: CurrentUser) -> dict:
    task = await get_task(user.id, task_id)
    if task is None:
        raise not_found("任务")
    eta = await queue_eta(task.id) if task.status in {"PENDING", "RUNNING"} else {}
    return ok(
        {
            "id": task.id,
            "kind": task.kind,
            "status": task.status,
            "progress": task.progress,
            "stage": task.stage,
            "error": task.error,
            "sessionId": (task.result or {}).get("sessionId"),
            "vision": (task.result or {}).get("vision"),
            "degraded": bool((task.result or {}).get("degraded")),
            "transcriptReason": (task.result or {}).get("transcriptReason"),
            "queue": eta,
        }
    )

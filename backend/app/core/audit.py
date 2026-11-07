"""管理台操作留痕。

中间件在请求成功后调用，独立开会话写入；写失败只记日志，绝不影响业务请求。
"""

from __future__ import annotations

import logging

from app.db.base import session_factory
from app.db.models import AuditLog

logger = logging.getLogger(__name__)

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


async def record(
    *,
    actor_id: str | None,
    actor_email: str | None,
    method: str,
    route: str,
    status: int,
    target_id: str | None,
    ip: str | None,
    request_id: str | None,
) -> None:
    try:
        async with session_factory() as session:
            session.add(
                AuditLog(
                    actor_id=actor_id,
                    actor_email=actor_email,
                    method=method,
                    route=route[:160],
                    status=status,
                    target_id=(target_id or None),
                    ip=(ip or None),
                    request_id=request_id,
                )
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit.write_failed error_type=%s", type(exc).__name__)

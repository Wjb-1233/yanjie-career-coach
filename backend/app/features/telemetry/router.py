"""前端错误上报：白屏/未捕获异常至少留下可观测信号。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response

from app.core import metrics
from app.core.schemas import ApiModel
from app.infrastructure.rate_limit import limit_client_error
from pydantic import Field

logger = logging.getLogger("app.client")

router = APIRouter(prefix="/client-errors", tags=["可观测"])


class ClientErrorReport(ApiModel):
    message: str = Field(min_length=1, max_length=300)
    stack: str | None = Field(default=None, max_length=2000)
    route: str | None = Field(default=None, max_length=200)
    user_agent: str | None = Field(default=None, max_length=300)


@router.post("", status_code=204, dependencies=[Depends(limit_client_error)])
async def report_client_error(body: ClientErrorReport) -> Response:
    logger.warning(
        "client.error",
        extra={
            "err_message": body.message,
            "err_route": body.route,
            "err_user_agent": body.user_agent,
        },
    )
    metrics.incr_event("client_error", "received")
    return Response(status_code=204)

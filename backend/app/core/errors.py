from dataclasses import dataclass
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.errors")


@dataclass
class AppError(Exception):
    status_code: int
    code: str
    detail: str
    headers: dict[str, str] | None = None


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "type": f"https://career-coach.local/errors/{exc.code.lower()}",
            "title": exc.code,
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": request.url.path,
            "requestId": getattr(request.state, "request_id", None),
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in item["loc"][1:]), "message": item["msg"]}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "type": "https://career-coach.local/errors/validation_error",
            "title": "VALIDATION_ERROR",
            "status": 422,
            "detail": "请求参数校验失败",
            "instance": request.url.path,
            "requestId": getattr(request.state, "request_id", None),
            "errors": errors,
        },
    )


def not_found(resource: str) -> AppError:
    return AppError(404, "NOT_FOUND", f"{resource}不存在")


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "request.unexpected_error",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://career-coach.local/errors/internal_error",
            "title": "INTERNAL_ERROR",
            "status": 500,
            "detail": "服务暂时不可用，请稍后重试",
            "instance": request.url.path,
            "requestId": request_id,
        },
    )


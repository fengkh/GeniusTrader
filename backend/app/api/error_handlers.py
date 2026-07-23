import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError, ErrorCode

logger = logging.getLogger("app.errors")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(
    request: Request,
    *,
    code: ErrorCode,
    message: str,
    status_code: int,
    details: object | None = None,
) -> JSONResponse:
    request.state.error_code = code.value
    body: dict[str, object] = {
        "error": {
            "code": code.value,
            "message": message,
            "request_id": _request_id(request),
        }
    }
    if details is not None:
        body["error"]["details"] = details  # type: ignore[index]
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"X-Request-ID": _request_id(request)},
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    safe_details = [
        {"loc": error.get("loc"), "msg": error.get("msg"), "type": error.get("type")}
        for error in exc.errors()
    ]
    return error_response(
        request,
        code=ErrorCode.VALIDATION_ERROR,
        message="请求参数无效",
        status_code=422,
        details=safe_details,
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception(
        "database error",
        extra={"request_id": _request_id(request), "error_code": ErrorCode.DATABASE_UNAVAILABLE.value},
    )
    return error_response(
        request,
        code=ErrorCode.DATABASE_UNAVAILABLE,
        message="数据库暂时不可用",
        status_code=503,
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "internal error",
        extra={"request_id": _request_id(request), "error_code": ErrorCode.INTERNAL_ERROR.value},
    )
    return error_response(
        request,
        code=ErrorCode.INTERNAL_ERROR,
        message="服务暂时不可用",
        status_code=500,
    )

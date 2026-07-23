import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.errors import ErrorCode
from app.core.security import generate_request_id, hash_csrf_token, hash_session_token
from app.repositories.sessions import get_session_by_token_hash

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_EXEMPT_PATHS = {"/api/v1/auth/login"}


class CsrfProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._should_check(request):
            return await call_next(request)

        settings = get_settings()
        session_token = request.cookies.get(settings.session_cookie_name)
        if not session_token:
            return await call_next(request)

        csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
        csrf_header = request.headers.get(CSRF_HEADER_NAME)
        if not csrf_cookie or not csrf_header:
            return self._error_response(
                request,
                ErrorCode.CSRF_TOKEN_REQUIRED,
                "缺少 CSRF Token",
                status_code=403,
            )
        if not secrets.compare_digest(csrf_cookie, csrf_header):
            return self._error_response(
                request,
                ErrorCode.CSRF_TOKEN_INVALID,
                "CSRF Token 无效",
                status_code=403,
            )

        async with AsyncSessionLocal() as db_session:
            session_row = await get_session_by_token_hash(db_session, hash_session_token(session_token))
            if not session_row:
                return await call_next(request)
            if not session_row.csrf_token_hash:
                return self._error_response(
                    request,
                    ErrorCode.CSRF_TOKEN_INVALID,
                    "CSRF Token 无效",
                    status_code=403,
                )
            if not secrets.compare_digest(session_row.csrf_token_hash, hash_csrf_token(csrf_header)):
                return self._error_response(
                    request,
                    ErrorCode.CSRF_TOKEN_INVALID,
                    "CSRF Token 无效",
                    status_code=403,
                )

        return await call_next(request)

    @staticmethod
    def _should_check(request: Request) -> bool:
        return (
            request.method.upper() in UNSAFE_METHODS
            and request.url.path.startswith("/api/v1")
            and request.url.path not in CSRF_EXEMPT_PATHS
        )

    @staticmethod
    def _error_response(
        request: Request,
        code: ErrorCode,
        message: str,
        *,
        status_code: int,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or generate_request_id()
        request.state.request_id = request_id
        request.state.error_code = code.value
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code.value,
                    "message": message,
                    "request_id": request_id,
                }
            },
            headers={"X-Request-ID": request_id},
        )

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    SESSION_REQUIRED = "SESSION_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    FORBIDDEN = "FORBIDDEN"
    USERNAME_ALREADY_EXISTS = "USERNAME_ALREADY_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    STOCK_NOT_FOUND = "STOCK_NOT_FOUND"
    WATCHLIST_ITEM_NOT_FOUND = "WATCHLIST_ITEM_NOT_FOUND"
    WATCHLIST_ITEM_ALREADY_EXISTS = "WATCHLIST_ITEM_ALREADY_EXISTS"
    WATCHLIST_LIMIT_EXCEEDED = "WATCHLIST_LIMIT_EXCEEDED"
    GROUP_NOT_FOUND = "GROUP_NOT_FOUND"
    TAG_NOT_FOUND = "TAG_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

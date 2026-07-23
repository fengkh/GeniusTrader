import hashlib
import re
import secrets

from pwdlib import PasswordHash

from app.core.errors import AppError, ErrorCode

_password_hash = PasswordHash.recommended()
_weak_passwords = {
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password123",
    "root",
    "admin",
    "qwerty123",
}


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def validate_password_strength(password: str, username: str | None = None) -> None:
    normalized = password.strip()
    username_normalized = (username or "").strip().lower()
    if len(normalized) < 10:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "密码长度至少需要10位",
            status_code=422,
        )
    if username_normalized and normalized.lower() == username_normalized:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "密码不能与用户名完全相同",
            status_code=422,
        )
    if normalized.lower() in _weak_passwords:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "密码过于常见，请更换更强的密码",
            status_code=422,
        )
    if not re.search(r"[A-Za-z]", normalized) or not re.search(r"\d", normalized):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "密码至少需要同时包含字母和数字",
            status_code=422,
        )


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_csrf_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_request_id() -> str:
    return secrets.token_hex(16)


def sanitize_request_id(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) > 64:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", value):
        return None
    return value

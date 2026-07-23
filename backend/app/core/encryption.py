from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode("ascii")


class SecretCipher:
    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise AppError(
                ErrorCode.ENCRYPTION_KEY_REQUIRED,
                "缺少应用加密密钥",
                status_code=500,
            )
        try:
            self._fernet = MultiFernet([Fernet(key.encode("ascii")) for key in keys])
        except (ValueError, TypeError) as exc:
            raise AppError(
                ErrorCode.ENCRYPTION_KEY_REQUIRED,
                "应用加密密钥格式无效",
                status_code=500,
            ) from exc

    def encrypt_secret(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode("utf-8")).decode("ascii")

    def decrypt_secret(self, encrypted_secret: str) -> str:
        try:
            return self._fernet.decrypt(encrypted_secret.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise AppError(
                ErrorCode.ENCRYPTION_KEY_REQUIRED,
                "无法解密已保存密钥",
                status_code=500,
            ) from exc


def get_secret_cipher(settings: Settings) -> SecretCipher:
    return SecretCipher(settings.encryption_keys)


def masked_secret_display(secret: str | None = None, *, configured: bool | None = None) -> str | None:
    if configured is False:
        return None
    if not secret:
        return "configured" if configured else None
    if len(secret) <= 8:
        return "****"
    return f"{secret[:2]}****{secret[-4:]}"

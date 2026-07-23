from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
LOCAL_DATABASE_ENV = REPO_ROOT / ".local" / "database.env"
BACKEND_ENV = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_name: str = Field(default="GeniusTrader API", validation_alias="APP_NAME")
    app_timezone: str = Field(default="Asia/Shanghai", validation_alias="APP_TIMEZONE")
    database_url: str = Field(min_length=1, validation_alias="DATABASE_URL")
    session_cookie_name: str = Field(
        default="geniustrader_session",
        validation_alias="SESSION_COOKIE_NAME",
    )
    session_ttl_seconds: int = Field(default=604800, validation_alias="SESSION_TTL_SECONDS")
    session_cookie_secure: bool = Field(default=False, validation_alias="SESSION_COOKIE_SECURE")
    cors_allowed_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=(LOCAL_DATABASE_ENV, BACKEND_ENV),
        env_file_encoding="utf-8-sig",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

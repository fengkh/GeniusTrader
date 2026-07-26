from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
LOCAL_DATABASE_ENV = REPO_ROOT / ".local" / "database.env"
LOCAL_APP_ENV = REPO_ROOT / ".local" / "app.env"
LOCAL_ANNOUNCEMENT_ENV = REPO_ROOT / ".local" / "announcement.env"
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
    csrf_cookie_name: str = Field(
        default="geniustrader_csrf",
        validation_alias="CSRF_COOKIE_NAME",
    )
    session_ttl_seconds: int = Field(default=604800, validation_alias="SESSION_TTL_SECONDS")
    session_cookie_secure: bool = Field(default=False, validation_alias="SESSION_COOKIE_SECURE")
    cors_allowed_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    app_encryption_keys: str = Field(default="", validation_alias="APP_ENCRYPTION_KEYS")
    ai_request_timeout_seconds: int = Field(default=60, validation_alias="AI_REQUEST_TIMEOUT_SECONDS")
    ai_max_input_chars: int = Field(default=30000, validation_alias="AI_MAX_INPUT_CHARS")
    ai_max_output_tokens: int = Field(default=4000, validation_alias="AI_MAX_OUTPUT_TOKENS")
    ai_max_retries: int = Field(default=1, validation_alias="AI_MAX_RETRIES")
    content_fetch_timeout_seconds: int = Field(
        default=10,
        validation_alias="CONTENT_FETCH_TIMEOUT_SECONDS",
    )
    content_fetch_max_bytes: int = Field(default=2097152, validation_alias="CONTENT_FETCH_MAX_BYTES")
    content_fetch_max_redirects: int = Field(default=3, validation_alias="CONTENT_FETCH_MAX_REDIRECTS")
    content_allowed_types: str = Field(
        default="text/html,text/plain,application/xhtml+xml",
        validation_alias="CONTENT_ALLOWED_TYPES",
    )
    allow_private_ai_base_url: bool = Field(default=False, validation_alias="ALLOW_PRIVATE_AI_BASE_URL")
    information_max_manual_text_chars: int = Field(
        default=50000,
        validation_alias="INFORMATION_MAX_MANUAL_TEXT_CHARS",
    )
    external_source_registry_enabled: bool = Field(
        default=True,
        validation_alias="EXTERNAL_SOURCE_REGISTRY_ENABLED",
    )
    announcement_ingestion_enabled: bool = Field(
        default=False,
        validation_alias="ANNOUNCEMENT_INGESTION_ENABLED",
    )
    announcement_real_network_enabled: bool = Field(
        default=False,
        validation_alias="ANNOUNCEMENT_REAL_NETWORK_ENABLED",
    )
    announcement_cninfo_enabled: bool = Field(
        default=False,
        validation_alias="ANNOUNCEMENT_CNINFO_ENABLED",
    )
    announcement_sse_enabled: bool = Field(
        default=False,
        validation_alias="ANNOUNCEMENT_SSE_ENABLED",
    )
    announcement_document_extraction_enabled: bool = Field(
        default=False,
        validation_alias="ANNOUNCEMENT_DOCUMENT_EXTRACTION_ENABLED",
    )
    announcement_max_symbols_per_run: int = Field(
        default=20,
        validation_alias="ANNOUNCEMENT_MAX_SYMBOLS_PER_RUN",
    )
    announcement_max_records_per_run: int = Field(
        default=50,
        validation_alias="ANNOUNCEMENT_MAX_RECORDS_PER_RUN",
    )
    announcement_max_requests_per_run: int = Field(
        default=30,
        validation_alias="ANNOUNCEMENT_MAX_REQUESTS_PER_RUN",
    )
    announcement_request_delay_ms: int = Field(
        default=1000,
        validation_alias="ANNOUNCEMENT_REQUEST_DELAY_MS",
    )
    announcement_request_timeout_seconds: int = Field(
        default=15,
        validation_alias="ANNOUNCEMENT_REQUEST_TIMEOUT_SECONDS",
    )
    announcement_max_response_bytes: int = Field(
        default=5242880,
        validation_alias="ANNOUNCEMENT_MAX_RESPONSE_BYTES",
    )
    announcement_max_pdf_bytes: int = Field(
        default=20971520,
        validation_alias="ANNOUNCEMENT_MAX_PDF_BYTES",
    )
    announcement_max_pdf_pages: int = Field(
        default=300,
        validation_alias="ANNOUNCEMENT_MAX_PDF_PAGES",
    )
    announcement_sync_lookback_days: int = Field(
        default=7,
        validation_alias="ANNOUNCEMENT_SYNC_LOOKBACK_DAYS",
    )

    model_config = SettingsConfigDict(
        env_file=(LOCAL_DATABASE_ENV, LOCAL_APP_ENV, LOCAL_ANNOUNCEMENT_ENV, BACKEND_ENV),
        env_file_encoding="utf-8-sig",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def encryption_keys(self) -> list[str]:
        return [key.strip() for key in self.app_encryption_keys.split(",") if key.strip()]

    @property
    def allowed_content_types(self) -> set[str]:
        return {item.strip().lower() for item in self.content_allowed_types.split(",") if item.strip()}

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

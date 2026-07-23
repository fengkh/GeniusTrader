import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AIProviderCreate(BaseModel):
    provider_name: str = Field(min_length=1, max_length=100)
    base_url: HttpUrl
    model_name: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1, max_length=4000)
    enabled: bool = False
    request_timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    max_output_tokens: int | None = Field(default=None, ge=1, le=20000)


class AIProviderUpdate(BaseModel):
    provider_name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: HttpUrl | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1, max_length=4000)
    enabled: bool | None = None
    request_timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    max_output_tokens: int | None = Field(default=None, ge=1, le=20000)

    @field_validator("api_key")
    @classmethod
    def reject_blank_api_key(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("api_key cannot be blank")
        return value


class AIProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_name: str
    api_style: Literal["openai_chat_completions"]
    base_url: str
    model_name: str
    enabled: bool
    api_key_configured: bool
    api_key_masked: str | None
    request_timeout_seconds: int | None
    max_output_tokens: int | None
    last_test_status: str | None
    last_tested_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class AIProviderTestResult(BaseModel):
    provider_id: uuid.UUID
    status: str
    error_code: str | None = None
    tested_at: datetime

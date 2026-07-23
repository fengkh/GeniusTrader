from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmModel


class UserRead(OrmModel):
    id: UUID
    username: str
    display_name: str
    role: str
    status: str
    must_change_password: bool
    created_at: datetime


class CurrentUserRead(OrmModel):
    id: UUID
    username: str
    display_name: str
    role: str
    status: str
    must_change_password: bool


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str | None = Field(default=None, max_length=100)
    temporary_password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value

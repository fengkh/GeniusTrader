from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmModel
from app.schemas.stock import StockRead


class WatchlistGroupRead(OrmModel):
    id: UUID
    name: str
    sort_order: int
    is_default: bool
    created_at: datetime
    updated_at: datetime


class WatchlistGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class WatchlistGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class UserTagRead(OrmModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class UserTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class UserTagUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class WatchlistItemRead(OrmModel):
    id: UUID
    stock: StockRead
    group: WatchlistGroupRead | None
    tags: list[UserTagRead]
    attention_reason: str | None
    notes: str | None
    sort_order: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WatchlistItemCreate(BaseModel):
    stock_id: UUID
    group_id: UUID | None = None
    attention_reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    tag_ids: list[UUID] = Field(default_factory=list)


class WatchlistItemUpdate(BaseModel):
    group_id: UUID | None = None
    attention_reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    sort_order: int | None = Field(default=None, ge=0)
    tag_ids: list[UUID] | None = None

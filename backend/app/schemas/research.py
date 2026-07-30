import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmModel
from app.schemas.stock import StockRead

ResearchTaskType = Literal["verification", "observation", "follow_up", "missing_document", "user_note"]
ResearchTaskStatus = Literal[
    "pending",
    "monitoring",
    "confirmed",
    "disproved",
    "partially_confirmed",
    "unable_to_determine",
    "no_longer_applicable",
    "dismissed",
]
ResearchTaskPriority = Literal["low", "medium", "high"]
ResearchTaskSourceType = Literal["user", "information_analysis", "daily_review", "announcement", "system_rule"]


class ResearchTaskCreate(BaseModel):
    stock_id: uuid.UUID | None = None
    task_type: ResearchTaskType = "verification"
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    status: ResearchTaskStatus = "pending"
    priority: ResearchTaskPriority = "medium"
    source_type: ResearchTaskSourceType = "user"
    source_information_item_id: uuid.UUID | None = None
    source_analysis_version_id: uuid.UUID | None = None
    source_daily_review_id: uuid.UUID | None = None
    source_daily_review_version_id: uuid.UUID | None = None
    due_date: date | None = None
    current_evidence_summary: str | None = Field(default=None, max_length=4000)
    suggestion_identifier: str | None = Field(default=None, max_length=120)

    @field_validator("title", "description", "current_evidence_summary", "suggestion_identifier")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class ResearchTaskPatch(BaseModel):
    stock_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    priority: ResearchTaskPriority | None = None
    due_date: date | None = None
    current_evidence_summary: str | None = Field(default=None, max_length=4000)
    resolution_note: str | None = Field(default=None, max_length=4000)

    @field_validator("title", "description", "current_evidence_summary", "resolution_note")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class ResearchTaskStatusUpdate(BaseModel):
    status: ResearchTaskStatus
    note: str | None = Field(default=None, max_length=4000)
    evidence_information_item_id: uuid.UUID | None = None
    evidence_analysis_version_id: uuid.UUID | None = None
    evidence_daily_review_version_id: uuid.UUID | None = None

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class ResearchTaskUpdateCreate(BaseModel):
    note: str = Field(min_length=1, max_length=4000)
    evidence_information_item_id: uuid.UUID | None = None
    evidence_analysis_version_id: uuid.UUID | None = None
    evidence_daily_review_version_id: uuid.UUID | None = None

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str) -> str:
        return value.strip()


class ResearchStockOut(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    exchange: str


class ResearchTaskUpdateOut(OrmModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    previous_status: str | None
    new_status: str
    note: str | None
    evidence_information_item_id: uuid.UUID | None
    evidence_analysis_version_id: uuid.UUID | None
    evidence_daily_review_version_id: uuid.UUID | None
    created_by: str
    created_at: datetime


class ResearchTaskOut(OrmModel):
    id: uuid.UUID
    user_id: uuid.UUID
    stock_id: uuid.UUID | None
    stock: StockRead | None = None
    task_type: str
    title: str
    description: str
    status: str
    priority: str
    source_type: str
    source_information_item_id: uuid.UUID | None
    source_analysis_version_id: uuid.UUID | None
    source_daily_review_id: uuid.UUID | None
    source_daily_review_version_id: uuid.UUID | None
    due_date: date | None
    current_evidence_summary: str | None
    resolution_note: str | None
    created_by: str
    deduplication_key: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    updates: list[ResearchTaskUpdateOut] = Field(default_factory=list)

import uuid
from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmModel

EventType = Literal[
    "user_daily_review.generated",
    "user_daily_review.partial",
    "user_daily_review.failed",
    "user_daily_review.became_stale",
    "information.high_priority_detected",
    "information.verification_required",
    "ai_task.failed",
]
Severity = Literal["info", "notice", "important"]
NotificationStatus = Literal["unread", "read", "archived", "expired"]
NotificationAction = Literal["mark_read", "mark_unread", "archive", "unarchive"]
NotificationFrequency = Literal["immediate", "daily_digest", "disabled"]


class BusinessEventOut(OrmModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: EventType
    event_version: str
    occurred_at: datetime
    subject_type: str
    subject_id: uuid.UUID
    severity: Severity
    payload: dict
    source: str
    correlation_id: str | None
    idempotency_key: str
    created_at: datetime


class NotificationOut(OrmModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_id: uuid.UUID
    event_type: EventType
    title: str
    summary: str
    severity: Severity
    target_type: str
    target_id: uuid.UUID
    deep_link: str
    status: NotificationStatus
    created_at: datetime
    updated_at: datetime
    read_at: datetime | None
    archived_at: datetime | None
    expires_at: datetime | None


class NotificationPatch(BaseModel):
    action: NotificationAction


class NotificationMarkAllReadRequest(BaseModel):
    event_type: EventType | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class NotificationUnreadCountOut(BaseModel):
    unread_count: int


class NotificationPreferenceOut(OrmModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: EventType
    channel: Literal["in_app"]
    enabled: bool
    frequency: NotificationFrequency
    minimum_severity: Severity
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    timezone: str
    created_at: datetime
    updated_at: datetime


class NotificationPreferenceUpdateItem(BaseModel):
    event_type: EventType
    enabled: bool = True
    frequency: NotificationFrequency = "immediate"
    minimum_severity: Severity = "info"
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        if value != "Asia/Shanghai":
            raise ValueError("timezone must be Asia/Shanghai in MVP")
        return value


class NotificationPreferenceUpdateRequest(BaseModel):
    items: list[NotificationPreferenceUpdateItem]

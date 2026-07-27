import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import OrmModel

ReviewStatus = Literal["complete", "partial", "empty", "failed", "stale"]
GenerationMode = Literal["rules_only", "rules_and_ai", "rules_with_ai_fallback"]


class DailyReviewGenerateRequest(BaseModel):
    review_date: date | None = None
    force: bool = False
    use_ai: bool = True


class DailyReviewPatch(BaseModel):
    archived: bool


class DailyReviewAIResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    executive_summary: str
    key_developments: list[str]
    stock_summaries: list[dict[str, Any]]
    verification_focus: list[str]
    tomorrow_observation_focus: list[str]
    uncertainty_summary: str
    limitations: list[str]
    source_item_ids: list[str]


class DailyReviewVersionOut(OrmModel):
    id: uuid.UUID
    daily_review_id: uuid.UUID
    version_number: int
    status: ReviewStatus
    generation_mode: GenerationMode
    ai_task_id: uuid.UUID | None
    rule_snapshot: dict[str, Any]
    ai_structured_result: dict[str, Any] | None
    ai_narrative: str | None
    input_fingerprint: str
    prompt_version: str | None
    schema_version: str
    provider_config_id: uuid.UUID | None
    model_name: str | None
    generated_at: datetime
    created_at: datetime


class DailyReviewSummaryOut(OrmModel):
    id: uuid.UUID
    user_id: uuid.UUID
    review_date: date
    status: ReviewStatus
    current_version_id: uuid.UUID | None
    current_version_number: int | None
    generation_mode: GenerationMode | None
    input_fingerprint: str | None
    generated_at: datetime | None
    stale_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    overview: dict[str, Any]
    ai_available: bool
    generation_in_progress: bool
    generation_task_id: uuid.UUID | None
    generation_task_status: str | None


class DailyReviewDetailOut(DailyReviewSummaryOut):
    current_version: DailyReviewVersionOut | None
    versions: list[DailyReviewVersionOut]

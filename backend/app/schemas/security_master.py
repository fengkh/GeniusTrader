from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class SecurityMasterProviderOut(BaseModel):
    source_code: str
    display_name: str
    implemented: bool
    enabled_by_config: bool
    official: bool
    capabilities: list[str]
    limitations: list[str]


class SecurityMasterSyncRequest(BaseModel):
    source_code: str = Field(min_length=1, max_length=80)
    exchanges: list[str] = Field(default_factory=list)
    force: bool = False


class SecurityMasterSyncRunOut(OrmModel):
    id: UUID
    triggered_by_user_id: UUID
    source_code: str
    status: str
    exchanges: list[str]
    request_count: int
    received_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    deactivated_count: int
    failure_count: int
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None
    error_summary: str | None
    metrics: dict
    created_at: datetime
    updated_at: datetime


class SecurityMasterStatusOut(BaseModel):
    total_count: int
    by_exchange: dict[str, int]
    by_board: dict[str, int]
    active_count: int
    development_seed_count: int
    seed_covered_count: int
    last_synced_at: datetime | None
    sources: list[str]
    data_gaps: list[str]
    latest_sync_status: str | None
    latest_sync_run: SecurityMasterSyncRunOut | None

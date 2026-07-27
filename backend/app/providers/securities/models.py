from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.providers.statuses import ProviderStatus


@dataclass(frozen=True, slots=True)
class SecurityMasterCapability:
    name: str
    description: str
    supports_pagination: bool
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SecurityMasterQuery:
    exchanges: list[str] = field(default_factory=list)
    security_types: list[str] = field(default_factory=list)
    listing_statuses: list[str] = field(default_factory=list)
    cursor: str | None = None
    max_records: int = 5000


@dataclass(frozen=True, slots=True)
class SecurityMasterRecord:
    source_code: str
    provider_security_id: str
    symbol: str
    code: str
    exchange: str
    market: str
    board: str
    security_type: str
    short_name: str
    full_name: str | None
    english_name: str | None
    listing_status: str
    listed_at: date | None
    delisted_at: date | None
    previous_symbols: list[str]
    aliases: list[str]
    raw_metadata_hash: str
    fetched_at: datetime
    data_completeness: str
    missing_fields: list[str]
    source_updated_at: datetime | None = None
    raw_status: str | None = None
    pinyin: str | None = None
    pinyin_initials: str | None = None


@dataclass(frozen=True, slots=True)
class SecurityMasterResult:
    status: ProviderStatus
    records: list[SecurityMasterRecord] = field(default_factory=list)
    next_cursor: str | None = None
    errors: list[dict[str, str]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0

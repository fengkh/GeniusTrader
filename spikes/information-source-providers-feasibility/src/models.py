from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .statuses import ProviderStatus


@dataclass(slots=True)
class ProviderProbeResult:
    provider: str
    capability: str
    status: ProviderStatus
    tested_at: datetime
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    latency_ms: int | None = None
    sample_count: int = 0
    error_code: str | None = None
    error_summary: str | None = None
    evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["tested_at"] = self.tested_at.isoformat()
        return value


@dataclass(slots=True)
class ProviderCursor:
    provider: str
    capability: str
    cursor_type: str
    cursor_value: str
    last_success_at: datetime | None
    last_item_published_at: datetime | None
    last_provider_item_id: str | None
    overlap_window_seconds: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["last_success_at"] = self.last_success_at.isoformat() if self.last_success_at else None
        value["last_item_published_at"] = self.last_item_published_at.isoformat() if self.last_item_published_at else None
        return value


@dataclass(slots=True)
class SpikeRunResult:
    provider_results: list[ProviderProbeResult]
    announcements: list[Any]
    news: list[Any]
    pdf_results: list[dict[str, Any]]
    raw_metrics: dict[str, Any]

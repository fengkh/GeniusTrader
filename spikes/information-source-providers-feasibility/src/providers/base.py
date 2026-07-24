from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from ..http_client import SpikeHttpClient
from ..models import ProviderProbeResult
from ..statuses import ProviderStatus


@dataclass(slots=True)
class ProviderRunContext:
    client: SpikeHttpClient
    date_from: date
    date_to: date
    symbols: list[str]
    max_records: int
    skip_pdf: bool = False


@dataclass(slots=True)
class ProviderOutput:
    results: list[ProviderProbeResult] = field(default_factory=list)
    announcements: list[Any] = field(default_factory=list)
    news: list[Any] = field(default_factory=list)
    pdf_urls: list[str] = field(default_factory=list)


class ProviderProbe(ABC):
    name: str

    @abstractmethod
    def probe(self, context: ProviderRunContext) -> ProviderOutput:
        raise NotImplementedError


def result_from_http(
    *,
    provider: str,
    capability: str,
    status: ProviderStatus,
    tested_at: datetime | None = None,
    request_count: int = 1,
    success_count: int = 0,
    failure_count: int = 0,
    latency_ms: int | None = None,
    sample_count: int = 0,
    error_code: str | None = None,
    error_summary: str | None = None,
    evidence: list[str] | None = None,
    limitations: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> ProviderProbeResult:
    return ProviderProbeResult(
        provider=provider,
        capability=capability,
        status=status,
        tested_at=tested_at or datetime.now(UTC),
        request_count=request_count,
        success_count=success_count,
        failure_count=failure_count,
        latency_ms=latency_ms,
        sample_count=sample_count,
        error_code=error_code,
        error_summary=error_summary,
        evidence=evidence or [],
        limitations=limitations or [],
        metrics=metrics or {},
    )


def status_from_http_code(status_code: int | None, error: str | None) -> ProviderStatus:
    if error == "TIMEOUT":
        return ProviderStatus.TIMEOUT
    if error:
        return ProviderStatus.NETWORK_ERROR
    if status_code == 429:
        return ProviderStatus.RATE_LIMITED
    if status_code in {401, 403}:
        return ProviderStatus.ACCESS_DENIED
    if status_code and 200 <= status_code < 300:
        return ProviderStatus.PASS
    return ProviderStatus.NETWORK_ERROR

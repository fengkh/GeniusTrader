from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

from app.providers.market_data.models import (
    DailyMarketSnapshotRecord,
    MarketDataProviderResult,
    MarketDataQuery,
    TradeCalendarDay,
)


class MarketDataProvider(ABC):
    source_code: str
    provider_adapter: str

    @abstractmethod
    def capabilities(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> MarketDataProviderResult:
        raise NotImplementedError

    @abstractmethod
    async def trade_calendar(self, query: MarketDataQuery) -> list[TradeCalendarDay]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_daily_snapshots(self, query: MarketDataQuery) -> MarketDataProviderResult:
        raise NotImplementedError

    def normalize_records(
        self,
        records: list[DailyMarketSnapshotRecord],
    ) -> list[DailyMarketSnapshotRecord]:
        return records


def provider_error(code: str, summary: str) -> dict[str, str]:
    return {"code": code[:80], "summary": summary[:300]}


def redacted_provider_metadata(value: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in value.items():
        lowered = key.lower()
        if lowered in {"token", "api_key", "password", "authorization", "cookie", "set-cookie"}:
            safe[key] = "[redacted]"
        elif isinstance(item, str) and len(item) > 500:
            safe[key] = f"{item[:500]}..."
        else:
            safe[key] = item
    return safe


def with_redacted_metadata(result: MarketDataProviderResult) -> MarketDataProviderResult:
    return replace(result, provider_metadata=redacted_provider_metadata(result.provider_metadata))

from datetime import date, timedelta
from decimal import Decimal

from app.core.time import utc_now
from app.providers.market_data.base import MarketDataProvider
from app.providers.market_data.models import (
    DailyMarketSnapshotRecord,
    MarketDataProviderResult,
    MarketDataQuery,
    TradeCalendarDay,
)
from app.providers.market_data.normalization import normalize_symbol, stable_hash
from app.providers.statuses import ProviderStatus


class MockMarketDataProvider(MarketDataProvider):
    source_code = "MOCK_MARKET_DATA"
    provider_adapter = "mock"

    def capabilities(self) -> list[str]:
        return ["daily_snapshot", "trade_calendar"]

    async def health_check(self) -> MarketDataProviderResult:
        return MarketDataProviderResult(status=ProviderStatus.PASS, request_count=0, success_count=1)

    async def trade_calendar(self, query: MarketDataQuery) -> list[TradeCalendarDay]:
        end = query.date_to or query.trade_date or date(2026, 7, 24)
        start = query.date_from or end - timedelta(days=10)
        rows: list[TradeCalendarDay] = []
        current = start
        previous_open: date | None = None
        while current <= end:
            is_open = current.weekday() < 5
            rows.append(
                TradeCalendarDay(
                    trade_date=current,
                    is_open=is_open,
                    previous_open_date=previous_open,
                    source_code=self.source_code,
                )
            )
            if is_open:
                previous_open = current
            current += timedelta(days=1)
        return rows

    async def fetch_daily_snapshots(self, query: MarketDataQuery) -> MarketDataProviderResult:
        trade_date = query.trade_date or query.date_to or date(2026, 7, 24)
        now = utc_now()
        records = [
            self._record(symbol=symbol, trade_date=trade_date, index=index, fetched_at=now)
            for index, symbol in enumerate(query.symbols[: query.max_records])
        ]
        return MarketDataProviderResult(
            status=ProviderStatus.PASS,
            records=records,
            metrics={"deterministic": True, "network": False},
            provider_metadata={"provider": self.source_code},
            request_count=1,
            success_count=1,
        )

    def _record(
        self,
        *,
        symbol: str,
        trade_date: date,
        index: int,
        fetched_at,
    ) -> DailyMarketSnapshotRecord:
        normalized = normalize_symbol(symbol)
        base = Decimal("10.00") + Decimal(index)
        change = Decimal("0.12") if index % 2 == 0 else Decimal("-0.08")
        close = base + change
        payload = {"symbol": normalized, "trade_date": trade_date.isoformat(), "close": str(close)}
        return DailyMarketSnapshotRecord(
            source_code=self.source_code,
            symbol=normalized,
            trade_date=trade_date,
            open=base,
            high=close + Decimal("0.30"),
            low=base - Decimal("0.20"),
            close=close,
            pre_close=base,
            change=change,
            pct_change=(change / base * Decimal("100")).quantize(Decimal("0.000001")),
            volume=Decimal(1000000 + index * 10000),
            amount=Decimal(10000000 + index * 100000),
            turnover_rate=Decimal("1.25") + Decimal(index) / Decimal("100"),
            volume_ratio=Decimal("1.10"),
            total_market_value=Decimal(1000000000 + index * 1000000),
            circulating_market_value=Decimal(800000000 + index * 1000000),
            pe_ttm=Decimal("20.5"),
            pb=Decimal("3.1"),
            is_trading=True,
            data_completeness="complete",
            source_updated_at=fetched_at,
            fetched_at=fetched_at,
            raw_metadata_hash=stable_hash(payload),
            limitations=["Mock Provider 仅用于自动测试；前端和生产环境不得显示为真实行情。"],
            source_record_ref=f"{normalized}:{trade_date.isoformat()}",
        )

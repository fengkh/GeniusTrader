from dataclasses import replace
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.providers.market_data.base import (
    MarketDataProvider,
    provider_error,
    with_redacted_metadata,
)
from app.providers.market_data.models import (
    DailyMarketSnapshotRecord,
    MarketDataProviderResult,
    MarketDataQuery,
    TradeCalendarDay,
)
from app.providers.market_data.normalization import (
    completeness_for_required,
    decimal_or_none,
    decimal_times,
    normalize_tushare_symbol,
    parse_trade_date,
    stable_hash,
)
from app.providers.statuses import ProviderStatus


class TushareMarketDataProvider(MarketDataProvider):
    source_code = "TUSHARE_PRO"
    provider_adapter = "tushare"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[str]:
        return ["daily_snapshot", "trade_calendar"]

    async def health_check(self) -> MarketDataProviderResult:
        self._ensure_configured_and_allowed()
        return MarketDataProviderResult(
            status=ProviderStatus.PASS,
            provider_metadata={"source_code": self.source_code, "token": "[redacted]"},
            request_count=0,
            success_count=1,
        )

    async def trade_calendar(self, query: MarketDataQuery) -> list[TradeCalendarDay]:
        self._ensure_configured_and_allowed()
        raw = await self._post(
            api_name="trade_cal",
            params={
                "exchange": "SSE",
                "start_date": query.date_from.strftime("%Y%m%d") if query.date_from else None,
                "end_date": query.date_to.strftime("%Y%m%d") if query.date_to else None,
            },
            fields="cal_date,is_open,pretrade_date",
        )
        fields, items = self._extract_table(raw)
        rows: list[TradeCalendarDay] = []
        for item in items:
            row = dict(zip(fields, item, strict=False))
            trade_date = parse_trade_date(row.get("cal_date"))
            if trade_date is None:
                continue
            rows.append(
                TradeCalendarDay(
                    trade_date=trade_date,
                    is_open=str(row.get("is_open")) == "1",
                    previous_open_date=parse_trade_date(row.get("pretrade_date")),
                    source_code=self.source_code,
                )
            )
        return rows

    async def fetch_daily_snapshots(self, query: MarketDataQuery) -> MarketDataProviderResult:
        self._ensure_configured_and_allowed()
        if not query.trade_date:
            return MarketDataProviderResult(
                status=ProviderStatus.DATA_INSUFFICIENT,
                errors=[provider_error("TRADE_DATE_REQUIRED", "trade_date is required for Tushare daily snapshots")],
            )

        params = {"trade_date": query.trade_date.strftime("%Y%m%d")}
        daily_raw = await self._post(
            api_name="daily",
            params=params,
            fields="ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
        )
        basic_raw = await self._post(
            api_name="daily_basic",
            params=params,
            fields="ts_code,trade_date,turnover_rate,volume_ratio,total_mv,circ_mv,pe_ttm,pb",
        )
        daily_fields, daily_items = self._extract_table(daily_raw)
        basic_fields, basic_items = self._extract_table(basic_raw)
        basic_by_symbol = {
            normalize_tushare_symbol(str(dict(zip(basic_fields, item, strict=False)).get("ts_code", ""))): dict(
                zip(basic_fields, item, strict=False)
            )
            for item in basic_items
        }

        symbols = {normalize_tushare_symbol(symbol) for symbol in query.symbols}
        records: list[DailyMarketSnapshotRecord] = []
        fetched_at = utc_now()
        for item in daily_items:
            daily = dict(zip(daily_fields, item, strict=False))
            symbol = normalize_tushare_symbol(str(daily.get("ts_code", "")))
            if symbols and symbol not in symbols:
                continue
            trade_date = parse_trade_date(daily.get("trade_date"))
            if not trade_date:
                continue
            basic = basic_by_symbol.get(symbol, {})
            merged = {**daily, **basic}
            records.append(self._normalize_record(symbol=symbol, raw=merged, fetched_at=fetched_at))

        status = ProviderStatus.PASS if records else ProviderStatus.DATA_INSUFFICIENT
        result = MarketDataProviderResult(
            status=status,
            records=records,
            errors=[] if records else [provider_error("NO_RECORDS", "Provider returned no usable rows")],
            metrics={"raw_daily_count": len(daily_items), "raw_daily_basic_count": len(basic_items)},
            provider_metadata={"source_code": self.source_code, "token": "[redacted]"},
            request_count=2,
            success_count=2,
            failure_count=0,
        )
        return with_redacted_metadata(result)

    def _ensure_configured_and_allowed(self) -> None:
        token = self.settings.market_data_tushare_token.strip()
        if not token:
            raise AppError(
                ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED,
                "Tushare Token 未配置",
                status_code=503,
            )
        if self.settings.is_production and self.settings.market_data_tushare_authorization_status != "commercially_authorized":
            raise AppError(
                ErrorCode.MARKET_DATA_PERMISSION_DENIED,
                "Tushare 尚未确认生产授权，生产环境拒绝同步",
                status_code=403,
            )
        if not self.settings.market_data_real_network_enabled:
            raise AppError(
                ErrorCode.MARKET_DATA_REAL_NETWORK_DISABLED,
                "行情真实网络同步未启用",
                status_code=403,
            )

    async def _post(self, *, api_name: str, params: dict[str, Any], fields: str) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - runtime dependency guard
            raise AppError(
                ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED,
                "httpx 未安装，无法执行 Tushare 网络请求",
                status_code=503,
            ) from exc

        payload = {
            "api_name": api_name,
            "token": self.settings.market_data_tushare_token.strip(),
            "params": {key: value for key, value in params.items() if value is not None},
            "fields": fields,
        }
        async with httpx.AsyncClient(timeout=self.settings.market_data_request_timeout_seconds) as client:
            response = await client.post(self.settings.market_data_tushare_base_url, json=payload)
        if response.status_code in {401, 403}:
            raise AppError(
                ErrorCode.MARKET_DATA_PERMISSION_DENIED,
                "Tushare 访问被拒绝",
                status_code=403,
            )
        if response.status_code >= 500:
            raise AppError(ErrorCode.MARKET_DATA_SYNC_FAILED, "Tushare 服务暂不可用", status_code=502)
        data = response.json()
        if data.get("code") not in (0, "0", None):
            message = str(data.get("msg") or "Tushare 返回业务错误")
            if "permission" in message.lower() or "权限" in message:
                raise AppError(ErrorCode.MARKET_DATA_PERMISSION_DENIED, "Tushare 权限不足", status_code=403)
            raise AppError(ErrorCode.MARKET_DATA_SOURCE_CHANGED, "Tushare 返回结构或业务状态异常", status_code=502)
        return data

    @staticmethod
    def _extract_table(data: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
        table = data.get("data") if isinstance(data, dict) else None
        fields = table.get("fields") if isinstance(table, dict) else None
        items = table.get("items") if isinstance(table, dict) else None
        if not isinstance(fields, list) or not isinstance(items, list):
            raise AppError(ErrorCode.MARKET_DATA_SOURCE_CHANGED, "Tushare 响应结构变化", status_code=502)
        return [str(field) for field in fields], [item for item in items if isinstance(item, list)]

    def _normalize_record(
        self,
        *,
        symbol: str,
        raw: dict[str, Any],
        fetched_at: datetime,
    ) -> DailyMarketSnapshotRecord:
        trade_date = parse_trade_date(raw.get("trade_date"))
        values = {
            "trade_date": trade_date,
            "open": decimal_or_none(raw.get("open")),
            "high": decimal_or_none(raw.get("high")),
            "low": decimal_or_none(raw.get("low")),
            "close": decimal_or_none(raw.get("close")),
        }
        completeness = completeness_for_required(values, ["trade_date", "open", "high", "low", "close"])
        return DailyMarketSnapshotRecord(
            source_code=self.source_code,
            symbol=symbol,
            trade_date=trade_date or datetime.fromtimestamp(0).date(),
            open=values["open"],
            high=values["high"],
            low=values["low"],
            close=values["close"],
            pre_close=decimal_or_none(raw.get("pre_close")),
            change=decimal_or_none(raw.get("change")),
            pct_change=decimal_or_none(raw.get("pct_chg")),
            volume=decimal_times(raw.get("vol"), "100"),
            amount=decimal_times(raw.get("amount"), "1000"),
            turnover_rate=decimal_or_none(raw.get("turnover_rate")),
            volume_ratio=decimal_or_none(raw.get("volume_ratio")),
            total_market_value=decimal_times(raw.get("total_mv"), "10000"),
            circulating_market_value=decimal_times(raw.get("circ_mv"), "10000"),
            pe_ttm=decimal_or_none(raw.get("pe_ttm")),
            pb=decimal_or_none(raw.get("pb")),
            is_trading=values["close"] is not None,
            data_completeness=completeness,
            source_updated_at=fetched_at,
            fetched_at=fetched_at,
            raw_metadata_hash=stable_hash({"symbol": symbol, **raw}),
            limitations=[
                "Tushare 字段单位需在 Checkpoint B 真实凭证 Smoke 后复核；当前适配器按已知口径做显式转换。"
            ],
            source_record_ref=f"{symbol}:{raw.get('trade_date')}",
        )

    def normalize_records(
        self,
        records: list[DailyMarketSnapshotRecord],
    ) -> list[DailyMarketSnapshotRecord]:
        return [replace(record, source_code=self.source_code) for record in records]

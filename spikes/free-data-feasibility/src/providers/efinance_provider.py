from __future__ import annotations

import pandas as pd

from ..capability import synthetic_record
from ..models import INTERNAL_DAILY_FIELDS, INTERNAL_MINUTE_FIELDS, INTERNAL_SNAPSHOT_FIELDS, ProviderResult
from ..normalization import NORMALIZED_UNITS, normalize_by_mapping, normalize_date, normalize_symbol, provider_index_symbol, provider_symbol, with_missing_columns
from .base import BaseProvider


EFINANCE_FUNCTIONS = [
    "stock.get_quote_history",
    "stock.get_realtime_quotes",
    "stock.get_quote_minute",
]


class EFinanceProvider(BaseProvider):
    provider_name = "efinance"

    def get_stock_snapshot(self, symbols: list[str]) -> ProviderResult:
        normalized_symbols = {normalize_symbol(symbol) for symbol in symbols}

        def normalize(frame: pd.DataFrame) -> pd.DataFrame:
            result = self._normalize_snapshot(frame)
            if normalized_symbols:
                result = result[result["symbol"].isin(normalized_symbols)]
            return result.reset_index(drop=True)

        return self._call(
            capability="stock_snapshot",
            api_name="stock.get_realtime_quotes",
            parameters={"fs": "沪深A股"},
            fields_expected=INTERNAL_SNAPSHOT_FIELDS,
            impacts=["today page", "watchlist latest quote", "stock detail header"],
            fallback="AKShare snapshot or stale cached snapshot",
            normalizer=normalize,
            original_units={"成交量": "hand", "成交额": "CNY_yuan", "换手率": "percent_value"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_daily_history(self, symbol: str, start_date: str, end_date: str, adjust: str) -> ProviderResult:
        fqt = 1 if adjust == "qfq" else 0 if adjust in {"", "none", "unadjusted"} else 2 if adjust == "hfq" else 0
        return self._call(
            capability="daily_history_qfq" if adjust == "qfq" else "daily_history",
            api_name="stock.get_quote_history",
            parameters={
                "stock_codes": provider_symbol(symbol, self.provider_name),
                "beg": _compact_date(start_date),
                "end": _compact_date(end_date),
                "klt": 101,
                "fqt": fqt,
            },
            fields_expected=INTERNAL_DAILY_FIELDS,
            impacts=["daily K", "program metrics", "cross-provider comparison"],
            fallback="AKShare daily, then BaoStock historical floor",
            normalizer=lambda frame: self._normalize_daily(frame, symbol, "qfq" if fqt == 1 else "none"),
            original_units={"成交量": "hand", "成交额": "CNY_yuan", "换手率": "percent_value", "振幅": "percent_value"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_minute_history(self, symbol: str, start_datetime: str, end_datetime: str, period: str) -> ProviderResult:
        klt = int(period) if str(period).isdigit() else 1
        return self._call(
            capability="minute_history",
            api_name="stock.get_quote_minute",
            parameters={"stock_code": provider_symbol(symbol, self.provider_name), "klt": klt, "fqt": 0},
            fields_expected=INTERNAL_MINUTE_FIELDS,
            impacts=["intraday chart", "max intraday drawdown"],
            fallback="AKShare minute or show unavailable intraday state",
            normalizer=lambda frame: self._normalize_minute(frame, symbol),
            original_units={"成交量": "hand", "成交额": "CNY_yuan"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_index_history(self, index_code: str, start_date: str, end_date: str) -> ProviderResult:
        return self._call(
            capability="index_history",
            api_name="stock.get_quote_history",
            parameters={
                "stock_codes": provider_index_symbol(index_code, self.provider_name),
                "beg": _compact_date(start_date),
                "end": _compact_date(end_date),
                "klt": 101,
                "fqt": 0,
            },
            fields_expected=INTERNAL_DAILY_FIELDS,
            impacts=["relative index strength"],
            fallback="AKShare or BaoStock index history",
            normalizer=lambda frame: self._normalize_daily(frame, index_code, "none"),
            original_units={"成交量": "hand", "成交额": "CNY_yuan"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_industry_boards(self) -> ProviderResult:
        return self._not_supported_board("industry_boards")

    def get_concept_boards(self) -> ProviderResult:
        return self._not_supported_board("concept_boards")

    def get_board_members(self, board_id: str) -> ProviderResult:
        return self._not_supported_board("board_members")

    def get_stock_board_memberships(self, symbol: str) -> ProviderResult:
        return self._not_supported_board("stock_board_memberships")

    def get_stock_status(self, symbol: str) -> ProviderResult:
        snapshot = self.get_stock_snapshot([symbol])
        if snapshot.data.empty:
            return snapshot
        data = snapshot.data[["symbol", "trade_status", "provider"]].copy()
        return ProviderResult(data, snapshot.record)

    def get_announcements(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="announcements",
                api_name="not_supported",
                status="NOT_SUPPORTED",
                parameters_summary={"symbol": normalize_symbol(symbol), "start_date": start_date, "end_date": end_date},
                fields_expected=["symbol", "title", "publish_time", "source_url"],
                impacts_features=["information center", "review materials"],
                recommended_fallback="Use exchange official disclosure sources, user-pasted links, or authorized information provider.",
            ),
        )

    def _normalize_snapshot(self, frame: pd.DataFrame) -> pd.DataFrame:
        code_column = _first_column(frame, ["股票代码", "代码"])
        _require_columns(frame, [code_column, "最新价", "涨跌幅"])
        result = normalize_by_mapping(
            frame,
            mapping={
                "symbol": code_column,
                "close": "最新价",
                "change": _first_column(frame, ["涨跌额", "涨跌额(元)"]),
                "pct_change": "涨跌幅",
                "volume": "成交量",
                "amount": "成交额",
                "high": "最高",
                "low": "最低",
                "open": "今开",
                "pre_close": "昨收",
                "volume_ratio": "量比",
                "turnover_rate": "换手率",
                "total_market_value": "总市值",
                "circulating_market_value": "流通市值",
            },
            provider=self.provider_name,
            volume_unit="hand",
            amount_unit="yuan",
            defaults={"trade_status": "trading_or_unknown"},
        )
        result["trade_date"] = pd.Timestamp.now(tz="Asia/Shanghai").date().isoformat()
        result["quote_time"] = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
        result["fetched_at"] = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
        result.loc[result["close"].isna(), "trade_status"] = "suspended_or_unavailable"
        return with_missing_columns(result, INTERNAL_SNAPSHOT_FIELDS)

    def _normalize_daily(self, frame: pd.DataFrame, symbol: str, adjustment: str) -> pd.DataFrame:
        _require_columns(frame, ["日期", "开盘", "收盘", "最高", "最低"])
        result = normalize_by_mapping(
            frame,
            mapping={
                "trade_date": "日期",
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
                "amplitude": "振幅",
                "pct_change": "涨跌幅",
                "change": "涨跌额",
                "turnover_rate": "换手率",
            },
            provider=self.provider_name,
            volume_unit="hand",
            amount_unit="yuan",
            defaults={"symbol": normalize_symbol(symbol), "adjustment": adjustment},
        )
        result["pre_close"] = result["close"].shift(1)
        return with_missing_columns(result, INTERNAL_DAILY_FIELDS)

    def _normalize_minute(self, frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
        datetime_column = _first_column(frame, ["日期", "时间", "datetime"])
        _require_columns(frame, [datetime_column, "开盘", "收盘", "最高", "最低"])
        result = normalize_by_mapping(
            frame,
            mapping={
                "datetime": datetime_column,
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
            },
            provider=self.provider_name,
            volume_unit="hand",
            amount_unit="yuan",
            defaults={"symbol": normalize_symbol(symbol)},
        )
        return with_missing_columns(result, INTERNAL_MINUTE_FIELDS)

    def _not_supported_board(self, capability: str) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability=capability,
                api_name="public_board_api_not_confirmed",
                status="NOT_SUPPORTED",
                fields_expected=["board_id", "board_name", "board_type", "symbol"],
                impacts_features=["board filter", "stock classification"],
                recommended_fallback="Use AKShare board APIs or paid classification provider; do not treat board names as user tags.",
                error_message="No stable public efinance board API is confirmed in this spike adapter.",
            ),
        )


def _require_columns(frame: pd.DataFrame, columns: list[str | None]) -> None:
    missing = [column for column in columns if column and column not in frame.columns]
    if missing:
        raise ValueError(f"required raw columns missing: {', '.join(missing)}; returned={list(frame.columns)}")


def _first_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    return next((column for column in candidates if column in frame.columns), None)


def _compact_date(value: str) -> str:
    normalized = normalize_date(value)
    return "" if normalized is None else normalized.replace("-", "")

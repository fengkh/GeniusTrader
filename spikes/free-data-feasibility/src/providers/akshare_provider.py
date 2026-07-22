from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ..capability import capability_record_from_frame, now_shanghai, synthetic_record
from ..models import INTERNAL_BOARD_FIELDS, INTERNAL_DAILY_FIELDS, INTERNAL_MINUTE_FIELDS, INTERNAL_SNAPSHOT_FIELDS, INTERNAL_STOCK_BASIC_FIELDS, ProviderResult
from ..normalization import (
    NORMALIZED_UNITS,
    amount_to_yuan,
    normalize_by_mapping,
    normalize_date,
    normalize_datetime,
    normalize_symbol,
    provider_index_symbol,
    provider_symbol,
    to_float,
    volume_to_shares,
    with_missing_columns,
)
from .base import BaseProvider


AKSHARE_FUNCTIONS = [
    "stock_zh_a_spot_em",
    "stock_zh_a_hist",
    "stock_zh_a_hist_min_em",
    "stock_zh_a_hist_pre_min_em",
    "stock_zh_index_spot_em",
    "index_zh_a_hist",
    "stock_board_industry_name_em",
    "stock_board_industry_cons_em",
    "stock_board_industry_hist_em",
    "stock_board_concept_name_em",
    "stock_board_concept_cons_em",
    "stock_board_concept_hist_em",
    "stock_notice_report",
    "stock_zh_a_disclosure_report_cninfo",
]


class AKShareProvider(BaseProvider):
    provider_name = "akshare"

    def get_stock_universe(self) -> ProviderResult:
        return self._call(
            capability="stock_universe",
            api_name="stock_zh_a_spot_em",
            parameters={},
            fields_expected=INTERNAL_STOCK_BASIC_FIELDS,
            impacts=["stock_basic", "BSE sample discovery", "watchlist add"],
            fallback="efinance snapshot or paid stock-basic source",
            normalizer=self._normalize_universe,
            original_units={},
            normalized_units={},
        )

    def get_stock_snapshot(self, symbols: list[str]) -> ProviderResult:
        normalized_symbols = {normalize_symbol(symbol) for symbol in symbols}

        def normalize(frame: pd.DataFrame) -> pd.DataFrame:
            result = self._normalize_snapshot(frame)
            if normalized_symbols:
                result = result[result["symbol"].isin(normalized_symbols)]
            return result.reset_index(drop=True)

        return self._call(
            capability="stock_snapshot",
            api_name="stock_zh_a_spot_em",
            parameters={},
            fields_expected=INTERNAL_SNAPSHOT_FIELDS,
            impacts=["today page", "watchlist latest quote", "stock detail header"],
            fallback="efinance realtime quotes or stale cached snapshot",
            normalizer=normalize,
            original_units={"成交量": "hand", "成交额": "CNY_yuan", "换手率": "percent_value", "涨跌幅": "percent_value"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_daily_history(self, symbol: str, start_date: str, end_date: str, adjust: str) -> ProviderResult:
        ak_adjust = "" if adjust in {"", "none", "unadjusted"} else "qfq" if adjust == "qfq" else adjust
        return self._call(
            capability="daily_history_qfq" if ak_adjust == "qfq" else "daily_history",
            api_name="stock_zh_a_hist",
            parameters={
                "symbol": provider_symbol(symbol, self.provider_name),
                "period": "daily",
                "start_date": _compact_date(start_date),
                "end_date": _compact_date(end_date),
                "adjust": ak_adjust,
            },
            fields_expected=INTERNAL_DAILY_FIELDS,
            impacts=["daily K", "program metrics", "cross-provider comparison"],
            fallback="efinance daily, then BaoStock historical floor",
            normalizer=lambda frame: self._normalize_daily(frame, symbol, ak_adjust or "none"),
            original_units={"成交量": "hand", "成交额": "CNY_yuan", "换手率": "percent_value", "振幅": "percent_value"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_minute_history(self, symbol: str, start_datetime: str, end_datetime: str, period: str) -> ProviderResult:
        return self._call(
            capability="minute_history",
            api_name="stock_zh_a_hist_min_em",
            parameters={
                "symbol": provider_symbol(symbol, self.provider_name),
                "start_date": _compact_datetime(start_datetime),
                "end_date": _compact_datetime(end_datetime),
                "period": period,
                "adjust": "",
            },
            fields_expected=INTERNAL_MINUTE_FIELDS,
            impacts=["intraday chart", "max intraday drawdown"],
            fallback="efinance minute or show unavailable intraday state",
            normalizer=lambda frame: self._normalize_minute(frame, symbol),
            original_units={"成交量": "hand", "成交额": "CNY_yuan"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_index_history(self, index_code: str, start_date: str, end_date: str) -> ProviderResult:
        return self._call(
            capability="index_history",
            api_name="index_zh_a_hist",
            parameters={
                "symbol": provider_index_symbol(index_code, self.provider_name),
                "period": "daily",
                "start_date": _compact_date(start_date),
                "end_date": _compact_date(end_date),
            },
            fields_expected=INTERNAL_DAILY_FIELDS,
            impacts=["relative index strength"],
            fallback="BaoStock index history or degrade relative index metric",
            normalizer=lambda frame: self._normalize_index(frame, index_code),
            original_units={"成交量": "hand", "成交额": "CNY_yuan"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_industry_boards(self) -> ProviderResult:
        return self._call(
            capability="industry_boards",
            api_name="stock_board_industry_name_em",
            parameters={},
            fields_expected=INTERNAL_BOARD_FIELDS,
            impacts=["board filter", "stock classification", "relative industry strength"],
            fallback="manual standard classification or paid classification source",
            normalizer=lambda frame: self._normalize_board_names(frame, "standard_industry"),
        )

    def get_concept_boards(self) -> ProviderResult:
        return self._call(
            capability="concept_boards",
            api_name="stock_board_concept_name_em",
            parameters={},
            fields_expected=INTERNAL_BOARD_FIELDS,
            impacts=["board filter", "stock classification"],
            fallback="manual concept classification or paid classification source",
            normalizer=lambda frame: self._normalize_board_names(frame, "concept_board"),
        )

    def get_board_members(self, board_id: str) -> ProviderResult:
        api_name = "stock_board_industry_cons_em" if board_id.startswith("standard_industry:") else "stock_board_concept_cons_em"
        board_name = board_id.split(":", 1)[1] if ":" in board_id else board_id
        return self._call(
            capability="board_members",
            api_name=api_name,
            parameters={"symbol": board_name},
            fields_expected=INTERNAL_BOARD_FIELDS,
            impacts=["board filter", "stock board membership cache"],
            fallback="skip board membership until cached mapping is available",
            normalizer=lambda frame: self._normalize_board_members(frame, board_id),
            original_units={"成交量": "provider_original", "成交额": "provider_original"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_stock_board_memberships(self, symbol: str) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="stock_board_memberships",
                api_name="board_member_reverse_lookup",
                status="NOT_SUPPORTED",
                parameters_summary={"symbol": normalize_symbol(symbol), "sample_scan_cap": 10},
                fields_expected=INTERNAL_BOARD_FIELDS,
                impacts_features=["stock detail classification", "board filter"],
                recommended_fallback="Build a nightly cached stock-board map from board member APIs; spike sample scan is capped at 10 boards.",
                error_message="No confirmed public reverse lookup function in AKShare candidates.",
            ),
        )

    def get_stock_status(self, symbol: str) -> ProviderResult:
        snapshot = self.get_stock_snapshot([symbol])
        if snapshot.record.status not in {"PASS", "PASS_EMPTY"}:
            return snapshot
        data = snapshot.data.copy()
        if data.empty:
            data = pd.DataFrame([{"symbol": normalize_symbol(symbol), "trade_status": "unknown", "provider": self.provider_name}])
        return ProviderResult(
            data[["symbol", "trade_status", "provider"]],
            capability_record_from_frame(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="stock_status",
                api_name="stock_zh_a_spot_em",
                frame=data,
                queried_at=now_shanghai(),
                parameters_summary={"symbol": normalize_symbol(symbol)},
                fields_expected=["symbol", "trade_status", "provider"],
                duration_ms=snapshot.record.duration_ms,
                source_type=self.source_type,
                original_units={},
                normalized_units={},
                impacts_features=["stock status", "suspended/stale display"],
                recommended_fallback="BaoStock historical status or manual status review",
                status="PARTIAL_PASS",
                error_message="Status is inferred from snapshot availability/price fields, not a full delisting lifecycle model.",
                fields_returned=snapshot.record.fields_returned,
            ),
        )

    def get_announcements(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        candidates = ["stock_notice_report", "stock_zh_a_disclosure_report_cninfo"]
        for api_name in candidates:
            if self._resolve_public_function(api_name) is not None:
                return self._call(
                    capability="announcements",
                    api_name=api_name,
                    parameters={"symbol": provider_symbol(symbol, self.provider_name), "date": _compact_date(end_date)},
                    fields_expected=["symbol", "title", "publish_time", "source_url"],
                    impacts=["information center", "review materials"],
                    fallback="exchange/public links manually pasted by user or paid announcement source",
                    normalizer=lambda frame: self._normalize_announcements(frame, symbol),
                )
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="announcements",
                api_name="stock_notice_report|stock_zh_a_disclosure_report_cninfo",
                status="NOT_SUPPORTED",
                parameters_summary={"symbol": normalize_symbol(symbol), "start_date": start_date, "end_date": end_date},
                fields_expected=["symbol", "title", "publish_time", "source_url"],
                impacts_features=["information center", "review materials"],
                recommended_fallback="Use exchange official disclosure sources, user-pasted links, or authorized information provider.",
                error_message="No confirmed announcement public function found among configured AKShare candidates.",
            ),
        )

    def _normalize_universe(self, frame: pd.DataFrame) -> pd.DataFrame:
        _require_columns(frame, ["代码", "名称"])
        result = normalize_by_mapping(
            frame,
            mapping={"symbol": "代码", "name": "名称"},
            provider=self.provider_name,
            defaults={"currency": "CNY", "list_status": "active_or_unknown", "market": "A股"},
        )
        result["exchange"] = result["symbol"].map(lambda value: value.split(".")[1] if isinstance(value, str) and "." in value else None)
        result["fetched_at"] = now_shanghai()
        return with_missing_columns(result, INTERNAL_STOCK_BASIC_FIELDS)

    def _normalize_snapshot(self, frame: pd.DataFrame) -> pd.DataFrame:
        _require_columns(frame, ["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额"])
        result = normalize_by_mapping(
            frame,
            mapping={
                "symbol": "代码",
                "close": "最新价",
                "change": "涨跌额",
                "pct_change": "涨跌幅",
                "volume": "成交量",
                "amount": "成交额",
                "amplitude": "振幅",
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
        result["quote_time"] = now_shanghai()
        result["trade_date"] = now_shanghai()[:10]
        result["fetched_at"] = now_shanghai()
        result.loc[result["close"].isna(), "trade_status"] = "suspended_or_unavailable"
        return with_missing_columns(result, INTERNAL_SNAPSHOT_FIELDS)

    def _normalize_daily(self, frame: pd.DataFrame, symbol: str, adjustment: str) -> pd.DataFrame:
        _require_columns(frame, ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"])
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
        datetime_column = "时间" if "时间" in frame.columns else "日期" if "日期" in frame.columns else None
        _require_columns(frame, [datetime_column or "时间", "开盘", "收盘", "最高", "最低"])
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

    def _normalize_index(self, frame: pd.DataFrame, index_code: str) -> pd.DataFrame:
        result = self._normalize_daily(frame, index_code, "none")
        result["symbol"] = normalize_symbol(index_code)
        return result

    def _normalize_board_names(self, frame: pd.DataFrame, board_type: str) -> pd.DataFrame:
        name_column = "板块名称" if "板块名称" in frame.columns else "名称" if "名称" in frame.columns else None
        _require_columns(frame, [name_column or "板块名称"])
        rows = []
        for _, row in frame.iterrows():
            name = row.get(name_column)
            rows.append(
                {
                    "board_id": f"{board_type}:{name}",
                    "board_name": name,
                    "board_type": board_type,
                    "source_system": "eastmoney_via_akshare",
                    "symbol": None,
                    "effective_date": None,
                    "provider": self.provider_name,
                }
            )
        return with_missing_columns(pd.DataFrame(rows), INTERNAL_BOARD_FIELDS)

    def _normalize_board_members(self, frame: pd.DataFrame, board_id: str) -> pd.DataFrame:
        code_column = "代码" if "代码" in frame.columns else "股票代码" if "股票代码" in frame.columns else None
        _require_columns(frame, [code_column or "代码"])
        board_type = "standard_industry" if board_id.startswith("standard_industry:") else "concept_board"
        board_name = board_id.split(":", 1)[1] if ":" in board_id else board_id
        rows = []
        for _, row in frame.iterrows():
            rows.append(
                {
                    "board_id": board_id,
                    "board_name": board_name,
                    "board_type": board_type,
                    "source_system": "eastmoney_via_akshare",
                    "symbol": normalize_symbol(row.get(code_column)),
                    "effective_date": None,
                    "provider": self.provider_name,
                }
            )
        return with_missing_columns(pd.DataFrame(rows), INTERNAL_BOARD_FIELDS)

    def _normalize_announcements(self, frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["symbol", "title", "publish_time", "source_url", "provider"])
        title_column = next((column for column in ["公告标题", "title", "标题"] if column in frame.columns), None)
        url_column = next((column for column in ["公告链接", "url", "链接"] if column in frame.columns), None)
        date_column = next((column for column in ["公告日期", "publish_time", "发布时间", "date"] if column in frame.columns), None)
        rows = []
        for _, row in frame.iterrows():
            rows.append(
                {
                    "symbol": normalize_symbol(symbol),
                    "title": row.get(title_column) if title_column else None,
                    "publish_time": normalize_datetime(row.get(date_column)) if date_column else None,
                    "source_url": row.get(url_column) if url_column else None,
                    "provider": self.provider_name,
                }
            )
        return pd.DataFrame(rows)


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column and column not in frame.columns]
    if missing:
        raise ValueError(f"required raw columns missing: {', '.join(missing)}; returned={list(frame.columns)}")


def _compact_date(value: str) -> str:
    normalized = normalize_date(value)
    return "" if normalized is None else normalized.replace("-", "")


def _compact_datetime(value: str) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return value

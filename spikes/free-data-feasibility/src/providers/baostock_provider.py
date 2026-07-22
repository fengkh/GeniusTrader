from __future__ import annotations

import time
from typing import Any

import pandas as pd

from ..capability import capability_record_from_frame, classify_exception, now_shanghai, synthetic_record
from ..models import INTERNAL_BOARD_FIELDS, INTERNAL_DAILY_FIELDS, INTERNAL_STOCK_BASIC_FIELDS, ProviderResult
from ..normalization import NORMALIZED_UNITS, normalize_by_mapping, normalize_date, normalize_symbol, provider_index_symbol, provider_symbol, with_missing_columns
from .base import BaseProvider


BAOSTOCK_FUNCTIONS = [
    "login",
    "logout",
    "query_history_k_data_plus",
    "query_all_stock",
    "query_stock_industry",
]


class BaoStockProvider(BaseProvider):
    provider_name = "baostock"

    def __init__(self, module: Any | None = None, *, request_interval: float = 1.0) -> None:
        super().__init__(module=module, request_interval=request_interval)
        self._logged_in = False

    def health_check(self) -> ProviderResult:
        error = self._ensure_login()
        if error is not None:
            return ProviderResult(
                pd.DataFrame(),
                synthetic_record(
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    capability="health_check",
                    api_name="login",
                    status=classify_exception(error),
                    error_message=str(error),
                    impacts_features=["baostock provider"],
                    recommended_fallback="skip BaoStock provider",
                ),
            )
        return ProviderResult(
            pd.DataFrame([{"provider": self.provider_name, "version": self.provider_version, "login": "ok"}]),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="health_check",
                api_name="login",
                status="PASS",
                fields_returned=["provider", "version", "login"],
                recommended_fallback="skip BaoStock provider",
            ),
        )

    def get_stock_universe(self) -> ProviderResult:
        end = pd.Timestamp.now(tz="Asia/Shanghai").date().isoformat()
        return self._query(
            capability="stock_universe",
            api_name="query_all_stock",
            parameters={"day": end},
            fields_expected=INTERNAL_STOCK_BASIC_FIELDS,
            impacts=["stock_basic", "BSE coverage check"],
            fallback="AKShare universe or paid stock-basic source",
            query=lambda: self.module.query_all_stock(day=end),
            normalizer=self._normalize_universe,
        )

    def get_daily_history(self, symbol: str, start_date: str, end_date: str, adjust: str) -> ProviderResult:
        adjustflag = {"hfq": "1", "qfq": "2", "none": "3", "unadjusted": "3", "": "3"}.get(adjust, "3")
        fields = "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,tradestatus,isST"
        return self._query(
            capability="daily_history_qfq" if adjustflag == "2" else "daily_history_hfq" if adjustflag == "1" else "daily_history",
            api_name="query_history_k_data_plus",
            parameters={
                "code": provider_symbol(symbol, self.provider_name),
                "fields": fields,
                "start_date": start_date,
                "end_date": end_date,
                "frequency": "d",
                "adjustflag": adjustflag,
            },
            fields_expected=INTERNAL_DAILY_FIELDS,
            impacts=["daily K", "program metrics", "historical floor"],
            fallback="AKShare or efinance daily; if all fail show historical unavailable state",
            query=lambda: self.module.query_history_k_data_plus(
                provider_symbol(symbol, self.provider_name),
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=adjustflag,
            ),
            normalizer=lambda frame: self._normalize_daily(frame, adjust),
            original_units={"volume": "share", "amount": "CNY_yuan", "turn": "percent_value", "pctChg": "percent_value"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_index_history(self, index_code: str, start_date: str, end_date: str) -> ProviderResult:
        fields = "date,code,open,high,low,close,preclose,volume,amount,pctChg"
        return self._query(
            capability="index_history",
            api_name="query_history_k_data_plus",
            parameters={
                "code": provider_index_symbol(index_code, self.provider_name),
                "fields": fields,
                "start_date": start_date,
                "end_date": end_date,
                "frequency": "d",
                "adjustflag": "3",
            },
            fields_expected=INTERNAL_DAILY_FIELDS,
            impacts=["relative index strength"],
            fallback="AKShare index history or degrade relative index metric",
            query=lambda: self.module.query_history_k_data_plus(
                provider_index_symbol(index_code, self.provider_name),
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",
            ),
            normalizer=lambda frame: self._normalize_daily(frame, "none"),
            original_units={"volume": "share", "amount": "CNY_yuan"},
            normalized_units=NORMALIZED_UNITS,
        )

    def get_industry_boards(self) -> ProviderResult:
        return self._query(
            capability="industry_boards",
            api_name="query_stock_industry",
            parameters={},
            fields_expected=INTERNAL_BOARD_FIELDS,
            impacts=["board filter", "stock classification"],
            fallback="AKShare board APIs or paid classification source",
            query=lambda: self.module.query_stock_industry(),
            normalizer=self._normalize_industry_boards,
        )

    def get_board_members(self, board_id: str) -> ProviderResult:
        industry = board_id.split(":", 1)[1] if ":" in board_id else board_id
        return self._query(
            capability="board_members",
            api_name="query_stock_industry",
            parameters={"board_id": board_id},
            fields_expected=INTERNAL_BOARD_FIELDS,
            impacts=["board filter", "stock board membership cache"],
            fallback="AKShare board member APIs",
            query=lambda: self.module.query_stock_industry(),
            normalizer=lambda frame: self._normalize_industry_members(frame, industry),
        )

    def get_stock_board_memberships(self, symbol: str) -> ProviderResult:
        normalized = normalize_symbol(symbol)
        return self._query(
            capability="stock_board_memberships",
            api_name="query_stock_industry",
            parameters={"symbol": normalized},
            fields_expected=INTERNAL_BOARD_FIELDS,
            impacts=["stock detail classification"],
            fallback="Build stock-board cache from AKShare board members or use paid classification source",
            query=lambda: self.module.query_stock_industry(),
            normalizer=lambda frame: self._normalize_stock_memberships(frame, normalized),
        )

    def get_stock_status(self, symbol: str) -> ProviderResult:
        end = pd.Timestamp.now(tz="Asia/Shanghai").date().isoformat()
        start = (pd.Timestamp.now(tz="Asia/Shanghai") - pd.Timedelta(days=30)).date().isoformat()
        result = self.get_daily_history(symbol, start, end, "none")
        if result.data.empty:
            return result
        status = result.data[["symbol", "trade_date", "provider"]].tail(1).copy()
        status["trade_status"] = "available_from_history"
        return ProviderResult(status, result.record)

    def get_stock_snapshot(self, symbols: list[str]) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="stock_snapshot",
                api_name="not_supported",
                status="NOT_SUPPORTED",
                parameters_summary={"symbols": [normalize_symbol(symbol) for symbol in symbols]},
                fields_expected=["latest quote fields"],
                impacts_features=["today latest quote", "watchlist latest quote"],
                recommended_fallback="Use AKShare or efinance for latest snapshots.",
            ),
        )

    def get_minute_history(self, symbol: str, start_datetime: str, end_datetime: str, period: str) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="minute_history",
                api_name="not_supported",
                status="NOT_SUPPORTED",
                parameters_summary={"symbol": normalize_symbol(symbol), "period": period},
                fields_expected=["minute OHLCV"],
                impacts_features=["intraday chart", "max intraday drawdown"],
                recommended_fallback="Use AKShare or efinance minute APIs; degrade intraday chart if unavailable.",
            ),
        )

    def get_concept_boards(self) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="concept_boards",
                api_name="not_supported",
                status="NOT_SUPPORTED",
                fields_expected=INTERNAL_BOARD_FIELDS,
                impacts_features=["concept board filter"],
                recommended_fallback="Use AKShare concept boards or paid classification source.",
            ),
        )

    def get_announcements(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="announcements",
                api_name="not_supported",
                status="NOT_SUPPORTED",
                parameters_summary={"symbol": normalize_symbol(symbol)},
                fields_expected=["symbol", "title", "publish_time", "source_url"],
                impacts_features=["information center", "review materials"],
                recommended_fallback="Use exchange/public links manually pasted by user or authorized information provider.",
            ),
        )

    def close(self) -> None:
        if self._logged_in and hasattr(self.module, "logout"):
            self.module.logout()
            self._logged_in = False

    def _ensure_login(self) -> Exception | None:
        if self._logged_in:
            return None
        try:
            result = self.module.login()
            error_code = getattr(result, "error_code", "0")
            error_msg = getattr(result, "error_msg", "")
            if str(error_code) != "0":
                return RuntimeError(f"BaoStock login failed: {error_code} {error_msg}")
            self._logged_in = True
            return None
        except Exception as error:  # noqa: BLE001
            return error

    def _query(
        self,
        *,
        capability: str,
        api_name: str,
        parameters: dict[str, Any],
        fields_expected: list[str],
        impacts: list[str],
        fallback: str,
        query: Any,
        normalizer: Any,
        original_units: dict[str, str] | None = None,
        normalized_units: dict[str, str] | None = None,
    ) -> ProviderResult:
        login_error = self._ensure_login()
        if login_error is not None:
            return ProviderResult(
                pd.DataFrame(),
                synthetic_record(
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    capability=capability,
                    api_name=api_name,
                    status=classify_exception(login_error),
                    parameters_summary=parameters,
                    fields_expected=fields_expected,
                    error_message=str(login_error),
                    impacts_features=impacts,
                    recommended_fallback=fallback,
                ),
            )
        start = time.perf_counter()
        try:
            raw_result = query()
            frame = _query_result_to_frame(raw_result)
            duration_ms = int((time.perf_counter() - start) * 1000)
            normalized = normalizer(frame)
            record = capability_record_from_frame(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability=capability,
                api_name=api_name,
                frame=normalized,
                queried_at=now_shanghai(),
                parameters_summary=parameters,
                fields_expected=fields_expected,
                duration_ms=duration_ms,
                source_type=self.source_type,
                original_units=original_units or {},
                normalized_units=normalized_units or {},
                impacts_features=impacts,
                recommended_fallback=fallback,
                status="PASS" if len(normalized) else "PASS_EMPTY",
                fields_returned=list(map(str, frame.columns)),
            )
            return ProviderResult(normalized, record)
        except Exception as error:  # noqa: BLE001
            return ProviderResult(
                pd.DataFrame(),
                synthetic_record(
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    capability=capability,
                    api_name=api_name,
                    status=classify_exception(error),
                    parameters_summary=parameters,
                    fields_expected=fields_expected,
                    error_message=str(error),
                    impacts_features=impacts,
                    recommended_fallback=fallback,
                ),
            )

    def _normalize_universe(self, frame: pd.DataFrame) -> pd.DataFrame:
        code_column = "code" if "code" in frame.columns else "证券代码" if "证券代码" in frame.columns else None
        name_column = "code_name" if "code_name" in frame.columns else "证券名称" if "证券名称" in frame.columns else None
        _require_columns(frame, [code_column])
        result = normalize_by_mapping(
            frame,
            mapping={"symbol": code_column, "name": name_column},
            provider=self.provider_name,
            defaults={"currency": "CNY", "list_status": "active_or_unknown", "market": "A股"},
        )
        result["exchange"] = result["symbol"].map(lambda value: value.split(".")[1] if isinstance(value, str) and "." in value else None)
        result["fetched_at"] = now_shanghai()
        return with_missing_columns(result, INTERNAL_STOCK_BASIC_FIELDS)

    def _normalize_daily(self, frame: pd.DataFrame, adjustment: str) -> pd.DataFrame:
        _require_columns(frame, ["date", "code", "open", "high", "low", "close"])
        result = normalize_by_mapping(
            frame,
            mapping={
                "symbol": "code",
                "trade_date": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "pre_close": "preclose",
                "volume": "volume",
                "amount": "amount",
                "turnover_rate": "turn",
                "pct_change": "pctChg",
            },
            provider=self.provider_name,
            volume_unit="share",
            amount_unit="yuan",
            defaults={"adjustment": adjustment},
        )
        if "amplitude" not in result.columns:
            result["amplitude"] = (pd.to_numeric(result["high"], errors="coerce") - pd.to_numeric(result["low"], errors="coerce")) / pd.to_numeric(result["pre_close"], errors="coerce") * 100
        return with_missing_columns(result, INTERNAL_DAILY_FIELDS)

    def _normalize_industry_boards(self, frame: pd.DataFrame) -> pd.DataFrame:
        industry_column = _first_column(frame, ["industry", "所属行业", "industryClassification"])
        _require_columns(frame, [industry_column])
        industries = sorted(str(value) for value in frame[industry_column].dropna().unique())
        rows = [
            {
                "board_id": f"standard_industry:{industry}",
                "board_name": industry,
                "board_type": "standard_industry",
                "source_system": "baostock_query_stock_industry",
                "symbol": None,
                "effective_date": None,
                "provider": self.provider_name,
            }
            for industry in industries
        ]
        return with_missing_columns(pd.DataFrame(rows), INTERNAL_BOARD_FIELDS)

    def _normalize_industry_members(self, frame: pd.DataFrame, industry: str) -> pd.DataFrame:
        code_column = _first_column(frame, ["code", "证券代码"])
        industry_column = _first_column(frame, ["industry", "所属行业", "industryClassification"])
        _require_columns(frame, [code_column, industry_column])
        subset = frame[frame[industry_column].astype(str) == industry]
        rows = [
            {
                "board_id": f"standard_industry:{industry}",
                "board_name": industry,
                "board_type": "standard_industry",
                "source_system": "baostock_query_stock_industry",
                "symbol": normalize_symbol(row.get(code_column)),
                "effective_date": None,
                "provider": self.provider_name,
            }
            for _, row in subset.iterrows()
        ]
        return with_missing_columns(pd.DataFrame(rows), INTERNAL_BOARD_FIELDS)

    def _normalize_stock_memberships(self, frame: pd.DataFrame, symbol: str | None) -> pd.DataFrame:
        code_column = _first_column(frame, ["code", "证券代码"])
        industry_column = _first_column(frame, ["industry", "所属行业", "industryClassification"])
        _require_columns(frame, [code_column, industry_column])
        normalized_codes = frame[code_column].map(normalize_symbol)
        subset = frame[normalized_codes == symbol]
        rows = []
        for _, row in subset.iterrows():
            industry = row.get(industry_column)
            rows.append(
                {
                    "board_id": f"standard_industry:{industry}",
                    "board_name": industry,
                    "board_type": "standard_industry",
                    "source_system": "baostock_query_stock_industry",
                    "symbol": symbol,
                    "effective_date": None,
                    "provider": self.provider_name,
                }
            )
        return with_missing_columns(pd.DataFrame(rows), INTERNAL_BOARD_FIELDS)


def _query_result_to_frame(result: Any) -> pd.DataFrame:
    if result is None:
        return pd.DataFrame()
    error_code = getattr(result, "error_code", "0")
    error_msg = getattr(result, "error_msg", "")
    if str(error_code) != "0":
        raise RuntimeError(f"BaoStock query failed: {error_code} {error_msg}")
    fields = list(getattr(result, "fields", []) or [])
    rows = []
    while result.next():
        rows.append(result.get_row_data())
    return pd.DataFrame(rows, columns=fields)


def _require_columns(frame: pd.DataFrame, columns: list[str | None]) -> None:
    missing = [column for column in columns if column and column not in frame.columns]
    if missing:
        raise ValueError(f"required raw columns missing: {', '.join(missing)}; returned={list(frame.columns)}")


def _first_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    return next((column for column in candidates if column in frame.columns), None)

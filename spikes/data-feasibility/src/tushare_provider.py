from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .capability import (
    capability_record_from_frame,
    normalize_exception,
    now_queried_at,
    redact_text,
    synthetic_record,
    timed_call,
)
from .models import CapabilityRecord

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

DEFAULT_SYMBOLS = ["600519.SH", "000001.SZ", "300750.SZ", "688981.SH"]

FIELD_SETS = {
    "trade_cal": "exchange,cal_date,is_open,pretrade_date",
    "stock_basic": "ts_code,symbol,name,market,exchange,list_status,list_date,delist_date,industry",
    "daily": "ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
    "daily_basic": "ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,total_share,float_share,free_share,total_mv,circ_mv",
    "adj_factor": "ts_code,trade_date,adj_factor",
    "suspend_d": "ts_code,suspend_date,resume_date,ann_date,suspend_reason,reason_type",
    "index_daily": "ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
    "anns_d": "ts_code,name,title,ann_date,ann_time,url",
    "rt_min_daily": "ts_code,trade_time,open,high,low,close,vol,amount",
}

UNIT_NOTES = {
    "trade_cal": "cal_date is YYYYMMDD; is_open 1=open, 0=closed.",
    "stock_basic": "Static stock metadata; list_status L=list, D=delist, P=pause depending on provider.",
    "daily": "Tushare daily vol/amount units must be confirmed before formal provider mapping.",
    "daily_basic": "Market cap fields are usually in 10k CNY; share fields and ratios require provider confirmation.",
    "adj_factor": "Use latest valid factor as normalization base for local qfq calculation.",
    "suspend_d": "No rows means no suspend/resume event for queried range, not an error.",
    "index_daily": "Index OHLC and amount units require provider confirmation before formal mapping.",
    "index_member_all": "Used for Shenwan industry hierarchy and latest membership state when available.",
    "sw_daily": "Official Shenwan daily quote interface candidate; do not substitute with generic index_daily.",
    "rt_min_daily": "Minute data availability depends on current time window, points/permission and provider freshness.",
    "anns_d": "Announcement metadata only; do not save complete announcement body.",
    "tdx_member": "Optional standard concept/member probe; do not expand into broad theme crawling.",
    "news": "Optional small permission probe; do not save full news text.",
}


class TushareProvider:
    def __init__(self, token: str, pro_client: Any | None = None) -> None:
        if not token:
            raise ValueError("TUSHARE_TOKEN is required")
        self.token = token
        if pro_client is not None:
            self.pro = pro_client
            return

        import tushare as ts

        self.pro = ts.pro_api(token)

    def query(
        self,
        *,
        capability: str,
        api_name: str,
        params: dict[str, Any] | None = None,
        fields: str | None = None,
        impacts_features: list[str] | None = None,
        recommended_fallback: str = "",
        unit_notes: str | None = None,
    ) -> tuple[pd.DataFrame, CapabilityRecord]:
        params = params or {}
        queried_at = now_queried_at()
        safe_params = {key: redact_text(value, self.token) for key, value in params.items()}

        try:
            frame, duration_ms = timed_call(lambda: self.pro.query(api_name, fields=fields or "", **params))
            record = capability_record_from_frame(
                capability=capability,
                api_name=api_name,
                frame=frame,
                queried_at=queried_at,
                parameters_summary=safe_params,
                fields_requested=fields,
                duration_ms=duration_ms,
                unit_notes=unit_notes or UNIT_NOTES.get(api_name, ""),
                impacts_features=impacts_features or [],
                recommended_fallback=recommended_fallback,
            )
            return frame, record
        except Exception as error:  # noqa: BLE001 - provider errors are normalized for capability reports.
            status, message = normalize_exception(error, self.token)
            record = synthetic_record(
                capability=capability,
                api_name=api_name,
                status=status,
                queried_at=queried_at,
                parameters_summary=safe_params,
                fields_requested=fields,
                unit_notes=unit_notes or UNIT_NOTES.get(api_name, ""),
                permission_or_error_message=message,
                impacts_features=impacts_features or [],
                recommended_fallback=recommended_fallback,
            )
            return pd.DataFrame(), record


def shanghai_now() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def yyyymmdd(value: datetime) -> str:
    return value.strftime("%Y%m%d")


def start_date_for_days(days: int, now: datetime | None = None) -> str:
    now = now or shanghai_now()
    return yyyymmdd(now - timedelta(days=days))


def latest_ended_trade_date(trade_cal: pd.DataFrame, now: datetime | None = None) -> str | None:
    if trade_cal.empty or "cal_date" not in trade_cal.columns or "is_open" not in trade_cal.columns:
        return None

    now = now or shanghai_now()
    calendar = trade_cal.copy()
    calendar["cal_date"] = calendar["cal_date"].astype(str)
    calendar["is_open"] = pd.to_numeric(calendar["is_open"], errors="coerce")
    open_days = calendar[calendar["is_open"] == 1].sort_values("cal_date")

    today = now.strftime("%Y%m%d")
    if now.time() >= dt_time(16, 0):
        candidates = open_days[open_days["cal_date"] <= today]
    else:
        candidates = open_days[open_days["cal_date"] < today]

    if candidates.empty:
        return None
    return str(candidates["cal_date"].iloc[-1])


def is_minute_probe_window(trade_cal: pd.DataFrame, now: datetime | None = None) -> bool:
    now = now or shanghai_now()
    today = now.strftime("%Y%m%d")
    if trade_cal.empty or "cal_date" not in trade_cal.columns or "is_open" not in trade_cal.columns:
        return False
    today_row = trade_cal[trade_cal["cal_date"].astype(str) == today]
    if today_row.empty or int(today_row["is_open"].iloc[0]) != 1:
        return False
    return dt_time(9, 30) <= now.time() <= dt_time(15, 30)


def select_bse_symbol(stock_basic: pd.DataFrame) -> tuple[str | None, str | None]:
    if stock_basic.empty:
        return None, "stock_basic returned no rows"
    required = {"ts_code", "exchange", "list_status"}
    missing = required - set(stock_basic.columns)
    if missing:
        return None, f"stock_basic missing fields: {', '.join(sorted(missing))}"

    bse = stock_basic[
        (stock_basic["exchange"].astype(str).str.upper().isin(["BSE", "BJSE"]))
        & (stock_basic["list_status"].astype(str).str.upper() == "L")
    ].copy()
    if bse.empty:
        bse = stock_basic[
            (stock_basic["ts_code"].astype(str).str.endswith(".BJ"))
            & (stock_basic["list_status"].astype(str).str.upper() == "L")
        ].copy()
    if bse.empty:
        return None, "no listed BSE/BJ stock found in stock_basic"
    bse = bse.sort_values("ts_code")
    return str(bse["ts_code"].iloc[0]), None


def choose_samples(stock_basic: pd.DataFrame, override_symbols: list[str] | None = None) -> tuple[list[str], list[str]]:
    if override_symbols:
        return override_symbols, ["symbols overridden by command line"]

    notes: list[str] = []
    symbols = list(DEFAULT_SYMBOLS)
    bse_symbol, reason = select_bse_symbol(stock_basic)
    if bse_symbol:
        symbols.append(bse_symbol)
        notes.append(f"selected deterministic BSE sample: {bse_symbol}")
    else:
        notes.append(f"BSE sample unavailable: {reason}")
    return symbols, notes


def benchmark_for_symbol(symbol: str) -> tuple[str | None, str]:
    if symbol.endswith(".BJ"):
        return None, "BSE benchmark not confirmed"
    if symbol.startswith("300"):
        return "399006.SZ", "ChiNext sample uses ChiNext Index"
    return "000300.SH", "default A-share benchmark uses CSI 300"

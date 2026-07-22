from __future__ import annotations

import importlib
import time
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import pandas as pd

from .financial_normalization import FutureDataError, normalize_financial_record
from .market_breadth import compute_market_breadth

CAPABILITY_VERSION = "gt-market-provider-probe-v0.1"


@dataclass(frozen=True)
class ProbeRecord:
    provider: str
    capability: str
    api_name: str
    status: str
    row_count: int
    fields_returned: list[str]
    earliest_date: str | None = None
    latest_date: str | None = None
    error_message: str | None = None
    source_type: str = "public_library"
    fallback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _record(
    provider: str,
    capability: str,
    api_name: str,
    status: str,
    frame: pd.DataFrame | None = None,
    *,
    error: Exception | str | None = None,
    fallback: str = "",
) -> ProbeRecord:
    frame = pd.DataFrame() if frame is None else frame
    earliest = None
    latest = None
    for column in ["trade_date", "date", "pubDate", "announcement_date"]:
        if column in frame.columns and not frame[column].dropna().empty:
            values = frame[column].astype(str)
            earliest = values.min()
            latest = values.max()
            break
    return ProbeRecord(
        provider=provider,
        capability=capability,
        api_name=api_name,
        status=status,
        row_count=int(len(frame)),
        fields_returned=list(map(str, frame.columns)),
        earliest_date=earliest,
        latest_date=latest,
        error_message=None if error is None else str(error),
        fallback=fallback,
    )


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


def _bs_symbol(symbol: str) -> str:
    symbol = symbol.strip()
    if symbol.startswith(("sh.", "sz.", "bj.")):
        return symbol
    code = symbol.split(".")[0]
    suffix = symbol.split(".")[-1].upper() if "." in symbol else ""
    if suffix == "SH" or code.startswith(("5", "6", "9")):
        return f"sh.{code}"
    if suffix == "BJ" or code.startswith(("4", "8", "92")):
        return f"bj.{code}"
    return f"sz.{code}"


def _norm_symbol(provider_code: Any) -> str | None:
    if provider_code is None:
        return None
    code = str(provider_code)
    if code.startswith("sh."):
        return f"{code[3:]}.SH"
    if code.startswith("sz."):
        return f"{code[3:]}.SZ"
    if code.startswith("bj."):
        return f"{code[3:]}.BJ"
    return code


def _normalize_daily(frame: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "date": "trade_date",
        "code": "symbol",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "preclose": "pre_close",
        "volume": "volume",
        "amount": "amount",
        "turn": "turnover_rate",
        "pctChg": "pct_change",
        "tradestatus": "trade_status",
        "isST": "is_st",
    }
    rows = []
    for _, row in frame.iterrows():
        payload = {dst: row.get(src) for src, dst in mapping.items() if src in frame.columns}
        if "symbol" in payload:
            payload["symbol"] = _norm_symbol(payload["symbol"])
        rows.append(payload)
    result = pd.DataFrame(rows)
    for column in ["open", "high", "low", "close", "pre_close", "volume", "amount", "turnover_rate", "pct_change"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    if "is_st" in result.columns:
        result["is_st"] = result["is_st"].astype(str).isin(["1", "True", "true", "ST"])
    return result


def _fetch_baostock_daily(bs: Any, symbol: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, ProbeRecord]:
    fields = "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,tradestatus,isST"
    try:
        raw = _query_result_to_frame(
            bs.query_history_k_data_plus(
                _bs_symbol(symbol),
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",
            )
        )
        normalized = _normalize_daily(raw)
        return normalized, _record("baostock", "daily_history", "query_history_k_data_plus", "PASS" if len(normalized) else "PASS_EMPTY", normalized)
    except Exception as error:  # noqa: BLE001
        return pd.DataFrame(), _record(
            "baostock",
            "daily_history",
            "query_history_k_data_plus",
            "UPSTREAM_ERROR",
            error=error,
            fallback="Use another daily-history provider or mark this stock unavailable.",
        )


def probe_efinance_snapshot() -> dict[str, Any]:
    try:
        module = importlib.import_module("efinance")
        stock = getattr(module, "stock")
        try:
            frame = stock.get_realtime_quotes()
        except TypeError:
            frame = stock.get_realtime_quotes("沪深A股")
        frame = pd.DataFrame(frame)
        status = "PASS" if len(frame) else "PASS_EMPTY"
        record = _record("efinance", "market_snapshot", "stock.get_realtime_quotes", status, frame)
        return {"record": record.to_dict(), "row_count": len(frame), "fields": list(map(str, frame.columns))}
    except Exception as error:  # noqa: BLE001
        return {
            "record": _record(
                "efinance",
                "market_snapshot",
                "stock.get_realtime_quotes",
                "UPSTREAM_ERROR",
                error=error,
                fallback="Use stale cached snapshot, BaoStock scheduled daily batch, or paid/latest snapshot source.",
            ).to_dict(),
            "row_count": 0,
            "fields": [],
        }


def probe_baostock_market_data(
    *,
    max_boards: int,
    max_stocks_per_board: int,
    days: int,
    request_interval: float,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    records: list[ProbeRecord] = []
    board_daily: dict[str, dict[str, pd.DataFrame]] = {}
    board_rows: list[dict[str, Any]] = []
    valuation_financials: list[dict[str, Any]] = []
    valuation_records: list[ProbeRecord] = []
    try:
        bs = importlib.import_module("baostock")
    except Exception as error:  # noqa: BLE001
        records.append(_record("baostock", "import", "import", "UPSTREAM_ERROR", error=error, fallback="Install baostock or use another provider."))
        return {
            "records": [item.to_dict() for item in records],
            "boards": [],
            "board_daily": {},
            "market_breadth": compute_market_breadth(None, as_of_date=as_of_date),
            "valuation_financials": [],
            "valuation_records": [],
            "network_completed": False,
        }
    login = bs.login()
    if str(getattr(login, "error_code", "0")) != "0":
        records.append(
            _record(
                "baostock",
                "health_check",
                "login",
                "UPSTREAM_ERROR",
                error=f"{getattr(login, 'error_code', '')} {getattr(login, 'error_msg', '')}",
                fallback="Skip BaoStock provider.",
            )
        )
        return {
            "records": [item.to_dict() for item in records],
            "boards": [],
            "board_daily": {},
            "market_breadth": compute_market_breadth(None, as_of_date=as_of_date),
            "valuation_financials": [],
            "valuation_records": [],
            "network_completed": False,
        }
    try:
        end = pd.to_datetime(as_of_date).date() if as_of_date else pd.Timestamp.now(tz="Asia/Shanghai").date()
        start = (pd.Timestamp(end) - pd.Timedelta(days=days)).date()
        try:
            universe = _query_result_to_frame(bs.query_all_stock(day=end.isoformat()))
            records.append(_record("baostock", "stock_universe", "query_all_stock", "PASS" if len(universe) else "PASS_EMPTY", universe))
        except Exception as error:  # noqa: BLE001
            universe = pd.DataFrame()
            records.append(_record("baostock", "stock_universe", "query_all_stock", "UPSTREAM_ERROR", error=error, fallback="Use paid stock-basic or alternate public source."))
        pause(request_interval)
        try:
            industry = _query_result_to_frame(bs.query_stock_industry())
            records.append(_record("baostock", "industry_boards", "query_stock_industry", "PASS" if len(industry) else "PASS_EMPTY", industry))
        except Exception as error:  # noqa: BLE001
            industry = pd.DataFrame()
            records.append(_record("baostock", "industry_boards", "query_stock_industry", "UPSTREAM_ERROR", error=error, fallback="Use AKShare concepts if stable, paid source, or manual classification."))
        pause(request_interval)
        if not industry.empty:
            industry_col = "industry" if "industry" in industry.columns else "industryClassification" if "industryClassification" in industry.columns else None
            code_col = "code" if "code" in industry.columns else None
            if industry_col and code_col:
                counts = industry[industry_col].dropna().astype(str).value_counts().head(max_boards)
                for board_name, _ in counts.items():
                    subset = industry[industry[industry_col].astype(str) == board_name].head(max_stocks_per_board)
                    board_id = f"standard_industry:{board_name}"
                    board_rows.append({"board_id": board_id, "board_name": board_name, "member_count_sample": int(len(subset))})
                    members = {}
                    for code in subset[code_col].dropna().astype(str):
                        symbol = _norm_symbol(code) or code
                        daily, record = _fetch_baostock_daily(bs, symbol, start.isoformat(), end.isoformat())
                        records.append(record)
                        if not daily.empty:
                            members[symbol] = daily
                        pause(request_interval)
                    board_daily[board_id] = members
        valuation_symbols = _deterministic_valuation_symbols(industry, universe)
        for symbol in valuation_symbols:
            price_frame, price_record = _fetch_baostock_daily(
                bs,
                symbol,
                (pd.Timestamp(end) - pd.Timedelta(days=20)).date().isoformat(),
                end.isoformat(),
            )
            records.append(price_record)
            current_price = None
            if not price_frame.empty and "close" in price_frame.columns:
                close_values = pd.to_numeric(price_frame["close"], errors="coerce").dropna()
                if not close_values.empty:
                    current_price = float(close_values.iloc[-1])
            financial, item_records = _probe_baostock_financial(bs, symbol, as_of=end.isoformat(), current_price=current_price)
            valuation_records.extend(item_records)
            if financial is not None:
                valuation_financials.append(financial)
            pause(request_interval)
        sample_rows = []
        for members in board_daily.values():
            for symbol, frame in members.items():
                if not frame.empty:
                    latest = frame.tail(1).copy()
                    latest["symbol"] = symbol
                    sample_rows.append(latest)
        snapshot = pd.concat(sample_rows, ignore_index=True) if sample_rows else pd.DataFrame()
        breadth = compute_market_breadth(snapshot, history_by_symbol={symbol: frame for members in board_daily.values() for symbol, frame in members.items()}, as_of_date=end.isoformat())
        breadth["input_scope"] = "limited_real_provider_sample_not_full_market"
        return {
            "records": [item.to_dict() for item in records],
            "boards": board_rows,
            "board_daily": board_daily,
            "market_breadth": breadth,
            "valuation_financials": valuation_financials,
            "valuation_records": [item.to_dict() for item in valuation_records],
            "network_completed": any(item.status == "PASS" for item in records),
        }
    finally:
        try:
            bs.logout()
        except Exception:  # noqa: BLE001
            pass


def _deterministic_valuation_symbols(industry: pd.DataFrame, universe: pd.DataFrame) -> list[str]:
    preferred = ["600519.SH", "000001.SZ", "300750.SZ", "600000.SH", "600028.SH", "688981.SH", "002594.SZ", "601318.SH"]
    available: set[str] = set()
    for frame in [industry, universe]:
        if frame.empty:
            continue
        code_col = "code" if "code" in frame.columns else None
        if code_col:
            available.update(filter(None, (_norm_symbol(item) for item in frame[code_col].astype(str))))
    result = [symbol for symbol in preferred if not available or symbol in available]
    return result[:8]


def _probe_baostock_financial(bs: Any, symbol: str, *, as_of: str, current_price: float | None = None) -> tuple[dict[str, Any] | None, list[ProbeRecord]]:
    code = _bs_symbol(symbol)
    as_of_date = pd.to_datetime(as_of).date()
    probe_years = [as_of_date.year, as_of_date.year - 1]
    probe_quarters = [1, 4, 3, 2]
    records: list[ProbeRecord] = []
    latest_payload: dict[str, Any] = {
        "symbol": symbol,
        "provider": "baostock",
        "as_of_date": as_of,
        "current_price": current_price,
        "input_sources": ["baostock:query_history_k_data_plus:latest_close"] if current_price is not None else [],
    }
    functions = [
        ("profit", "query_profit_data"),
        ("balance", "query_balance_data"),
        ("cash_flow", "query_cash_flow_data"),
        ("dupont", "query_dupont_data"),
    ]
    for dataset, function_name in functions:
        function = getattr(bs, function_name, None)
        if function is None:
            records.append(_record("baostock", f"financial_{dataset}", function_name, "NOT_SUPPORTED", fallback="Use another financial data source."))
            continue
        success_frame = pd.DataFrame()
        for year in probe_years:
            for quarter in probe_quarters:
                try:
                    frame = _query_result_to_frame(function(code=code, year=year, quarter=quarter))
                    status = "PASS" if len(frame) else "PASS_EMPTY"
                    records.append(_record("baostock", f"financial_{dataset}", function_name, status, frame))
                    if len(frame):
                        success_frame = frame
                        break
                except Exception as error:  # noqa: BLE001
                    records.append(_record("baostock", f"financial_{dataset}", function_name, "UPSTREAM_ERROR", error=error, fallback="Use paid financial source or skip affected valuation method."))
                    break
            if not success_frame.empty:
                break
        if not success_frame.empty:
            row = success_frame.iloc[-1]
            latest_payload["input_sources"].append(f"baostock:{function_name}")
            for key, value in _map_baostock_financial_fields(row).items():
                if value is None or value == "":
                    continue
                latest_payload[key] = value
    try:
        normalized = normalize_financial_record(latest_payload, as_of_date=as_of)
        return normalized, records
    except FutureDataError as error:
        records.append(_record("baostock", "financial_no_future_check", "normalize_financial_record", "DATA_INSUFFICIENT", error=error, fallback="Drop future financial record."))
    except Exception as error:  # noqa: BLE001
        records.append(_record("baostock", "financial_normalization", "normalize_financial_record", "UPSTREAM_ERROR", error=error, fallback="Use another financial provider or mark valuation unavailable."))
    return None, records


def _map_baostock_financial_fields(row: pd.Series) -> dict[str, Any]:
    return {
        "announcement_date": row.get("pubDate"),
        "report_period": row.get("statDate"),
        "eps_ttm": row.get("epsTTM"),
        "net_profit_ttm": row.get("netProfit"),
        "revenue_ttm": row.get("MBRevenue"),
        "roe": row.get("roeAvg") or row.get("dupontROE"),
        "gross_margin": row.get("gpMargin"),
        "net_margin": row.get("npMargin"),
        "operating_cash_flow": row.get("NOCFToOperatingNI"),
        "debt_ratio": row.get("liabilityToAsset"),
    }


def pause(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)

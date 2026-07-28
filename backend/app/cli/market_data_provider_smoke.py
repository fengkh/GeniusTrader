import argparse
import asyncio
import json
from datetime import date
from typing import Any

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.providers.market_data.models import MarketDataQuery
from app.providers.market_data.registry import (
    get_market_data_provider,
    normalize_market_data_source_code,
)
from app.services.market_data import UNIT_NOTES

AUTHORIZATION_NOTE = "技术可达不代表生产授权；未确认 commercially_authorized 前不得写入或公开展示行情。"


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    provider_code = normalize_market_data_source_code(args.provider)
    symbols = _symbols(args.symbols)[: args.max_records]
    if provider_code == "TUSHARE_PRO" and not settings.market_data_tushare_token.strip():
        _print(
            {
                "status": "not_configured",
                "provider": provider_code,
                "error_code": ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED.value,
                "token": "not_configured",
                "authorization_note": AUTHORIZATION_NOTE,
            }
        )
        return 3
    if args.persist and settings.is_production and settings.market_data_tushare_authorization_status != "commercially_authorized":
        _print(
            {
                "status": "blocked",
                "provider": provider_code,
                "error_code": ErrorCode.MARKET_DATA_PERMISSION_DENIED.value,
                "authorization_status": settings.market_data_tushare_authorization_status,
                "authorization_note": AUTHORIZATION_NOTE,
            }
        )
        return 1

    provider = get_market_data_provider(provider_code, settings)
    if provider is None:
        _print({"status": "failed", "provider": provider_code, "error_code": "PROVIDER_NOT_IMPLEMENTED"})
        return 1
    trade_date = date.fromisoformat(args.date) if args.date else date.today()
    query = MarketDataQuery(
        trade_date=trade_date,
        date_from=trade_date,
        date_to=trade_date,
        symbols=symbols,
        max_records=args.max_records,
        mode="selected_trade_date",
        dry_run=args.dry_run,
    )
    try:
        result = await provider.fetch_daily_snapshots(query)
    except AppError as exc:
        _print(
            {
                "status": "failed",
                "provider": provider_code,
                "error_code": exc.code.value,
                "message": exc.message,
                "token": "configured" if provider_code == "TUSHARE_PRO" else "not_required",
                "authorization_note": AUTHORIZATION_NOTE,
            }
        )
        return 3 if exc.code == ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED else 1
    except Exception as exc:  # noqa: BLE001
        _print({"status": "failed", "provider": provider_code, "error_type": type(exc).__name__})
        return 1

    fields_present = sorted(
        {
            field
            for record in result.records
            for field in [
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "change",
                "pct_change",
                "volume",
                "amount",
                "turnover_rate",
                "total_market_value",
                "circulating_market_value",
            ]
            if getattr(record, field) is not None
        }
    )
    _print(
        {
            "status": result.status.value,
            "provider": provider_code,
            "dry_run": args.dry_run,
            "persist": args.persist,
            "request_count": result.request_count,
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "record_count": len(result.records),
            "coverage_symbols": [record.symbol for record in result.records],
            "fields_present": fields_present,
            "unit_notes": UNIT_NOTES,
            "authorization_status": settings.market_data_tushare_authorization_status
            if provider_code == "TUSHARE_PRO"
            else "not_applicable",
            "authorization_note": AUTHORIZATION_NOTE,
            "errors": result.errors,
        }
    )
    return 0 if result.records else 1


def _symbols(raw: str) -> list[str]:
    values = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return values[:2] if values else ["600519.SH", "000001.SZ"]


def _print(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
    token = get_settings().market_data_tushare_token.strip()
    if token:
        text = text.replace(token, "[redacted]")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a market data provider without persisting by default")
    parser.add_argument("--provider", default="TUSHARE_PRO", help="Provider code, e.g. TUSHARE_PRO")
    parser.add_argument("--symbols", default="600519.SH,000001.SZ", help="Comma-separated symbols; max two by default")
    parser.add_argument("--date", help="Trade date in YYYY-MM-DD; defaults to today for technical smoke")
    parser.add_argument("--max-records", type=int, default=2, choices=[1, 2], help="Maximum symbols/records to request")
    parser.add_argument("--dry-run", action="store_true", help="Run as technical smoke; does not write database records")
    parser.add_argument("--persist", action="store_true", help="Allow persistence only when provider is commercially authorized")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()

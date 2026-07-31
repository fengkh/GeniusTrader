import argparse
import asyncio
from datetime import date
from uuid import UUID

from app.cli._helpers import first_admin_user, print_summary
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError, ErrorCode
from app.services.market_data import start_market_data_sync


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    admin = await first_admin_user()
    if admin is None and not args.dry_run:
        print_summary({"status": "failed", "error_code": "ADMIN_USER_REQUIRED"})
        return 2
    try:
        async with AsyncSessionLocal() as session:
            run_row = await start_market_data_sync(
                session,
                admin_user=admin,
                source_code=args.provider,
                sync_mode="selected_trade_date" if args.date else "latest_completed_trade_day",
                trade_date=date.fromisoformat(args.date) if args.date else None,
                lookback_days=args.lookback,
                stock_ids=_parse_stock_ids(args.stock_ids),
                use_current_watchlist=args.stock_scope == "watchlist",
                dry_run=args.dry_run,
                trigger_type="cli",
                settings=settings,
                request_id="cli",
                max_symbols=args.max_records,
            )
            print_summary(
                {
                    "status": run_row.status,
                    "job_run_id": str(run_row.id),
                    "provider": run_row.source_code,
                    "resolved_trade_date": run_row.resolved_trade_date,
                    "received_count": run_row.received_count,
                    "created_count": run_row.created_count,
                    "updated_count": run_row.updated_count,
                    "unchanged_count": run_row.unchanged_count,
                    "failure_count": run_row.failure_count,
                    "error_code": run_row.error_code,
                }
            )
            return 0 if run_row.status in {"complete", "partial", "data_insufficient"} else 1
    except AppError as exc:
        print_summary({"status": "failed", "error_code": exc.code.value, "message": exc.message})
        return 1 if exc.code != ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED else 3


def _parse_stock_ids(raw: str | None) -> list[UUID]:
    if not raw:
        return []
    return [UUID(item.strip()) for item in raw.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GeniusTrader daily market data snapshots")
    parser.add_argument("--provider", default="BAOSTOCK", help="Market data provider code")
    parser.add_argument("--date", help="Trade date in YYYY-MM-DD")
    parser.add_argument("--lookback", type=int, default=1, help="Backfill lookback days, max configured by backend")
    parser.add_argument(
        "--stock-scope",
        choices=["watchlist", "stock-ids"],
        default="watchlist",
        help="Sync only the admin watchlist by default, or explicit stock ids",
    )
    parser.add_argument("--stock-ids", help="Comma-separated existing stock UUIDs; only used with --stock-scope stock-ids")
    parser.add_argument("--max-records", type=int, default=20, help="Maximum existing stocks to request in this run")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and fetch without writing snapshots")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()

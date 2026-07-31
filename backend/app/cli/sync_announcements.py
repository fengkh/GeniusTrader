import argparse
import asyncio
from datetime import date, timedelta
from uuid import UUID

from app.cli._helpers import first_admin_user, print_summary
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.services.announcement_ingestion import start_announcement_sync_run


async def run(args: argparse.Namespace) -> int:
    admin = await first_admin_user()
    if admin is None:
        print_summary({"status": "failed", "error_code": "ADMIN_USER_REQUIRED"})
        return 2
    try:
        date_to = date.fromisoformat(args.date_to) if args.date_to else date.today()
        date_from = date.fromisoformat(args.date_from) if args.date_from else date_to - timedelta(days=max(args.lookback - 1, 0))
        async with AsyncSessionLocal() as session:
            run_row = await start_announcement_sync_run(
                session,
                user_id=admin.id,
                source_code=args.provider,
                date_from=date_from,
                date_to=date_to,
                stock_ids=_parse_stock_ids(args.stock_ids),
                use_current_watchlist=args.stock_scope == "watchlist",
                settings=get_settings(),
                request_id="cli",
                dry_run=args.dry_run,
                max_records=args.max_records,
            )
            print_summary(
                {
                    "status": run_row.status,
                    "job_run_id": str(run_row.id),
                    "provider": args.provider,
                    "record_count": run_row.record_count,
                    "candidate_count": run_row.candidate_count,
                    "failure_count": run_row.failure_count,
                    "error_code": run_row.error_code,
                    "dry_run": bool(run_row.metrics.get("dry_run")),
                }
            )
            return 0 if run_row.status in {"complete", "partial", "data_insufficient"} else 1
    except AppError as exc:
        print_summary({"status": "failed", "error_code": exc.code.value, "message": exc.message})
        return 1


def _parse_stock_ids(raw: str | None) -> list[UUID]:
    if not raw:
        return []
    return [UUID(item.strip()) for item in raw.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GeniusTrader official announcement candidates")
    parser.add_argument("--provider", default="CNINFO", help="Announcement provider source code")
    parser.add_argument("--date-from", help="Start date in YYYY-MM-DD; defaults to date-to minus lookback")
    parser.add_argument("--date-to", help="End date in YYYY-MM-DD; defaults to today")
    parser.add_argument("--lookback", type=int, default=7, help="Lookback window in days when dates are omitted")
    parser.add_argument(
        "--stock-scope",
        choices=["watchlist", "stock-ids"],
        default="watchlist",
        help="Sync only the admin watchlist by default, or explicit stock ids",
    )
    parser.add_argument("--stock-ids", help="Comma-separated existing stock UUIDs; only used with --stock-scope stock-ids")
    parser.add_argument("--use-current-watchlist", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true", help="Fetch provider data and record a dry-run without candidates")
    parser.add_argument("--max-records", type=int, default=50, help="Maximum provider records to request in this run")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()

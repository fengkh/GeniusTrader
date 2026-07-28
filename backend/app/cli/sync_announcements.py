import argparse
import asyncio
from datetime import date

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
        async with AsyncSessionLocal() as session:
            run_row = await start_announcement_sync_run(
                session,
                user_id=admin.id,
                source_code=args.provider,
                date_from=date.fromisoformat(args.date_from),
                date_to=date.fromisoformat(args.date_to),
                stock_ids=[],
                use_current_watchlist=args.use_current_watchlist,
                settings=get_settings(),
                request_id="cli",
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
                }
            )
            return 0 if run_row.status in {"complete", "partial", "data_insufficient"} else 1
    except AppError as exc:
        print_summary({"status": "failed", "error_code": exc.code.value, "message": exc.message})
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GeniusTrader official announcement candidates")
    parser.add_argument("--provider", default="CNINFO", help="Announcement provider source code")
    parser.add_argument("--date-from", required=True, help="Start date in YYYY-MM-DD")
    parser.add_argument("--date-to", required=True, help="End date in YYYY-MM-DD")
    parser.add_argument("--use-current-watchlist", action="store_true", help="Sync the admin user's watchlist")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()

import argparse
import asyncio

from app.cli._helpers import first_admin_user, print_summary
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.services.security_master import start_security_master_sync


async def run(args: argparse.Namespace) -> int:
    admin = await first_admin_user()
    if admin is None:
        print_summary({"status": "failed", "error_code": "ADMIN_USER_REQUIRED"})
        return 2
    try:
        async with AsyncSessionLocal() as session:
            run_row = await start_security_master_sync(
                session,
                admin_user=admin,
                source_code=args.provider,
                exchanges=args.exchange,
                force=args.force,
                settings=get_settings(),
                request_id="cli",
            )
            print_summary(
                {
                    "status": run_row.status,
                    "job_run_id": str(run_row.id),
                    "provider": run_row.source_code,
                    "received_count": run_row.received_count,
                    "created_count": run_row.created_count,
                    "updated_count": run_row.updated_count,
                    "failure_count": run_row.failure_count,
                    "error_code": run_row.error_code,
                }
            )
            return 0 if run_row.status in {"complete", "partial", "data_insufficient"} else 1
    except AppError as exc:
        print_summary({"status": "failed", "error_code": exc.code.value, "message": exc.message})
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GeniusTrader A-share security master")
    parser.add_argument("--provider", default="SSE_SECURITY_MASTER", help="Security master provider code")
    parser.add_argument("--exchange", action="append", default=[], help="Exchange code; may be provided repeatedly")
    parser.add_argument("--force", action="store_true", help="Force provider sync when supported")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()

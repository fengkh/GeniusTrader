import argparse
import asyncio
from datetime import timedelta

from sqlalchemy import delete

from app.cli._helpers import print_summary
from app.core.database import AsyncSessionLocal
from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.market_data import MarketDataSyncRun
from app.models.security_master import SecurityMasterSyncRun


async def run(args: argparse.Namespace) -> int:
    cutoff = utc_now() - timedelta(days=args.older_than_days)
    targets = [
        ("audit_logs", AuditLog, AuditLog.created_at),
        ("market_data_sync_runs", MarketDataSyncRun, MarketDataSyncRun.created_at),
        ("security_master_sync_runs", SecurityMasterSyncRun, SecurityMasterSyncRun.created_at),
    ]
    counts: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        for name, model, column in targets:
            statement = delete(model).where(column < cutoff)
            if args.dry_run:
                counts[name] = 0
            else:
                result = await session.execute(statement)
                counts[name] = int(result.rowcount or 0)
        if not args.dry_run:
            await session.commit()
    print_summary({"status": "complete", "dry_run": args.dry_run, "cutoff": cutoff, "deleted": counts})
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup old operational rows")
    parser.add_argument("--older-than-days", type=int, default=90)
    parser.add_argument("--execute", action="store_true", help="Actually delete rows; default is dry-run")
    args = parser.parse_args()
    args.dry_run = not args.execute
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()

#!/usr/bin/env sh
set -eu

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required}"

cd backend
DATABASE_URL="$RESTORE_DATABASE_URL" alembic current
DATABASE_URL="$RESTORE_DATABASE_URL" python - <<'PY'
import os

from app.core.database import create_sync_engine_for_settings
from app.core.config import Settings
from sqlalchemy import text

settings = Settings(database_url=os.environ["DATABASE_URL"])
engine = create_sync_engine_for_settings(settings, null_pool=True)
with engine.connect() as connection:
    counts = {
        "users": connection.execute(text("select count(*) from users")).scalar_one(),
        "stocks": connection.execute(text("select count(*) from stocks")).scalar_one(),
        "watchlist_items": connection.execute(text("select count(*) from user_watchlist_items")).scalar_one(),
        "announcement_records": connection.execute(text("select count(*) from announcement_records")).scalar_one(),
        "information_items": connection.execute(text("select count(*) from information_items")).scalar_one(),
        "user_daily_reviews": connection.execute(text("select count(*) from daily_reviews")).scalar_one(),
        "ai_tasks": connection.execute(text("select count(*) from ai_tasks")).scalar_one(),
        "stock_daily_snapshots": connection.execute(text("select count(*) from stock_daily_snapshots")).scalar_one(),
    }
print(counts)
engine.dispose()
PY

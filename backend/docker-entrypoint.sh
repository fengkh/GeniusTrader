#!/usr/bin/env sh
set -eu

if [ -z "${APP_ENCRYPTION_KEYS:-}" ]; then
  echo "APP_ENCRYPTION_KEYS is required" >&2
  exit 2
fi

alembic upgrade head
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

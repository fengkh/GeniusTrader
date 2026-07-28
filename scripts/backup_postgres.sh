#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$BACKUP_DIR/geniustrader-$STAMP.dump"

pg_dump --format=custom --no-owner --no-privileges "$DATABASE_URL" --file "$OUTPUT"
echo "{\"status\":\"complete\",\"backup_file\":\"$OUTPUT\"}"

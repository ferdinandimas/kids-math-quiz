#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/app}"
DATA_DIR="$(dirname "${DB_PATH:-/data/kids-quiz/kids-quiz.sqlite3}")"
DB_PATH="${DB_PATH:-/data/kids-quiz/kids-quiz.sqlite3}"
SEED_DB="${SEED_DB:-$APP_DIR/seed/kids-quiz.sqlite3}"

mkdir -p "$DATA_DIR"

# A Railway volume overlays /data at runtime, so initialize the persistent
# database here rather than relying only on the image layer created at build.
if [ ! -f "$DB_PATH" ]; then
    cp "$SEED_DB" "$DB_PATH"
fi

export DB_PATH
# Migrations never need ADMIN_CLEAR_PASSWORD; the app checks it at startup.
python "$APP_DIR/scripts/migrate.py"

exec "$@"

#!/bin/sh
set -eu

if [ "${APP_ENV:-}" != "production" ]; then
  echo "Refusing preview deployment without APP_ENV=production" >&2
  exit 1
fi
if [ -z "${DATABASE_URL:-}" ] || [ -z "${SESSION_SECRET:-}" ] || [ -z "${ALLOWED_ORIGINS:-}" ]; then
  echo "Missing required DATABASE_URL, SESSION_SECRET or ALLOWED_ORIGINS" >&2
  exit 1
fi

# All mutable preview data lives on the attached Railway volume.
mkdir -p /data/data_store
cd /app/backend
python -m alembic -c alembic.ini upgrade head
cd /app
exec python -m uvicorn agentic_trading.api:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1

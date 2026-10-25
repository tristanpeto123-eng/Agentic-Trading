#!/usr/bin/env bash
set -euo pipefail
# Sprint 0 local-only API: no authentication
exec uvicorn agentic_trading.api:app --host 127.0.0.1 --port 8000

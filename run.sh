#!/usr/bin/env bash
# Convenience launcher for the dashboard.
set -e
cd "$(dirname "$0")"
exec python3 -m uvicorn app.api:app --host 0.0.0.0 --port "${PORT:-8000}"

#!/usr/bin/env bash
# Start the CiteSeal HTTP server (FastAPI wrapper around citeseal.py).
#
# Usage:
#   bash run_server.sh                # default 0.0.0.0:8765
#   PORT=9000 bash run_server.sh
#   CITESEAL_ROOT=/path bash run_server.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$HERE/.."
exec python -m uvicorn server.app:app \
  --host "${CITESEAL_HOST:-0.0.0.0}" \
  --port "${CITESEAL_PORT:-8765}" \
  --app-dir "$HERE"

#!/usr/bin/env bash
# Start the x_media CI HTTP server (FastAPI wrapper around x_media_ci.py).
#
# Usage:
#   bash run_server.sh                # default 0.0.0.0:8765
#   PORT=9000 bash run_server.sh
#   X_MEDIA_CI_ROOT=/path bash run_server.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$HERE/.."
exec python -m uvicorn server.app:app \
  --host "${X_MEDIA_CI_HOST:-0.0.0.0}" \
  --port "${X_MEDIA_CI_PORT:-8765}" \
  --app-dir "$HERE"

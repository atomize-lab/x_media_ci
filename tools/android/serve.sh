#!/usr/bin/env bash
# serve.sh — start a tiny static HTTP server rooted at DIR.
#
# Usage:
#   bash tools/android/serve.sh <dir> [port]
#
# The server binds 0.0.0.0 so phones on the same WiFi can connect.
set -euo pipefail

DIR="${1:-../accounts}"
PORT="${2:-8765}"

if [[ ! -d "$DIR" ]]; then
  echo "ERROR: not a directory: $DIR" >&2
  exit 2
fi

cd "$DIR"

# Pick a server that's almost always available.
if command -v python3 >/dev/null 2>&1; then
  echo "Serving $DIR at http://0.0.0.0:$PORT (python3 -m http.server)"
  exec python3 -m http.server "$PORT" --bind 0.0.0.0
elif command -v py >/dev/null 2>&1; then
  echo "Serving $DIR at http://0.0.0.0:$PORT (py -3 -m http.server)"
  exec py -3 -m http.server "$PORT" --bind 0.0.0.0
elif command -v python >/dev/null 2>&1; then
  echo "Serving $DIR at http://0.0.0.0:$PORT (python -m http.server)"
  exec python -m http.server "$PORT" --bind 0.0.0.0
else
  echo "ERROR: no python interpreter found" >&2
  exit 2
fi

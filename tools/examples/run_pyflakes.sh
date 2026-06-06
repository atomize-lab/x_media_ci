#!/usr/bin/env bash
# Run pyflakes over the bundled scripts.
# Usage:
#   bash examples/run_pyflakes.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
exec python x_media_ci.py lint

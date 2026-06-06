#!/usr/bin/env bash
# Validate tweet.json files under the accounts root.
#
# Usage:
#   bash examples/run_validate.sh                       # uses ../accounts
#   bash examples/run_validate.sh /path/to/accounts     # custom root
#   bash examples/run_validate.sh /path/to/accounts --strict
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TARGET="${1:-$ROOT/../accounts}"
shift || true

cd "$ROOT"
exec python x_media_ci.py validate --root "$TARGET" "$@"

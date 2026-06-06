#!/usr/bin/env bash
# adb_sync.sh — push / pull the x_media CI tree to/from a connected Android device.
#
# Usage:
#   bash tools/android/adb_sync.sh push <local_path> <android_path>
#   bash tools/android/adb_sync.sh pull <android_path> <local_path>
#   bash tools/android/adb_sync.sh reverse <port>     # adb reverse tcp:PORT tcp:PORT
#   bash tools/android/adb_sync.sh devices
#
# Notes:
# * /sdcard paths are exposed to user-level file managers; safer than
#   trying to write into app-private directories without root.
# * We always use --no-clobber on push so we don't trample newer copies.
set -euo pipefail

if ! command -v adb >/dev/null 2>&1; then
  echo "ERROR: adb not found. Install Android platform-tools first." >&2
  exit 2
fi

OP="${1:-}"
shift || true

case "$OP" in
  push)
    SRC="${1:-}"; DST="${2:-}"
    [[ -z "$SRC" || -z "$DST" ]] && { echo "Usage: $0 push <local> <android>" >&2; exit 2; }
    adb push "$SRC" "$DST"
    ;;
  pull)
    SRC="${1:-}"; DST="${2:-}"
    [[ -z "$SRC" || -z "$DST" ]] && { echo "Usage: $0 pull <android> <local>" >&2; exit 2; }
    adb pull "$SRC" "$DST"
    ;;
  reverse)
    PORT="${1:-8765}"
    adb reverse "tcp:$PORT" "tcp:$PORT"
    echo "Phone can now reach PC at http://127.0.0.1:$PORT/ (while USB is connected)"
    ;;
  devices)
    adb devices -l
    ;;
  *)
    sed -n '2,12p' "$0"
    exit 2
    ;;
esac

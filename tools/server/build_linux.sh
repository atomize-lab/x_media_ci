#!/usr/bin/env bash
# Build a portable, self-contained Linux tarball for the x_media CI server.
#
# Why not PyInstaller on Linux? On Ubuntu 22 + glibc 2.35, PyInstaller's
# bootloader has to be rebuilt for the target ABI, and the resulting
# binary is still ~30 MB. A 100% pure-Python venv on the other hand is
# small, debuggable, and runs on any glibc >= 2.31.
#
# Output:
#   dist/x_media_ci_server-linux-x64.tar.gz
#
# Usage:
#   bash tools/server/build_linux.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$(cd "$HERE/.." && pwd)"
DIST="$TOOLS/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

NAME="x_media_ci_server-linux-x64"
ROOT="$STAGE/$NAME"
mkdir -p "$ROOT/bin" "$ROOT/venv" "$ROOT/scripts"

echo "[1/5] Copying source..."
cp -r "$TOOLS/server"            "$ROOT/server"
cp -r "$TOOLS/scripts"           "$ROOT/scripts"
cp    "$TOOLS/x_media_ci.py"     "$ROOT/"
cp    "$TOOLS/requirements.txt"  "$ROOT/"
cp    "$TOOLS/server/requirements.txt" "$ROOT/server-requirements.txt"

echo "[2/5] Building venv..."
python3 -m venv "$ROOT/venv"
# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate"
pip install --upgrade pip --quiet
pip install -r "$ROOT/requirements.txt"        --quiet
pip install -r "$ROOT/server-requirements.txt" --quiet

echo "[3/5] Writing run script..."
cat > "$ROOT/bin/run.sh" <<'SH'
#!/usr/bin/env bash
# Start the x_media CI server. Override X_MEDIA_CI_ROOT if your
# accounts/ tree lives somewhere else.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
export X_MEDIA_CI_HOST="${X_MEDIA_CI_HOST:-0.0.0.0}"
export X_MEDIA_CI_PORT="${X_MEDIA_CI_PORT:-8765}"
export X_MEDIA_CI_ROOT="${X_MEDIA_CI_ROOT:-$ROOT/accounts}"
exec "$ROOT/venv/bin/python" "$ROOT/x_media_ci_server.py" --host "$X_MEDIA_CI_HOST" --port "$X_MEDIA_CI_PORT"
SH
chmod +x "$ROOT/bin/run.sh"

# Drop a tiny shim that points at uvicorn via the venv's python.
cat > "$ROOT/x_media_ci_server.py" <<'PY'
"""Entry point used by the bundled run.sh."""
import os
import uvicorn
from server.app import app

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("X_MEDIA_CI_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int,
                   default=int(os.environ.get("X_MEDIA_CI_PORT", "8765")))
    args = p.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
PY

echo "[4/5] Writing README + .env.example..."
cat > "$ROOT/README.txt" <<'TXT'
x_media CI server — Linux x64 portable
=====================================

Quick start:

    tar -xzf x_media_ci_server-linux-x64.tar.gz
    cd x_media_ci_server-linux-x64
    X_MEDIA_CI_ROOT=/path/to/your/accounts ./bin/run.sh

Then open http://localhost:8765/docs for the Swagger UI.

Environment variables:

    X_MEDIA_CI_HOST  bind host (default 0.0.0.0)
    X_MEDIA_CI_PORT  bind port (default 8765)
    X_MEDIA_CI_ROOT  path to your accounts/ tree
TXT

echo "[5/5] Tarball..."
mkdir -p "$DIST"
TARBALL="$DIST/$NAME.tar.gz"
tar -czf "$TARBALL" -C "$STAGE" "$NAME"
echo "Done: $TARBALL"
ls -lh "$TARBALL"

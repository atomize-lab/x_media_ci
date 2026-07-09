#!/usr/bin/env bash
# Build a portable, self-contained Linux tarball for the CiteSeal server.
#
# Why not PyInstaller on Linux? On Ubuntu 22 + glibc 2.35, PyInstaller's
# bootloader has to be rebuilt for the target ABI, and the resulting
# binary is still ~30 MB. A 100% pure-Python venv on the other hand is
# small, debuggable, and runs on any glibc >= 2.31.
#
# Output:
#   dist/citeseal_server-linux-x64.tar.gz
#
# Usage:
#   bash tools/server/build_linux.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$(cd "$HERE/.." && pwd)"
DIST="$TOOLS/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

NAME="citeseal_server-linux-x64"
ROOT="$STAGE/$NAME"
mkdir -p "$ROOT/bin" "$ROOT/venv" "$ROOT/scripts"

echo "[1/5] Copying source..."
cp -r "$TOOLS/server"            "$ROOT/server"
cp -r "$TOOLS/scripts"           "$ROOT/scripts"
cp    "$TOOLS/citeseal.py"     "$ROOT/"
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
# Start the CiteSeal server. Override CITESEAL_ROOT if your
# accounts/ tree lives somewhere else.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
export CITESEAL_HOST="${CITESEAL_HOST:-0.0.0.0}"
export CITESEAL_PORT="${CITESEAL_PORT:-8765}"
export CITESEAL_ROOT="${CITESEAL_ROOT:-$ROOT/accounts}"
exec "$ROOT/venv/bin/python" "$ROOT/citeseal_server.py" --host "$CITESEAL_HOST" --port "$CITESEAL_PORT"
SH
chmod +x "$ROOT/bin/run.sh"

# Drop a tiny shim that points at uvicorn via the venv's python.
cat > "$ROOT/citeseal_server.py" <<'PY'
"""Entry point used by the bundled run.sh."""
import os
import uvicorn
from server.app import app

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("CITESEAL_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int,
                   default=int(os.environ.get("CITESEAL_PORT", "8765")))
    args = p.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
PY

echo "[4/5] Writing README + .env.example..."
cat > "$ROOT/README.txt" <<'TXT'
CiteSeal server — Linux x64 portable
=====================================

Quick start:

    tar -xzf citeseal_server-linux-x64.tar.gz
    cd citeseal_server-linux-x64
    CITESEAL_ROOT=/path/to/your/accounts ./bin/run.sh

Then open http://localhost:8765/docs for the Swagger UI.

Environment variables:

    CITESEAL_HOST  bind host (default 0.0.0.0)
    CITESEAL_PORT  bind port (default 8765)
    CITESEAL_ROOT  path to your accounts/ tree
TXT

echo "[5/5] Tarball..."
mkdir -p "$DIST"
TARBALL="$DIST/$NAME.tar.gz"
tar -czf "$TARBALL" -C "$STAGE" "$NAME"
echo "Done: $TARBALL"
ls -lh "$TARBALL"

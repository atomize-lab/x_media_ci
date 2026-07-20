#!/usr/bin/env bash
# Build a self-contained Linux x64 tarball for the CiteSeal server.
#
# The release payload contains a PyInstaller-frozen executable rather than a
# Python virtual environment. Virtual environments contain host-specific
# interpreter symlinks and are not relocatable across machines.
#
# Output:
#   tools/dist/citeseal_server-linux-x64.tar.gz
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
BUILD_VENV="$STAGE/build-venv"
BUILD_DIST="$STAGE/pyinstaller-dist"
BUILD_WORK="$STAGE/pyinstaller-work"
TARBALL="$DIST/$NAME.tar.gz"

mkdir -p "$ROOT/bin" "$BUILD_DIST" "$BUILD_WORK" "$DIST"

printf '%s\n' '[1/5] Preparing isolated build environment...'
if command -v uv >/dev/null 2>&1; then
  uv venv --seed --python python3 "$BUILD_VENV"
else
  python3 -m venv "$BUILD_VENV"
fi
"$BUILD_VENV/bin/python" -m pip install --upgrade pip --quiet
"$BUILD_VENV/bin/python" -m pip install \
  -r "$TOOLS/requirements.txt" \
  -r "$HERE/requirements.txt" \
  'pyinstaller>=6.0,<7.0' \
  --quiet

printf '%s\n' '[2/5] Freezing server executable...'
"$BUILD_VENV/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$BUILD_DIST" \
  --workpath "$BUILD_WORK" \
  "$HERE/citeseal_server.spec"

if [[ ! -x "$BUILD_DIST/citeseal_server" ]]; then
  printf 'ERROR: frozen executable missing: %s\n' \
    "$BUILD_DIST/citeseal_server" >&2
  exit 1
fi

printf '%s\n' '[3/5] Staging portable payload...'
install -m 0755 \
  "$BUILD_DIST/citeseal_server" \
  "$ROOT/bin/citeseal_server"

cat > "$ROOT/bin/run.sh" <<'SH'
#!/usr/bin/env bash
# Start the self-contained CiteSeal server. No system Python is required.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
export CITESEAL_HOST="${CITESEAL_HOST:-0.0.0.0}"
export CITESEAL_PORT="${CITESEAL_PORT:-8765}"
export CITESEAL_ROOT="${CITESEAL_ROOT:-$ROOT/accounts}"
mkdir -p "$CITESEAL_ROOT"
exec "$HERE/citeseal_server"
SH
chmod 0755 "$ROOT/bin/run.sh"

cat > "$ROOT/README.txt" <<'TXT'
CiteSeal server — Linux x64 self-contained bundle
=================================================

No system Python installation is required.

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

cat > "$ROOT/.env.example" <<'ENV'
CITESEAL_HOST=0.0.0.0
CITESEAL_PORT=8765
CITESEAL_ROOT=./accounts
ENV

printf '%s\n' '[4/5] Creating tarball...'
rm -f "$TARBALL"
tar -czf "$TARBALL" -C "$STAGE" "$NAME"

printf '%s\n' '[5/5] Verifying tarball contract...'
"$BUILD_VENV/bin/python" "$HERE/verify_linux_tarball.py" "$TARBALL"
printf 'Done: %s\n' "$TARBALL"
ls -lh "$TARBALL"

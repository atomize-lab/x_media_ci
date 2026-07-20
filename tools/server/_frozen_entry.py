"""PyInstaller entry point for the self-contained CiteSeal server.

The frozen executable has two modes:

* default: start the FastAPI/Uvicorn server;
* ``--citeseal-cli``: run the bundled CiteSeal CLI in the same embedded
  Python runtime. The server uses this private mode for background jobs, so a
  host Python installation is not required.
"""
from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Sequence

FROZEN_CLI_FLAG = "--citeseal-cli"


def _wire_log_file() -> None:
    """When frozen, also tee server stdout/stderr to a file next to the exe."""
    if not getattr(sys, "frozen", False):
        return
    log_path = os.path.join(
        os.path.dirname(sys.executable), "citeseal_server.log"
    )
    log_fp = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.stdout, log_fp)
    sys.stderr = _Tee(sys.stderr, log_fp)
    print(f"[citeseal_server] logging to {log_path}", flush=True)


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for stream in self._streams:
            try:
                stream.write(s)
            except Exception:
                pass

    def flush(self):
        for stream in self._streams:
            try:
                stream.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def _ensure_runtime_paths() -> None:
    """Expose bundled data modules to both server and embedded CLI modes."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend([meipass, os.path.join(meipass, "scripts")])
    else:
        tools_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.extend([tools_root, os.path.join(tools_root, "scripts")])
    for candidate in reversed(candidates):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


def _run_embedded_cli(argv: Sequence[str]) -> int:
    _ensure_runtime_paths()
    citeseal_module = importlib.import_module("citeseal")
    return int(citeseal_module.main(argv) or 0)


def _run_server() -> None:
    _ensure_runtime_paths()
    _wire_log_file()
    from app import app
    import uvicorn

    host = os.environ.get("CITESEAL_HOST", "0.0.0.0")
    # Use 18765 (not 8765) to reduce collisions on a fresh install.
    port = int(os.environ.get("CITESEAL_PORT", "18765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == [FROZEN_CLI_FLAG]:
        return _run_embedded_cli(argv[1:])
    _run_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

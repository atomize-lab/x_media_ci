"""PyInstaller entry point for the CiteSeal server.

This file is **only** used by PyInstaller. The runtime entry point is
``app:app`` (the FastAPI instance). We import the FastAPI app eagerly
so PyInstaller picks it up, then start uvicorn programmatically so the
frozen binary doesn't need an external ``uvicorn`` CLI to be on PATH.

Run locally (without PyInstaller):

    python server/_frozen_entry.py

Build a single-file Windows executable:

    pyinstaller --noconfirm --clean server/citeseal_server.spec
"""
from __future__ import annotations

import os
import sys


def _wire_log_file() -> None:
    """When frozen, also tee stdout/stderr to a log file next to the exe."""
    if not getattr(sys, "frozen", False):
        return
    log_path = os.path.join(os.path.dirname(sys.executable),
                            "citeseal_server.log")
    log_fp = open(log_path, "a", encoding="utf-8", buffering=1)
    # Replace stdout/stderr so uvicorn's prints are captured too.
    sys.stdout = _Tee(sys.stdout, log_fp)
    sys.stderr = _Tee(sys.stderr, log_fp)
    print(f"[citeseal_server] logging to {log_path}", flush=True)


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
            except Exception:
                pass

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self):
        return False


# Import the FastAPI app; must happen after sys.path is set up by
# PyInstaller's bootloader (which adds the frozen dir to sys.path).
from app import app  # noqa: E402


def main() -> None:
    _wire_log_file()
    import uvicorn
    host = os.environ.get("CITESEAL_HOST", "0.0.0.0")
    # Use 18765 (not 8765) to reduce the chance of colliding with other
    # services on a fresh Windows install. Override with CITESEAL_PORT.
    port = int(os.environ.get("CITESEAL_PORT", "18765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

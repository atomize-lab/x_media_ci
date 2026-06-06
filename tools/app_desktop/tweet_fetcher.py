"""Tweet fetcher used by the desktop GUI.

The GUI does **not** talk to X directly. Instead it shells out to
``x_media_ci.py`` and treats the existing on-disk ``tweet.json`` plus
``media/`` tree as the source of truth. This keeps the GUI in lock-step
with every other consumer (CLI, FastAPI server, Flutter app).

Strategy:
  1. The user pastes a tweet URL.
  2. We try ``x_media_ci.py`` which currently expects a local
     ``tweet_dir`` (a folder already populated by your existing pipeline).
     If only a URL is given, we run a small helper that maps the URL to
     an expected ``tweet_dir`` path and lets the user pick/create it.
  3. "Save" buttons run the corresponding ``x_media_ci`` sub-command
     (``md``, ``pdf``, ``transcode``) on that directory and stream
     progress back via a callback.

This module is intentionally tiny so it can be bundled by PyInstaller
without bringing in FastAPI / Uvicorn / Pydantic.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse


# Regex for a tweet URL — used to derive handle / id.
_TWEET_URL_RE = re.compile(
    r"^https?://(www\.)?(x\.com|twitter\.com)/([^/]+)/status/(\d+)",
    re.IGNORECASE,
)


@dataclass
class TweetRef:
    url: str
    handle: str = ""
    tweet_id: str = ""
    tweet_dir: Optional[Path] = None
    note: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(self.handle and self.tweet_id)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "handle": self.handle,
            "tweet_id": self.tweet_id,
            "tweet_dir": str(self.tweet_dir) if self.tweet_dir else "",
            "note": self.note,
        }


def parse_tweet_url(url: str) -> TweetRef:
    """Extract handle / id from a tweet URL. Returns an invalid ref on failure."""
    ref = TweetRef(url=url.strip())
    if not ref.url:
        return ref
    m = _TWEET_URL_RE.match(ref.url)
    if not m:
        # try to be forgiving: pull the last path segment as id
        u = urlparse(ref.url)
        parts = [p for p in u.path.split("/") if p]
        if parts and parts[-1].isdigit():
            ref.tweet_id = parts[-1]
            if len(parts) >= 2:
                ref.handle = parts[-2]
        return ref
    ref.handle = m.group(3)
    ref.tweet_id = m.group(4)
    return ref


def locate_tweet_dir(ref: TweetRef, save_root: Path) -> Optional[Path]:
    """Walk ``save_root`` looking for a directory whose name ends with
    ``_<tweet_id>`` and pick the first match (any handle)."""
    if not ref.is_valid:
        return None
    if not save_root or not save_root.exists():
        return None
    suffix = f"_{ref.tweet_id}"
    for p in save_root.rglob("*" + suffix):
        if p.is_dir():
            return p
    return None


def guess_tweet_dir(ref: TweetRef, save_root: Path) -> Path:
    """Build the conventional CI path for a tweet, even if it doesn't exist yet.

    Path:
        <save_root>/<handle>/tweets/YYYY/YYYY-MM/<UTC-stamp>_<tweet_id>
    The UTC stamp is derived from the current time so the user can re-run
    and overwrite safely. If the directory does not exist, the user is
    expected to populate it (or the GUI runs the helper commands).
    """
    now = time.gmtime()
    yyyy = time.strftime("%Y", now)
    ym = time.strftime("%Y-%m", now)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", now)
    return save_root / ref.handle / "tweets" / yyyy / ym / f"{stamp}_{ref.tweet_id}"


# ---------------------------------------------------------------------------
# Running x_media_ci as a subprocess
# ---------------------------------------------------------------------------

ProgressCB = Callable[[str, float], None]   # (line, fraction 0..1)


@dataclass
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str = ""


def _tools_dir() -> Path:
    """Resolve <tools> directory whether running as script or frozen exe.

    Frozen layout (PyInstaller --onedir):
        <exedir>/x_media_ci_app.exe
        <exedir>/x_media_ci.py
        <exedir>/fetch_tweet.py
        <exedir>/fetch_x.py
        <exedir>/scripts/...
    The data files (x_media_ci.py etc.) are dropped at the top level
    alongside the exe by COLLECT.

    Script layout (python tools/app_desktop/tweet_gui.py):
        tools/app_desktop/tweet_fetcher.py   <- this file
        tools/x_media_ci.py
        tools/fetch_tweet.py
    so parent.parent == tools/.
    """
    frozen = getattr(sys, "frozen", False)
    if frozen:
        exe_dir = Path(sys.executable).resolve().parent
        # With --onedir, both layouts are common:
        for cand in (
            exe_dir,
            exe_dir / "_internal",
            Path(getattr(sys, "_MEIPASS", exe_dir)),
        ):
            if (cand / "x_media_ci.py").is_file():
                return cand
        return exe_dir
    return Path(__file__).resolve().parent.parent  # app_desktop/ -> tools/


def _x_media_ci_py() -> Path:
    return _tools_dir() / "x_media_ci.py"


def _python_exe() -> str:
    if getattr(sys, "frozen", False):
        # The frozen exe cannot be re-spawned as a regular python, so
        # delegate to the system Python that the user (presumably) has.
        import shutil
        for cand in ("py", "python", "python3"):
            p = shutil.which(cand)
            if p:
                return p
        return sys.executable
    return sys.executable or "python"


def run_x_media_ci(op: str, args: list[str], *,
                   cwd: Optional[Path] = None,
                   on_line: Optional[ProgressCB] = None) -> RunResult:
    """Run ``python x_media_ci.py <op> <args>`` and stream stdout/stderr.

    ``on_line`` is called for each new line (text only). The fraction is
    0..1 (best effort; 0/1 from each child process).
    """
    ci_py = _x_media_ci_py()
    if not ci_py.is_file():
        return RunResult(returncode=127, error=f"x_media_ci.py not found: {ci_py}")
    cmd = [_python_exe(), str(ci_py), op, *args]
    return _run_streaming(cmd, cwd=cwd, on_line=on_line)


def _run_streaming(cmd: list[str], *,
                   cwd: Optional[Path] = None,
                   env: Optional[dict[str, str]] = None,
                   on_line: Optional[ProgressCB] = None) -> RunResult:
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as e:
        return RunResult(returncode=127, error=f"executable not found: {e}")
    except NotADirectoryError as e:
        return RunResult(
            returncode=1,
            error=(
                f"working directory is not a real directory: {cwd!r}. "
                f"Create it (or let the app create it) first. "
                f"({type(e).__name__}: {e})"
            ),
        )
    except PermissionError as e:
        return RunResult(
            returncode=1,
            error=f"permission denied while spawning: {e}",
        )
    except OSError as e:
        return RunResult(
            returncode=1,
            error=f"{type(e).__name__} while spawning: {e}",
        )
    except Exception as e:
        return RunResult(returncode=1, error=f"{type(e).__name__}: {e}")

    out_lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        out_lines.append(line)
        if on_line:
            try:
                on_line(line.rstrip("\n"), 0.5)
            except Exception:
                pass
    proc.wait()
    return RunResult(
        returncode=proc.returncode or 0,
        stdout="".join(out_lines),
    )


# ---------------------------------------------------------------------------
# High-level "actions" invoked by the GUI buttons
# ---------------------------------------------------------------------------

def action_fetch(url: str, save_root: Path, *,
                 on_line: Optional[ProgressCB] = None,
                 ci_root: Optional[Path] = None,
                 headed: bool = False,
                 user_data_dir: Optional[Path] = None,
                 auth_token: str = "",
                 ct0: str = "",
                 browser_channel: str = "",
                 skip_fetch: bool = False) -> tuple[TweetRef, RunResult]:
    """Locate the tweet dir for a URL. If not found, **really** fetch it
    via the bundled ``fetch_tweet.py`` (Playwright-based scraper that
    downloads media and writes the CI-shaped folder).

    Strategy:
      1. Parse URL.
      2. Look for an existing tweet_dir under ``save_root``.
      3. If ``skip_fetch`` is True: do NOT call the scraper; just create
         a CI-shaped skeleton (useful for offline / testing).
      4. If not found and not skipping, run
         ``python fetch_tweet.py <url> --out <tweet_dir>`` (which
         delegates to ``tools/fetch_x.py``). The scraper downloads
         images / mp4 / m3u8→mp4 and writes ``tweet.json``.
      5. Then run ``x_media_ci fix --apply`` to normalize the result
         and ``validate`` to surface any issues.
    """
    ref = parse_tweet_url(url)
    if not ref.is_valid:
        return ref, RunResult(returncode=2, error="Could not parse tweet URL")

    on_line and on_line(f"[fetch] parsed handle={ref.handle} id={ref.tweet_id}", 0.1)

    existing = locate_tweet_dir(ref, save_root)
    if existing:
        ref.tweet_dir = existing
        on_line and on_line(f"[fetch] found existing dir: {existing}", 0.3)
        rr = run_x_media_ci("validate", [str(existing)],
                            cwd=existing, on_line=on_line)
        return ref, rr

    # Not found locally.
    target = guess_tweet_dir(ref, save_root)
    ref.tweet_dir = target

    # Make sure the parent dir exists *before* we hand it to Popen
    # as `cwd`. Otherwise Windows raises NotADirectoryError
    # (WinError 267) when the leaf doesn't exist yet.
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return ref, RunResult(
            returncode=1,
            error=f"Cannot create tweet parent dir {target.parent}: {type(e).__name__}: {e}",
        )

    if skip_fetch:
        on_line and on_line(
            "[fetch] 'Local only' is on — creating a CI-shaped skeleton "
            "without contacting x.com. Click Fetch again with 'Local only' "
            "off to actually download media.", "dim",
        )
        _create_skeleton(target, ref)
        on_line and on_line(f"[fetch] skeleton: {target}", 0.9)
        return ref, RunResult(returncode=0, stdout="(skeleton)\n")

    # Real fetch path.
    fetch_tweet_py = _tools_dir() / "fetch_tweet.py"
    fetch_x_py     = _tools_dir() / "fetch_x.py"
    if fetch_tweet_py.is_file():
        cmd = [_python_exe(), str(fetch_tweet_py), url, "--out", str(target)]
        if ci_root:
            cmd += ["--ci-root", str(ci_root)]
        if headed:
            cmd.append("--headed")
        if user_data_dir:
            cmd += ["--user-data-dir", str(user_data_dir)]
        on_line and on_line(f"[fetch] delegating to: {fetch_tweet_py.name}", 0.4)
        env = os.environ.copy()
        if auth_token:
            env["X_AUTH_TOKEN"] = auth_token
        if ct0:
            env["X_CT0"] = ct0
        if browser_channel:
            env["X_BROWSER_CHANNEL"] = browser_channel
        rr = _run_streaming(cmd, cwd=target.parent, env=env, on_line=on_line)
    elif fetch_x_py.is_file():
        cmd = [_python_exe(), str(fetch_x_py),
               "url", "--url", url, "--out", str(target)]
        if ci_root:
            cmd += ["--ci-root", str(ci_root)]
        if headed:
            cmd.append("--headed")
        if user_data_dir:
            cmd += ["--user-data-dir", str(user_data_dir)]
        on_line and on_line(f"[fetch] delegating to: {fetch_x_py.name}", 0.4)
        rr = _run_streaming(cmd, cwd=target.parent, on_line=on_line)
    else:
        on_line and on_line("[fetch] no fetch_tweet.py / fetch_x.py found", "err")
        _create_skeleton(target, ref)
        return ref, RunResult(
            returncode=127,
            error="No fetch_tweet.py / fetch_x.py found in tools/. Skeleton created.",
        )

    if rr.returncode != 0:
        on_line and on_line(f"[fetch] scraper rc={rr.returncode}", "err")
        return ref, rr

    on_line and on_line("[fetch] scraper succeeded; running fix", 0.9)
    fix = run_x_media_ci("fix", [str(target), "--apply"],
                         cwd=target, on_line=on_line)
    on_line and on_line(f"[fetch] fix rc={fix.returncode}", 1.0)
    return ref, RunResult(returncode=0, stdout=rr.stdout + fix.stdout)


def _resolve_fetcher(save_root: Path) -> Optional[Path]:
    """Find a user-provided tweet fetcher script.

    Lookup order:
      1. ``$X_MEDIA_FETCHER`` env var (absolute path)
      2. ``<save_root>/../tools/fetch_tweet.py``  (the conventional
         location if you keep your existing Solo scraper there)
      3. ``<save_root>/../fetch_tweet.py``
      4. ``~/Documents/Solo/fetch_tweet.py``      (Windows default)
    """
    env = os.environ.get("X_MEDIA_FETCHER")
    if env and Path(env).is_file():
        return Path(env)
    candidates = [
        save_root.parent / "tools" / "fetch_tweet.py",
        save_root.parent / "fetch_tweet.py",
        Path.home() / "Documents" / "Solo" / "fetch_tweet.py",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _create_skeleton(target: Path, ref: TweetRef) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for sub in ("images", "video", "audio", "raw"):
        (target / "media" / sub).mkdir(parents=True, exist_ok=True)
    (target / "exports").mkdir(parents=True, exist_ok=True)
    placeholder = {
        "tweet_id": ref.tweet_id,
        "tweet_url": ref.url,
        "author_handle": ref.handle,
        "datetime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "text": "",
        "media": [],
        "exports": [],
        "_note": "auto-created by the desktop app; populate media[] and re-run 'Fetch'",
    }
    (target / "tweet.json").write_text(
        json.dumps(placeholder, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def action_save_md(ref: TweetRef, *, on_line: Optional[ProgressCB] = None) -> RunResult:
    if not ref.tweet_dir:
        return RunResult(returncode=2, error="No tweet_dir; run 'Fetch' first")
    return run_x_media_ci("md",
                          ["--tweet-dir", str(ref.tweet_dir), "--force"],
                          cwd=ref.tweet_dir, on_line=on_line)


def action_save_pdf(ref: TweetRef, *, on_line: Optional[ProgressCB] = None) -> RunResult:
    if not ref.tweet_dir:
        return RunResult(returncode=2, error="No tweet_dir; run 'Fetch' first")
    return run_x_media_ci("pdf",
                          ["--tweet-dir", str(ref.tweet_dir), "--force"],
                          cwd=ref.tweet_dir, on_line=on_line)


def action_save_media(ref: TweetRef, *,
                      on_line: Optional[ProgressCB] = None,
                      also_transcode: bool = True) -> RunResult:
    if not ref.tweet_dir:
        return RunResult(returncode=2, error="No tweet_dir; run 'Fetch' first")
    if also_transcode:
        return run_x_media_ci("transcode",
                              ["--tweet-dir", str(ref.tweet_dir), "--force",
                               "--apply"],
                              cwd=ref.tweet_dir, on_line=on_line)
    # Just run fix + validate; media itself is presumed to be in place
    return run_x_media_ci("fix",
                          ["--root", str(ref.tweet_dir.parent.parent.parent.parent
                                          if ref.tweet_dir else "."), "--apply"],
                          cwd=ref.tweet_dir, on_line=on_line)


def action_save_all(ref: TweetRef, *,
                    on_line: Optional[ProgressCB] = None) -> RunResult:
    """Convenience: md + pdf + transcode in one shot."""
    if not ref.tweet_dir:
        return RunResult(returncode=2, error="No tweet_dir; run 'Fetch' first")
    return run_x_media_ci("all",
                          ["--tweet-dir", str(ref.tweet_dir),
                           "--keep-going", "--force", "--with-ocr"],
                          cwd=ref.tweet_dir, on_line=on_line)


# ---------------------------------------------------------------------------
# Environment check
# ---------------------------------------------------------------------------

def check_setup(*, on_line: Optional[ProgressCB] = None) -> RunResult:
    """Probe the system Python for the deps the fetcher needs.

    Reports:
      - which `python` will be used
      - whether `playwright` is importable
      - whether the chromium browser binary is installed
      - whether ffmpeg is on PATH (for transcoding HLS)

    Returns rc=0 if everything is fine, rc=10/11/12 if a dep is missing.
    """
    py = _python_exe()
    on_line and on_line(f"[check] python: {py}", 0.1)

    probe = (
        "import sys, json, shutil, importlib\n"
        "out = {'python': sys.executable, 'version': sys.version.split()[0]}\n"
        "try:\n"
        "    import playwright; out['playwright'] = getattr(playwright, '__version__', 'present')\n"
        "except Exception as e:\n"
        "    out['playwright'] = 'MISSING: ' + repr(e)\n"
        "try:\n"
        "    from playwright.sync_api import sync_playwright\n"
        "    with sync_playwright() as p:\n"
        "        try:\n"
        "            out['chromium'] = p.chromium.executable_path\n"
        "        except Exception as e:\n"
        "            out['chromium'] = 'MISSING: ' + repr(e)\n"
        "except Exception as e:\n"
        "    out['chromium'] = '(skipped: ' + repr(e) + ')'\n"
        "out['ffmpeg'] = shutil.which('ffmpeg') or 'MISSING'\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
    )
    cmd = [py, "-c", probe]
    return _run_streaming(cmd, on_line=on_line)

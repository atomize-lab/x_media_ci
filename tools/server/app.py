"""FastAPI wrapper around the x_media CI CLI.

This server does **not** re-implement any of the existing logic. It
simply exposes the same operations via JSON so that the Flutter app
(Win11 / Ubuntu22 / Android 14+) can drive them.

Run:

    uvicorn app:app --host 0.0.0.0 --port 8765

Endpoints (all JSON unless noted):

    GET  /api/health
    GET  /api/accounts                       -> list of {handle, tweet_count}
    GET  /api/accounts/{handle}              -> {handle, months: [{year,month,count}]}
    GET  /api/tweet                          -> list of tweet ids (paginated)
    GET  /api/tweet/{tweet_id}               -> full tweet.json + media list
    PUT  /api/tweet/{tweet_id}               -> write back a new tweet.json
    POST /api/run                            -> trigger md|pdf|ocr|all|fix|transcode
    GET  /api/jobs/{job_id}                  -> poll job status / result
    GET  /media/{handle}/{tweet_id}/{path}   -> serve local media files

The CI root is auto-discovered relative to this file, but can be
overridden with the X_MEDIA_CI_ROOT env var.
"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Make the bundled scripts package importable so we can reuse helpers.
# We need to handle two cases:
#   * dev mode: scripts/ lives next to server/ at <tools>/scripts/
#   * frozen mode (PyInstaller): PyInstaller unpacks bundled data into
#     sys._MEIPASS, and the .spec lists scripts/ as a data folder
#     (datas=[(scripts_pkg, "scripts")]). At runtime that folder is
#     available at sys._MEIPASS/scripts/ on disk, so the same lookup
#     path works if we add sys._MEIPASS to sys.path.
import sys as _sys
_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent
_SCRIPTS = _TOOLS / "scripts"
_MEIPASS = getattr(_sys, "_MEIPASS", None)
if _MEIPASS:
    _MEIPASS_scripts = Path(_MEIPASS) / "scripts"
    if _MEIPASS_scripts.is_dir() and str(_MEIPASS_scripts) not in _sys.path:
        _sys.path.insert(0, str(_MEIPASS_scripts))
if _SCRIPTS.is_dir() and str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))

# Reuse the same helpers as the CLI for path conventions.
from ci_common import (  # noqa: E402
    find_tweet_dirs,
    is_tweet_dir,
    load_tweet_meta,
    tweet_paths,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CI_ROOT = Path(os.environ.get("X_MEDIA_CI_ROOT")
               or (_TOOLS / ".." / "accounts")).resolve()
# When running frozen via PyInstaller, ``_TOOLS`` is the unpacked
# bootloader dir, so ``_TOOLS / ".." / "accounts"`` points to nonsense
# (usually under %TEMP%). In that case, default to ``<exe_dir>/accounts``
# which is the most natural drop-in location.
if (not CI_ROOT.is_dir()) and getattr(sys, "frozen", False):
    alt = Path(sys.executable).resolve().parent / "accounts"
    if alt.is_dir():
        CI_ROOT = alt
    else:
        CI_ROOT = alt  # even if missing, keep the sane default for the error


def _resolve_python() -> str:
    """Pick the interpreter used to spawn ``x_media_ci.py``.

    In dev mode, ``sys.executable`` is the active Python — perfect.
    In PyInstaller-frozen mode, ``sys.executable`` is the frozen
    server itself, so re-spawning it would just start a second
    server. Fall back to ``py -3`` (the Windows launcher) or
    ``python3`` on POSIX.
    """
    if not getattr(sys, "frozen", False):
        return sys.executable or "python"
    import shutil
    for cand in ("py", "python", "python3", "python3.11", "python3.12"):
        p = shutil.which(cand)
        if p:
            return p
    return sys.executable  # last resort; will likely fail clearly


PYTHON = _resolve_python()

# Locate x_media_ci.py. In dev mode it lives at <tools>/x_media_ci.py.
# In PyInstaller-frozen mode, the .spec bundles it into sys._MEIPASS.
X_MEDIA_CI = _TOOLS / "x_media_ci.py"
if not X_MEDIA_CI.is_file():
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "x_media_ci.py"
        if candidate.is_file():
            X_MEDIA_CI = candidate

if not X_MEDIA_CI.is_file():
    raise RuntimeError(f"x_media_ci.py not found (tried {_TOOLS} and sys._MEIPASS)")


# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="x_media CI Server",
    description=("HTTP wrapper around the x_media CI CLI. "
                 "Use from the Flutter app on Win11 / Ubuntu22 / Android 14+."),
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# In-memory job registry
# ---------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    op: str
    args: dict
    status: str = "queued"   # queued | running | done | failed
    returncode: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "op": self.op,
            "args": self.args,
            "status": self.status,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stdout_tail": self.stdout[-4000:],
            "stderr_tail": self.stderr[-4000:],
            "error": self.error,
        }


JOBS: dict[str, Job] = {}


async def _run_job(job: Job) -> None:
    job.status = "running"
    cmd = [PYTHON, str(X_MEDIA_CI), job.op, *job.args_to_argv()]
    pretty = " ".join(shlex.quote(c) for c in cmd)
    job.stdout += f"$ {pretty}\n"
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        job.stdout += (stdout_b or b"").decode("utf-8", "replace")
        job.stderr += (stderr_b or b"").decode("utf-8", "replace")
        job.returncode = proc.returncode
        job.status = "done" if proc.returncode == 0 else "failed"
    except Exception as e:
        job.status = "failed"
        job.error = f"{type(e).__name__}: {e}"
    finally:
        job.finished_at = time.time()


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    op: str = Field(..., description="md | pdf | ocr | ocr-md | ocr-long | all | fix | transcode | validate | batch")
    args: dict[str, Any] = Field(default_factory=dict,
                                 description="CLI args as a dict; converted via --key value")


class TweetUpdate(BaseModel):
    meta: dict = Field(..., description="Replacement tweet.json content")


# ---------------------------------------------------------------------------
# Health + discovery
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "ci_root": str(CI_ROOT),
        "ci_root_exists": CI_ROOT.is_dir(),
        "python": PYTHON,
        "x_media_ci": str(X_MEDIA_CI),
        "ts": time.time(),
    }


@app.get("/api/accounts")
async def list_accounts() -> dict:
    if not CI_ROOT.is_dir():
        return {"accounts": [], "ci_root": str(CI_ROOT)}
    out = []
    for handle_dir in sorted(p for p in CI_ROOT.iterdir() if p.is_dir()):
        tweet_count = 0
        for _ in find_tweet_dirs(handle_dir):
            tweet_count += 1
        if tweet_count == 0:
            continue
        out.append({"handle": handle_dir.name, "tweet_count": tweet_count})
    return {"accounts": out, "ci_root": str(CI_ROOT)}


@app.get("/api/accounts/{handle}")
async def account_detail(handle: str) -> dict:
    handle_dir = (CI_ROOT / handle).resolve()
    if not handle_dir.is_dir() or handle_dir.parent != CI_ROOT:
        raise HTTPException(404, f"unknown handle: {handle}")
    months: dict[str, int] = {}
    for td in find_tweet_dirs(handle_dir):
        parts = td.parts
        try:
            yyyy = parts[-3]
            ym = parts[-2]
            key = f"{yyyy}/{ym}"
        except IndexError:
            continue
        months[key] = months.get(key, 0) + 1
    return {
        "handle": handle,
        "tweet_count": sum(months.values()),
        "months": [{"key": k, "count": v}
                   for k, v in sorted(months.items())],
    }


# ---------------------------------------------------------------------------
# Tweet CRUD
# ---------------------------------------------------------------------------

def _locate_tweet(tweet_id: str) -> Optional[Path]:
    """Find the tweet directory under CI_ROOT by tweet_id (any handle)."""
    for td in find_tweet_dirs(CI_ROOT):
        if td.name.endswith(f"_{tweet_id}"):
            return td
    return None


@app.get("/api/tweet/{tweet_id}")
async def get_tweet(tweet_id: str) -> dict:
    td = _locate_tweet(tweet_id)
    if not td:
        raise HTTPException(404, f"tweet not found: {tweet_id}")
    meta = load_tweet_meta(td)
    tp = tweet_paths(td)
    media = []
    for sub in ("images", "video", "audio", "raw"):
        d = tp.root / "media" / sub
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file():
                    media.append({
                        "sub": sub,
                        "name": f.name,
                        "size": f.stat().st_size,
                        "url": f"/media/{tp.handle}/{td.name}/{sub}/{f.name}",
                    })
    return {
        "tweet_id": tweet_id,
        "dir": str(td),
        "handle": tp.handle,
        "meta": meta,
        "media": media,
    }


@app.put("/api/tweet/{tweet_id}")
async def put_tweet(tweet_id: str, body: TweetUpdate) -> dict:
    td = _locate_tweet(tweet_id)
    if not td:
        raise HTTPException(404, f"tweet not found: {tweet_id}")
    out = td / "tweet.json"
    out.write_text(
        json.dumps(body.meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, "path": str(out), "tweet_id": tweet_id}


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------

def _coerce_argv_value(v: Any) -> list[str]:
    """Booleans -> flags; lists -> repeated --key v; others -> --key str(v)."""
    if isinstance(v, bool):
        return ["--force"] if v else []
    if isinstance(v, (list, tuple)):
        out: list[str] = []
        for item in v:
            out += [f"--item" if False else "--" + "x", str(item)]  # placeholder
        return out
    return [str(v)]


def _argv_from_args(args: dict[str, Any]) -> list[str]:
    """Convert {"key": value, "flag": True, "list": [...]} to CLI argv."""
    out: list[str] = []
    for k, v in args.items():
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                out.append(flag)
        elif isinstance(v, (list, tuple)):
            for item in v:
                out += [flag, str(item)]
        else:
            out += [flag, str(v)]
    return out


# Monkey-patch the Job helper to expose argv()
def _job_args_to_argv(self) -> list[str]:  # type: ignore[no-redef]
    return _argv_from_args(self.args)
Job.args_to_argv = _job_args_to_argv  # type: ignore[attr-defined]


@app.post("/api/run")
async def run_op(req: RunRequest) -> dict:
    op = req.op
    if op not in {"md", "pdf", "ocr", "ocr-md", "ocr-long", "all",
                  "fix", "transcode", "validate", "batch", "lint"}:
        raise HTTPException(400, f"unsupported op: {op}")
    job = Job(id=uuid.uuid4().hex[:12], op=op, args=req.args)
    JOBS[job.id] = job
    asyncio.create_task(_run_job(job))
    return {"job_id": job.id, "status": job.status}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"unknown job: {job_id}")
    return job.to_dict()


# ---------------------------------------------------------------------------
# Static media serving
# ---------------------------------------------------------------------------

@app.get("/media/{handle}/{tweet_dir}/{sub}/{filename}")
async def media_file(handle: str, tweet_dir: str, sub: str, filename: str):
    # Defend against path traversal
    if ".." in (handle, tweet_dir, sub, filename) or "/" in filename or "\\" in filename:
        raise HTTPException(400, "invalid path")
    base = (CI_ROOT / handle).resolve()
    if base.parent != CI_ROOT or not base.is_dir():
        raise HTTPException(404, "unknown handle")
    p = (base / "tweets" / tweet_dir / "media" / sub / filename).resolve()
    if not str(p).startswith(str(base)) or not p.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(p)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

@app.get("/api/index/tweets")
async def index_tweets(limit: int = Query(200, ge=1, le=5000),
                       handle: Optional[str] = None) -> dict:
    """Return a flattened list of recent tweets from JSONL indices."""
    candidates: list[Path] = []
    if handle:
        candidates.append(CI_ROOT / "indices" / "by_handle" / f"{handle}.jsonl")
    else:
        candidates.append(CI_ROOT / "indices" / "tweets.jsonl")
    rows: list[dict] = []
    for p in candidates:
        if not p.is_file():
            continue
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    rows = rows[:limit]
    return {"count": len(rows), "items": rows}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:  # pragma: no cover
    import uvicorn
    host = os.environ.get("X_MEDIA_CI_HOST", "0.0.0.0")
    port = int(os.environ.get("X_MEDIA_CI_PORT", "18765"))
    uvicorn.run("app:app", host=host, port=port, reload=False)


if __name__ == "__main__":  # pragma: no cover
    main()

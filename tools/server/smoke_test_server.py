#!/usr/bin/env python3
"""Smoke-test a running frozen CiteSeal server, including one CLI-backed job."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise RuntimeError(f"expected JSON object from {url}")
    return decoded


def smoke_test(base_url: str, root: Path, *, timeout: float = 30.0) -> dict[str, Any]:
    """Verify health and a successful frozen ``validate`` background job."""
    base_url = base_url.rstrip("/")
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            health = _request_json(f"{base_url}/api/health")
            if health.get("ok") is True:
                break
            last_error = RuntimeError(f"unexpected health response: {health!r}")
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.25)
    else:
        raise RuntimeError(f"health check timed out: {last_error}")

    submitted = _request_json(
        f"{base_url}/api/run",
        method="POST",
        payload={
            "op": "validate",
            "args": {"root": str(root.resolve()), "quiet": True},
        },
    )
    job_id = submitted.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise RuntimeError(f"server returned no job_id: {submitted!r}")

    while time.monotonic() < deadline:
        job = _request_json(f"{base_url}/api/jobs/{job_id}")
        status = job.get("status")
        if status == "done":
            if job.get("returncode") != 0:
                raise RuntimeError(f"job reported done with nonzero return code: {job!r}")
            return job
        if status == "failed":
            raise RuntimeError(f"validate smoke job failed: {job!r}")
        if status not in {"queued", "running"}:
            raise RuntimeError(f"unexpected job status: {job!r}")
        time.sleep(0.25)

    raise RuntimeError(f"validate smoke job timed out: {job_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        result = smoke_test(args.url, args.root, timeout=args.timeout)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "job_id": result.get("id"),
                "status": result.get("status"),
                "returncode": result.get("returncode"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

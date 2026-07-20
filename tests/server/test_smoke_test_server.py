"""Tests for the cross-platform frozen-server smoke verifier."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "tools" / "server" / "smoke_test_server.py"
SPEC = importlib.util.spec_from_file_location("smoke_test_server", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_smoke_test_waits_for_health_and_successful_validate_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    responses = iter(
        [
            {"ok": True},
            {"job_id": "job-1", "status": "queued"},
            {"id": "job-1", "status": "running", "returncode": None},
            {"id": "job-1", "status": "done", "returncode": 0},
        ]
    )
    calls: list[tuple[str, str, object]] = []

    def fake_request(url, *, method="GET", payload=None, timeout=5.0):
        calls.append((url, method, payload))
        return next(responses)

    monkeypatch.setattr(smoke, "_request_json", fake_request)
    monkeypatch.setattr(smoke.time, "sleep", lambda _seconds: None)

    result = smoke.smoke_test("http://127.0.0.1:8765/", tmp_path, timeout=5)

    assert result["status"] == "done"
    assert calls[1] == (
        "http://127.0.0.1:8765/api/run",
        "POST",
        {
            "op": "validate",
            "args": {"root": str(tmp_path.resolve()), "quiet": True},
        },
    )
    assert calls[-1][0].endswith("/api/jobs/job-1")


def test_smoke_test_fails_closed_on_failed_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    responses = iter(
        [
            {"ok": True},
            {"job_id": "job-2", "status": "queued"},
            {
                "id": "job-2",
                "status": "failed",
                "returncode": 2,
                "stderr_tail": "boom",
            },
        ]
    )
    monkeypatch.setattr(
        smoke,
        "_request_json",
        lambda *args, **kwargs: next(responses),
    )

    with pytest.raises(RuntimeError, match="validate smoke job failed"):
        smoke.smoke_test("http://127.0.0.1:8765", tmp_path, timeout=5)

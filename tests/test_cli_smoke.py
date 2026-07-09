"""Smoke tests for CLI entry points.

These don't test full functionality (that's covered by unit tests).
They verify that the CLI scripts:
  - Can be invoked without import errors
  - ``--help`` exits 0
  - No-args invocation exits with a usage error (exit 2)
  - The validate CLI correctly exits 0 for good fixtures, 1 for bad

This catches environment/path issues that unit tests miss.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Project root (parent of tests/)
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "tools" / "scripts"
CLI = ROOT / "tools" / "citeseal.py"
FIXTURES = ROOT / "tests" / "fixtures"

GOOD_DIR = (
    FIXTURES / "accounts" / "example_user" / "tweets" / "2026" / "2026-07"
    / "20260708_180000_1234567890"
)
DIRTY_DIR = (
    FIXTURES / "accounts" / "example_user" / "tweets" / "2026" / "2026-07"
    / "20260701_120000_9876543210"
)


def _run(script: Path, args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    """Run a Python script and capture output."""
    cmd = [sys.executable, str(script), *args]
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30
    )


# ── tweet_validate.py ───────────────────────────────────────────────────────

class TestValidateCLI:
    def test_help_exits_0(self):
        r = _run(SCRIPTS / "tweet_validate.py", ["--help"])
        assert r.returncode == 0
        assert "validate" in r.stdout.lower() or "usage" in r.stdout.lower()

    def test_no_args_exits_2(self):
        r = _run(SCRIPTS / "tweet_validate.py", [])
        assert r.returncode == 2
        assert "required" in r.stderr.lower()

    def test_good_fixture_exits_0(self):
        r = _run(SCRIPTS / "tweet_validate.py", [str(GOOD_DIR)])
        assert r.returncode == 0
        assert "0 error" in r.stdout

    def test_dirty_fixture_exits_1(self):
        r = _run(SCRIPTS / "tweet_validate.py", [str(DIRTY_DIR)])
        assert r.returncode == 1
        assert "1 error" in r.stdout

    def test_root_recursive(self):
        r = _run(SCRIPTS / "tweet_validate.py", ["--root", str(FIXTURES / "accounts")])
        assert r.returncode == 1  # dirty + invalid fixtures have errors
        assert "3 dirs" in r.stdout

    def test_strict_mode_treats_warnings_as_errors(self):
        """Dirty fixture has warnings; --strict should still exit 1."""
        r = _run(SCRIPTS / "tweet_validate.py", ["--strict", str(DIRTY_DIR)])
        assert r.returncode == 1


# ── tweet_fix.py ────────────────────────────────────────────────────────────

class TestFixCLI:
    def test_help_exits_0(self):
        r = _run(SCRIPTS / "tweet_fix.py", ["--help"])
        assert r.returncode == 0

    def test_no_args_exits_2(self):
        r = _run(SCRIPTS / "tweet_fix.py", [])
        assert r.returncode == 2

    def test_dry_run_does_not_modify(self, tmp_path: Path):
        """Dry run (default) should not modify tweet.json."""
        # Copy dirty fixture to tmp to avoid mutating the committed fixture
        import shutil
        dst = tmp_path / "dirty_copy"
        shutil.copytree(DIRTY_DIR, dst)

        original = (dst / "tweet.json").read_text(encoding="utf-8")
        r = _run(SCRIPTS / "tweet_fix.py", [str(dst)])
        assert r.returncode == 0
        # File should be unchanged in dry-run mode
        assert (dst / "tweet.json").read_text(encoding="utf-8") == original

    def test_apply_modifies_file(self, tmp_path: Path):
        """--apply should strip the @ prefix from author_handle."""
        import shutil
        dst = tmp_path / "dirty_copy"
        shutil.copytree(DIRTY_DIR, dst)

        r = _run(SCRIPTS / "tweet_fix.py", ["--apply", str(dst)])
        assert r.returncode == 0

        import json
        meta = json.loads((dst / "tweet.json").read_text(encoding="utf-8"))
        assert meta["author_handle"] == "example_user"
        assert not meta["author_handle"].startswith("@")


# ── citeseal.py ───────────────────────────────────────────────────────────

class TestUnifiedCLI:
    def test_help_exits_0(self):
        r = _run(CLI, ["--help"])
        assert r.returncode == 0
        assert "md" in r.stdout or "pdf" in r.stdout or "ocr" in r.stdout

    def test_no_args_shows_usage(self):
        r = _run(CLI, [])
        # argparse with subcommands: no subcommand -> exit 2
        assert r.returncode == 2

    def test_doctor_help_exits_0(self):
        """doctor subcommand should be registered and show help."""
        r = _run(CLI, ["doctor", "--help"])
        assert r.returncode == 0
        assert "doctor" in r.stdout.lower()

    def test_doctor_runs_and_reports(self):
        """doctor should run, print diagnostics, and exit 0 (warnings only, no errors)."""
        r = _run(CLI, ["doctor"])
        assert r.returncode == 0
        assert "citeseal doctor" in r.stdout
        assert "Python" in r.stdout
        assert "Project layout" in r.stdout


# ── export-agent ────────────────────────────────────────────────────────────

class TestExportAgentCLI:
    def test_export_agent_help_exits_0(self):
        """export-agent subcommand should be registered and show help."""
        r = _run(CLI, ["export-agent", "--help"])
        assert r.returncode == 0
        assert "export-agent" in r.stdout.lower()
        assert "bundle" in r.stdout.lower()

    def test_export_agent_no_args_exits_2(self):
        r = _run(CLI, ["export-agent"])
        assert r.returncode == 2

    def test_export_agent_creates_bundle(self, tmp_path: Path):
        """export-agent should create a valid bundle.json in the output dir."""
        out = tmp_path / "bundle_out"
        r = _run(CLI, [
            "export-agent",
            "--tweet-dir", str(GOOD_DIR),
            "--output", str(out),
            "--hash-media",
        ])
        assert r.returncode == 0
        assert (out / "bundle.json").is_file()

        # Verify the bundle is valid JSON with expected fields
        import json
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert data["bundle_version"] == "1.0"
        assert data["item_id"] == "1234567890"
        assert data["author_handle"] == "example_user"

    def test_export_agent_media_copied(self, tmp_path: Path):
        """export-agent should copy media files into the bundle."""
        out = tmp_path / "bundle_out"
        r = _run(CLI, [
            "export-agent",
            "--tweet-dir", str(GOOD_DIR),
            "--output", str(out),
        ])
        assert r.returncode == 0
        # The good fixture has 2 images
        media_dir = out / "media"
        assert media_dir.is_dir()
        copied = list(media_dir.iterdir())
        assert len(copied) == 2

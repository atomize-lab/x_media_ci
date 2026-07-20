"""Smoke test for the live demo script.

Ensures the end-to-end demo (export-agent -> manifest -> structural checks)
passes without errors, using synthetic fixtures only.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_SCRIPT = REPO_ROOT / "tools" / "scripts" / "demo_agent_consumption.py"


def test_demo_runs_successfully(tmp_path):
    """The demo script should exit 0 and print DEMO PASSED."""
    result = subprocess.run(
        [
            sys.executable,
            str(DEMO_SCRIPT),
            "--bundle-dir",
            str(tmp_path / "cs_demo"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    assert result.returncode == 0, f"demo failed:\n{result.stderr}"
    assert "DEMO PASSED" in result.stdout, "demo did not report PASSED"
    assert "10/10 structural checks passed" in result.stdout


def test_demo_runs_with_cp1252_console(tmp_path):
    """The demo must remain usable on legacy Windows console encodings."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
        [
            sys.executable,
            str(DEMO_SCRIPT),
            "--bundle-dir",
            str(tmp_path / "cs_demo_cp1252"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, f"demo failed under cp1252:\n{result.stderr}"
    assert "DEMO PASSED" in result.stdout

"""Shared pytest configuration and fixtures.

Makes ``tools/scripts/`` importable so tests can ``from ci_common import ...``
without sys.path hacks in every file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Path setup ──────────────────────────────────────────────────────────────
# Project root = parent of tests/
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "tools" / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ── Fixtures ────────────────────────────────────────────────────────────────

FIXTURES_DIR = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Root of the synthetic fixture tree."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def accounts_dir(fixtures_dir: Path) -> Path:
    return fixtures_dir / "accounts"


@pytest.fixture(scope="session")
def good_tweet_dir(fixtures_dir: Path) -> Path:
    """A fully-compliant tweet dir (zero errors, zero warnings)."""
    return (
        fixtures_dir
        / "accounts"
        / "example_user"
        / "tweets"
        / "2026"
        / "2026-07"
        / "20260708_180000_1234567890"
    )


@pytest.fixture(scope="session")
def dirty_tweet_dir(fixtures_dir: Path) -> Path:
    """A tweet dir with warnings + one error (missing media file)."""
    return (
        fixtures_dir
        / "accounts"
        / "example_user"
        / "tweets"
        / "2026"
        / "2026-07"
        / "20260701_120000_9876543210"
    )


@pytest.fixture(scope="session")
def invalid_tweet_dir(fixtures_dir: Path) -> Path:
    """A tweet dir missing required fields (3 errors)."""
    return (
        fixtures_dir
        / "accounts"
        / "example_user"
        / "tweets"
        / "2026"
        / "2026-07"
        / "20260705_090000_5555555555"
    )


@pytest.fixture
def tmp_tweet_dir(tmp_path: Path) -> Path:
    """A fresh empty tweet dir for write/round-trip tests."""
    d = tmp_path / "tmp_tweet"
    d.mkdir()
    return d

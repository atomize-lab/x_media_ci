"""Tests for the JSONL index files under ``indices/``.

Verifies that:
  - Each line is valid JSON
  - The ``tweet_id`` dedup key is present
  - ``by_handle/`` and ``by_date/`` partitions are consistent with ``tweets.jsonl``
"""
from __future__ import annotations

import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    """Read a .jsonl file and return a list of parsed dicts."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ── tweets.jsonl (global index) ─────────────────────────────────────────────

class TestGlobalIndex:
    def test_tweets_jsonl_is_valid_jsonl(self, fixtures_dir: Path):
        rows = _read_jsonl(fixtures_dir / "indices" / "tweets.jsonl")
        assert len(rows) == 2

    def test_each_row_has_tweet_id(self, fixtures_dir: Path):
        rows = _read_jsonl(fixtures_dir / "indices" / "tweets.jsonl")
        for row in rows:
            assert "tweet_id" in row
            assert row["tweet_id"]

    def test_tweet_ids_are_unique(self, fixtures_dir: Path):
        rows = _read_jsonl(fixtures_dir / "indices" / "tweets.jsonl")
        ids = [r["tweet_id"] for r in rows]
        assert len(ids) == len(set(ids))

    def test_row_has_required_fields(self, fixtures_dir: Path):
        rows = _read_jsonl(fixtures_dir / "indices" / "tweets.jsonl")
        for row in rows:
            assert "tweet_url" in row
            assert "author_handle" in row
            assert "datetime_utc" in row
            assert "text_preview" in row


# ── by_handle partition ─────────────────────────────────────────────────────

class TestByHandleIndex:
    def test_handle_partition_exists(self, fixtures_dir: Path):
        p = fixtures_dir / "indices" / "by_handle" / "example_user.jsonl"
        assert p.is_file()

    def test_handle_partition_matches_global(self, fixtures_dir: Path):
        global_rows = _read_jsonl(fixtures_dir / "indices" / "tweets.jsonl")
        handle_rows = _read_jsonl(
            fixtures_dir / "indices" / "by_handle" / "example_user.jsonl"
        )
        global_ids = {r["tweet_id"] for r in global_rows}
        handle_ids = {r["tweet_id"] for r in handle_rows}
        # All handle-partition tweets should be in the global index
        assert handle_ids.issubset(global_ids)


# ── by_date partition ───────────────────────────────────────────────────────

class TestByDateIndex:
    def test_date_partition_exists(self, fixtures_dir: Path):
        p = fixtures_dir / "indices" / "by_date" / "2026" / "2026-07.jsonl"
        assert p.is_file()

    def test_date_partition_has_correct_month(self, fixtures_dir: Path):
        rows = _read_jsonl(
            fixtures_dir / "indices" / "by_date" / "2026" / "2026-07.jsonl"
        )
        for row in rows:
            # datetime_utc should start with 2026-07
            assert row["datetime_utc"].startswith("2026-07")

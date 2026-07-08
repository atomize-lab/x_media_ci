"""Tests for ``ci_common.py`` shared helpers.

These are the foundational path/IO helpers used by every other tool,
so they get the most thorough coverage.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ci_common import (
    EXPORTS_DIRNAME,
    MEDIA_SUBDIRS,
    TWEET_JSON_NAME,
    TweetPaths,
    ensure_dir,
    env_flag,
    find_first_existing,
    find_tweet_dirs,
    is_tweet_dir,
    load_tweet_meta,
    safe_filename,
    tweet_paths,
)


# ── Constants ───────────────────────────────────────────────────────────────

class TestConstants:
    def test_media_subdirs(self):
        assert MEDIA_SUBDIRS == ("images", "video", "audio", "raw")

    def test_exports_dirname(self):
        assert EXPORTS_DIRNAME == "exports"

    def test_tweet_json_name(self):
        assert TWEET_JSON_NAME == "tweet.json"


# ── TweetPaths ──────────────────────────────────────────────────────────────

class TestTweetPaths:
    def test_resolves_all_subdirs(self, good_tweet_dir: Path):
        tp = tweet_paths(good_tweet_dir)
        assert tp.root == good_tweet_dir
        assert tp.images_dir == good_tweet_dir / "media" / "images"
        assert tp.video_dir == good_tweet_dir / "media" / "video"
        assert tp.audio_dir == good_tweet_dir / "media" / "audio"
        assert tp.raw_dir == good_tweet_dir / "media" / "raw"
        assert tp.exports_dir == good_tweet_dir / EXPORTS_DIRNAME
        assert tp.tweet_json == good_tweet_dir / TWEET_JSON_NAME

    def test_handle_property_extracts_from_path(self, good_tweet_dir: Path):
        tp = tweet_paths(good_tweet_dir)
        # path: .../accounts/<handle>/tweets/YYYY/YYYY-MM/<dir>
        assert tp.handle == "example_user"

    def test_handle_empty_for_shallow_path(self):
        # A path with fewer than 5 parts cannot have a handle component
        d = Path("/tmp")
        tp = tweet_paths(d)
        assert tp.handle == ""

    def test_extract_json_prefers_non_ocr(self, good_tweet_dir: Path):
        tp = tweet_paths(good_tweet_dir)
        result = tp.extract_json()
        assert result is not None
        assert result.name == "article_md_extract.json"
        assert "_ocr_" not in result.name

    def test_extract_json_returns_none_when_no_exports(self, invalid_tweet_dir: Path):
        tp = tweet_paths(invalid_tweet_dir)
        assert tp.extract_json() is None

    def test_ocr_txt_returns_none_when_missing(self, good_tweet_dir: Path):
        tp = tweet_paths(good_tweet_dir)
        assert tp.ocr_txt() is None


# ── is_tweet_dir / find_tweet_dirs ──────────────────────────────────────────

class TestTweetDirDiscovery:
    def test_is_tweet_dir_true(self, good_tweet_dir: Path):
        assert is_tweet_dir(good_tweet_dir) is True

    def test_is_tweet_dir_false_for_plain_dir(self, tmp_path: Path):
        assert is_tweet_dir(tmp_path) is False

    def test_is_tweet_dir_false_for_file(self, good_tweet_dir: Path):
        assert is_tweet_dir(good_tweet_dir / "tweet.json") is False

    def test_find_tweet_dirs_finds_all(self, accounts_dir: Path):
        results = find_tweet_dirs(accounts_dir)
        assert len(results) == 3
        # Results are sorted
        ids = [p.name for p in results]
        assert "20260701_120000_9876543210" in ids
        assert "20260705_090000_5555555555" in ids
        assert "20260708_180000_1234567890" in ids

    def test_find_tweet_dirs_empty_for_nonexistent(self):
        assert find_tweet_dirs(Path("/nonexistent/path")) == []

    def test_find_tweet_dirs_empty_for_no_tweets(self, tmp_path: Path):
        assert find_tweet_dirs(tmp_path) == []


# ── load_tweet_meta ─────────────────────────────────────────────────────────

class TestLoadTweetMeta:
    def test_loads_valid_json(self, good_tweet_dir: Path):
        meta = load_tweet_meta(good_tweet_dir)
        assert meta["tweet_id"] == "1234567890"
        assert meta["author_handle"] == "example_user"
        assert len(meta["media"]) == 2

    def test_returns_empty_for_missing_file(self, tmp_path: Path):
        assert load_tweet_meta(tmp_path) == {}

    def test_returns_empty_for_invalid_json(self, tmp_path: Path):
        (tmp_path / "tweet.json").write_text("{invalid json}", encoding="utf-8")
        assert load_tweet_meta(tmp_path) == {}


# ── safe_filename ───────────────────────────────────────────────────────────

class TestSafeFilename:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("hello world", "hello world"),
            ("a/b", "a_b"),
            ("a\\b", "a_b"),
            ('a"b', "a_b"),
            ("a*b?c", "a_b_c"),
            ("trailing.", "trailing"),
            ("trailing   ", "trailing"),
            ("", "untitled"),
            ("   ", "untitled"),
        ],
    )
    def test_safe_filename(self, raw, expected):
        assert safe_filename(raw) == expected


# ── ensure_dir / find_first_existing ────────────────────────────────────────

class TestFileHelpers:
    def test_ensure_dir_creates_nested(self, tmp_path: Path):
        p = tmp_path / "a" / "b" / "c"
        result = ensure_dir(p)
        assert result == p
        assert p.is_dir()

    def test_ensure_dir_idempotent(self, tmp_path: Path):
        p = tmp_path / "x"
        ensure_dir(p)
        ensure_dir(p)  # should not raise
        assert p.is_dir()

    def test_find_first_existing_returns_first(self, tmp_path: Path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        b.write_text("x")
        result = find_first_existing([a, b])
        assert result == b

    def test_find_first_existing_returns_none(self, tmp_path: Path):
        assert find_first_existing([tmp_path / "a", tmp_path / "b"]) is None

    def test_find_first_existing_handles_none(self):
        assert find_first_existing([None, None]) is None


# ── env_flag ────────────────────────────────────────────────────────────────

class TestEnvFlag:
    def test_true_values(self, monkeypatch):
        for v in ("1", "true", "True", "YES", "on", "y"):
            monkeypatch.setenv("TEST_FLAG", v)
            assert env_flag("TEST_FLAG") is True

    def test_false_values(self, monkeypatch):
        for v in ("0", "false", "no", "off", "", "random"):
            monkeypatch.setenv("TEST_FLAG", v)
            assert env_flag("TEST_FLAG") is False

    def test_unset_uses_default(self, monkeypatch):
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert env_flag("TEST_FLAG") is False
        assert env_flag("TEST_FLAG", default=True) is True

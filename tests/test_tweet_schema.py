"""Tests for ``tweet_schema.py`` validation logic.

Uses the three fixture tweet dirs (good / dirty / invalid) to verify
that the validator correctly distinguishes errors from warnings and
that ``write_tweet_json`` round-trips cleanly.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tweet_schema import (
    RECOMMENDED_FIELDS,
    REQUIRED_FIELDS,
    ValidationIssue,
    ValidationReport,
    validate_tweet_dir,
    write_tweet_json,
)


# ── Constants ───────────────────────────────────────────────────────────────

class TestSchemaConstants:
    def test_required_fields(self):
        assert REQUIRED_FIELDS == (
            "tweet_id",
            "tweet_url",
            "author_handle",
            "datetime_utc",
        )

    def test_recommended_fields(self):
        assert "text" in RECOMMENDED_FIELDS
        assert "media" in RECOMMENDED_FIELDS
        assert "exports" in RECOMMENDED_FIELDS


# ── ValidationIssue / ValidationReport ──────────────────────────────────────

class TestValidationReport:
    def test_ok_with_no_issues(self):
        r = ValidationReport()
        assert r.ok is True
        assert r.errors == []
        assert r.warnings == []

    def test_not_ok_with_error(self):
        r = ValidationReport()
        r.issues.append(ValidationIssue("error", "E001", "boom"))
        assert r.ok is False
        assert len(r.errors) == 1
        assert len(r.warnings) == 0

    def test_warnings_do_not_break_ok(self):
        r = ValidationReport()
        r.issues.append(ValidationIssue("warning", "W001", "meh"))
        assert r.ok is True
        assert len(r.warnings) == 1
        assert len(r.errors) == 0

    def test_extend(self):
        r = ValidationReport()
        r.extend([
            ValidationIssue("error", "E1", "a"),
            ValidationIssue("warning", "W1", "b"),
        ])
        assert len(r.issues) == 2

    def test_issue_render(self):
        i = ValidationIssue("error", "E001", "bad thing", "/path/to/file")
        rendered = i.render()
        assert "ERROR" in rendered
        assert "E001" in rendered
        assert "bad thing" in rendered
        assert "/path/to/file" in rendered

    def test_required_field_error_names_the_field(self, tmp_path: Path):
        """E010 messages must name the field so users can fix tweet.json quickly."""
        tweet_dir = tmp_path / "t"
        tweet_dir.mkdir()
        (tweet_dir / "tweet.json").write_text(
            json.dumps({"tweet_id": "1", "tweet_url": "https://x.com/a/status/1"}),
            encoding="utf-8",
        )
        report = validate_tweet_dir(tweet_dir)
        e010 = [e for e in report.errors if e.code == "E010"]
        assert e010, "expected missing-required-field errors"
        messages = " ".join(e.message for e in e010)
        assert "author_handle" in messages
        assert "datetime_utc" in messages
        assert "missing required field" in messages


# ── validate_tweet_dir: good fixture ────────────────────────────────────────

class TestValidateGoodFixture:
    def test_good_tweet_passes(self, good_tweet_dir: Path):
        report = validate_tweet_dir(good_tweet_dir)
        assert report.ok is True
        assert len(report.errors) == 0
        assert len(report.warnings) == 0

    def test_validates_media_files_exist(self, good_tweet_dir: Path):
        report = validate_tweet_dir(good_tweet_dir)
        # No E052 errors (media file not found)
        e052 = [e for e in report.issues if e.code == "E052"]
        assert e052 == []

    def test_validates_exports_files_exist(self, good_tweet_dir: Path):
        report = validate_tweet_dir(good_tweet_dir)
        w062 = [w for w in report.issues if w.code == "W062"]
        assert w062 == []


# ── validate_tweet_dir: dirty fixture ───────────────────────────────────────

class TestValidateDirtyFixture:
    def test_dirty_tweet_has_errors(self, dirty_tweet_dir: Path):
        report = validate_tweet_dir(dirty_tweet_dir)
        assert report.ok is False
        assert len(report.errors) >= 1

    def test_dirty_tweet_missing_media_file(self, dirty_tweet_dir: Path):
        report = validate_tweet_dir(dirty_tweet_dir)
        e052 = [e for e in report.errors if e.code == "E052"]
        assert len(e052) == 1
        assert "missing_file.png" in e052[0].message

    def test_dirty_tweet_handle_starts_with_at(self, dirty_tweet_dir: Path):
        report = validate_tweet_dir(dirty_tweet_dir)
        w030 = [w for w in report.warnings if w.code == "W030"]
        assert len(w030) == 1

    def test_dirty_tweet_datetime_not_iso(self, dirty_tweet_dir: Path):
        report = validate_tweet_dir(dirty_tweet_dir)
        w040 = [w for w in report.warnings if w.code == "W040"]
        assert len(w040) == 1

    def test_dirty_tweet_export_missing_on_disk(self, dirty_tweet_dir: Path):
        report = validate_tweet_dir(dirty_tweet_dir)
        w062 = [w for w in report.warnings if w.code == "W062"]
        assert len(w062) == 1
        assert "nonexistent.pdf" in w062[0].message


# ── validate_tweet_dir: invalid fixture ─────────────────────────────────────

class TestValidateInvalidFixture:
    def test_invalid_tweet_missing_required_fields(self, invalid_tweet_dir: Path):
        report = validate_tweet_dir(invalid_tweet_dir)
        assert report.ok is False
        e010 = [e for e in report.errors if e.code == "E010"]
        # Missing: tweet_url, author_handle, datetime_utc
        missing = [e.message for e in e010]
        assert any("tweet_url" in m for m in missing)
        assert any("author_handle" in m for m in missing)
        assert any("datetime_utc" in m for m in missing)


# ── validate_tweet_dir: edge cases ──────────────────────────────────────────

class TestValidateEdgeCases:
    def test_not_a_tweet_dir(self, tmp_path: Path):
        report = validate_tweet_dir(tmp_path)
        assert report.ok is False
        assert report.errors[0].code == "E001"

    def test_invalid_json(self, tmp_path: Path):
        (tmp_path / "tweet.json").write_text("{broken", encoding="utf-8")
        report = validate_tweet_dir(tmp_path)
        assert report.ok is False
        assert any(e.code == "E003" for e in report.errors)

    def test_url_handle_mismatch_is_warning(self, tmp_tweet_dir: Path):
        """tweet_url handle differs from author_handle -> W021 warning."""
        meta = {
            "tweet_id": "111",
            "tweet_url": "https://x.com/wrong_handle/status/111",
            "author_handle": "correct_handle",
            "datetime_utc": "2026-07-08T10:00:00Z",
            "text": "test",
        }
        (tmp_tweet_dir / "tweet.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        report = validate_tweet_dir(tmp_tweet_dir)
        w021 = [w for w in report.warnings if w.code == "W021"]
        assert len(w021) == 1


# ── write_tweet_json round-trip ─────────────────────────────────────────────

class TestWriteTweetJson:
    def test_write_and_validate_roundtrip(self, tmp_tweet_dir: Path):
        meta = {
            "tweet_id": "9999999999",
            "tweet_url": "https://x.com/test_user/status/9999999999",
            "author_handle": "test_user",
            "datetime_utc": "2026-07-08T12:00:00Z",
            "datetime_local": "2026-07-08T20:00:00+08:00",
            "text": "Round-trip test.",
            "media": [],
            "exports": [],
            "components": ["text"],
            "replies": [],
        }
        out = write_tweet_json(tmp_tweet_dir, meta)
        assert out.is_file()

        # Re-read and verify
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["tweet_id"] == "9999999999"
        assert loaded["author_handle"] == "test_user"

        # Validate the written file
        report = validate_tweet_dir(tmp_tweet_dir)
        assert report.ok is True

    def test_write_raises_on_invalid_meta(self, tmp_tweet_dir: Path):
        """Missing required fields should raise ValueError."""
        meta = {
            "tweet_id": "123",
            # missing tweet_url, author_handle, datetime_utc
            "text": "invalid",
        }
        with pytest.raises(ValueError, match="validation failed"):
            write_tweet_json(tmp_tweet_dir, meta)

    def test_write_skips_validation_when_disabled(self, tmp_tweet_dir: Path):
        meta = {"tweet_id": "123", "text": "no validation"}
        out = write_tweet_json(tmp_tweet_dir, meta, validate=False)
        assert out.is_file()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["tweet_id"] == "123"

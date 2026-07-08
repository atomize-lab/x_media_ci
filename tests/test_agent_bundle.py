"""Tests for the agent bundle builder (tools/scripts/build_agent_bundle.py).

Covers:
  - Module-level build_bundle() with the good fixture
  - Text truncation logic
  - Media copying and SHA-256 hashing
  - Trust flags correctness
  - Provenance and citation label
  - Self-check verification
  - Error handling for invalid tweet dirs
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

# conftest.py adds tools/scripts to sys.path
from build_agent_bundle import (
    BUNDLE_VERSION,
    MAX_EXCERPT_CHARS,
    build_bundle,
    _build_excerpt,
    _build_citation_label,
    _infer_platform,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOOD_DIR = (
    FIXTURES / "accounts" / "example_user" / "tweets" / "2026" / "2026-07"
    / "20260708_180000_1234567890"
)


# ── build_bundle() integration ─────────────────────────────────────────────

class TestBuildBundle:
    """Integration tests using the good fixture directory."""

    def test_creates_bundle_json(self, tmp_path: Path):
        out = tmp_path / "bundle"
        bundle_path = build_bundle(GOOD_DIR, out)
        assert bundle_path.is_file()
        assert bundle_path.name == "bundle.json"

    def test_bundle_has_required_fields(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))

        required = (
            "bundle_version", "item_id", "source_platform", "source_url",
            "captured_at", "author_handle", "text_excerpt", "assets",
            "provenance",
        )
        for key in required:
            assert key in data, f"Missing required field: {key}"

    def test_bundle_version_is_1_0(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert data["bundle_version"] == BUNDLE_VERSION
        assert data["bundle_version"] == "1.0"

    def test_item_id_matches_tweet_id(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert data["item_id"] == "1234567890"

    def test_source_platform_is_x(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert data["source_platform"] == "x"

    def test_author_handle_no_at_prefix(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert data["author_handle"] == "example_user"
        assert not data["author_handle"].startswith("@")

    def test_text_excerpt_present(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert "local-first media archiver" in data["text_excerpt"]

    def test_text_full_omitted_for_short_text(self, tmp_path: Path):
        """The good fixture text is < 280 chars, so text_full should be omitted."""
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert "text_full" not in data

    def test_media_copied_to_bundle(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        media = data.get("media") or []
        assert len(media) == 2
        # Files should exist on disk
        for m in media:
            assert (out / m["path"]).is_file()

    def test_media_has_alt_text(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        media = data.get("media") or []
        assert any(m.get("alt_text") for m in media)

    def test_hash_media_adds_sha256(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out, hash_media=True)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        media = data.get("media") or []
        for m in media:
            assert "sha256" in m
            assert len(m["sha256"]) == 64  # SHA-256 hex length

    def test_no_hash_media_omits_sha256(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out, hash_media=False)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        media = data.get("media") or []
        for m in media:
            assert "sha256" not in m

    def test_trust_flags(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        flags = data["trust_flags"]
        assert flags["validated"] is True
        assert flags["has_media"] is True
        assert flags["media_verified"] is True

    def test_citation_label(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert data["citation_label"] == "@example_user, 2026-07-08"

    def test_provenance_fields(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        prov = data["provenance"]
        assert "exported_at" in prov
        assert "export_tool" in prov
        assert "source_dir" in prov
        assert "build_agent_bundle" in prov["export_tool"]

    def test_assets_list_does_not_include_bundle_json(self, tmp_path: Path):
        """bundle.json is the manifest itself, not an asset."""
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        asset_paths = [a["path"] for a in data["assets"]]
        assert "bundle.json" not in asset_paths

    def test_assets_list_includes_tweet_json(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        asset_paths = [a["path"] for a in data["assets"]]
        assert "tweet.json" in asset_paths

    def test_assets_have_kinds(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        valid_kinds = {"metadata", "media", "ocr", "article", "export",
                       "context", "manifest"}
        for a in data["assets"]:
            assert a["kind"] in valid_kinds

    def test_overwrite_removes_existing(self, tmp_path: Path):
        out = tmp_path / "bundle"
        out.mkdir()
        (out / "old_file.txt").write_text("old", encoding="utf-8")
        build_bundle(GOOD_DIR, out, overwrite=True)
        assert not (out / "old_file.txt").exists()
        assert (out / "bundle.json").is_file()

    def test_no_overwrite_keeps_existing(self, tmp_path: Path):
        """With overwrite=False, existing files are kept alongside new ones."""
        out = tmp_path / "bundle"
        out.mkdir()
        (out / "old_file.txt").write_text("old", encoding="utf-8")
        build_bundle(GOOD_DIR, out, overwrite=False)
        assert (out / "old_file.txt").exists()
        assert (out / "bundle.json").is_file()

    def test_invalid_tweet_dir_raises(self, tmp_path: Path):
        bad_dir = tmp_path / "not_a_tweet"
        bad_dir.mkdir()
        with pytest.raises(NotADirectoryError):
            build_bundle(bad_dir, tmp_path / "out")


# ── Text truncation ────────────────────────────────────────────────────────

class TestExcerptTruncation:
    def test_short_text_no_truncation(self):
        text = "Short text."
        excerpt, full = _build_excerpt(text, 280)
        assert excerpt == text
        assert full is None

    def test_long_text_truncated(self):
        text = "A" * 500
        excerpt, full = _build_excerpt(text, 280)
        assert len(excerpt) == 280 + 3  # 280 chars + "..."
        assert excerpt.endswith("...")
        assert full == text

    def test_exact_boundary_no_truncation(self):
        text = "A" * 280
        excerpt, full = _build_excerpt(text, 280)
        assert excerpt == text
        assert full is None

    def test_empty_text(self):
        excerpt, full = _build_excerpt("", 280)
        assert excerpt == ""
        assert full is None

    def test_custom_max_excerpt(self):
        text = "A" * 100
        excerpt, full = _build_excerpt(text, 50)
        assert len(excerpt) == 53
        assert excerpt.endswith("...")
        assert full == text

    def test_truncation_in_build_bundle(self, tmp_path: Path):
        """Verify that a long text produces text_full in the bundle."""
        # Create a synthetic tweet dir with long text
        src = tmp_path / "long_tweet"
        src.mkdir()
        (src / "media" / "images").mkdir(parents=True)

        long_text = "X" * 500
        meta = {
            "tweet_id": "999",
            "tweet_url": "https://x.com/testuser/status/999",
            "author_handle": "testuser",
            "datetime_utc": "2026-07-09T10:00:00Z",
            "text": long_text,
            "media": [],
        }
        (src / "tweet.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        out = tmp_path / "bundle_out"
        build_bundle(src, out, max_excerpt=100)

        data = json.loads((out / "bundle.json").read_text("utf-8"))
        assert len(data["text_excerpt"]) == 103  # 100 + "..."
        assert data["text_excerpt"].endswith("...")
        assert data["text_full"] == long_text


# ── Citation label ─────────────────────────────────────────────────────────

class TestCitationLabel:
    def test_full_label(self):
        meta = {"author_handle": "example_user", "datetime_utc": "2026-07-08T18:00:00Z"}
        assert _build_citation_label(meta) == "@example_user, 2026-07-08"

    def test_handle_with_at(self):
        meta = {"author_handle": "@example_user", "datetime_utc": "2026-07-08T18:00:00Z"}
        assert _build_citation_label(meta) == "@example_user, 2026-07-08"

    def test_no_date(self):
        meta = {"author_handle": "example_user", "datetime_utc": ""}
        assert _build_citation_label(meta) == "@example_user"

    def test_no_handle(self):
        meta = {"author_handle": "", "datetime_utc": "2026-07-08T18:00:00Z"}
        assert _build_citation_label(meta) == ""

    def test_empty_meta(self):
        assert _build_citation_label({}) == ""


# ── Platform inference ─────────────────────────────────────────────────────

class TestPlatformInference:
    def test_x_dot_com(self):
        assert _infer_platform("https://x.com/user/status/123") == "x"

    def test_twitter_dot_com(self):
        assert _infer_platform("https://twitter.com/user/status/123") == "twitter"

    def test_web(self):
        assert _infer_platform("https://example.com/article") == "web"

    def test_empty(self):
        assert _infer_platform("") == "web"


# ── Self-check ─────────────────────────────────────────────────────────────

class TestSelfCheck:
    def test_self_check_passes_for_good_fixture(self, tmp_path: Path):
        """The build should not raise during self-check for a valid fixture."""
        out = tmp_path / "bundle"
        # This should not raise
        bundle_path = build_bundle(GOOD_DIR, out)
        assert bundle_path.is_file()

    def test_bundle_json_is_valid_json(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(GOOD_DIR, out)
        # Should not raise
        json.loads((out / "bundle.json").read_text("utf-8"))


# ── Dirty fixture (missing media) ──────────────────────────────────────────

class TestDirtyFixture:
    """Test with the fixture that has a missing media file."""

    DIRTY_DIR = (
        FIXTURES / "accounts" / "example_user" / "tweets" / "2026" / "2026-07"
        / "20260701_120000_9876543210"
    )

    def test_media_verified_false_when_media_missing(self, tmp_path: Path):
        out = tmp_path / "bundle"
        build_bundle(self.DIRTY_DIR, out)
        data = json.loads((out / "bundle.json").read_text("utf-8"))
        # The dirty fixture has a media entry referencing a file that doesn't exist
        assert data["trust_flags"]["media_verified"] is False

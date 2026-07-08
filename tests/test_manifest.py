"""Tests for the manifest builder (tools/scripts/build_manifest.py).

Covers:
  - Module-level build_manifest() with the good fixture
  - File inventory completeness and hashing
  - Transform chain inference
  - Trust flags correctness
  - Summary aggregation
  - Schema validation
  - CLI smoke test
  - Error handling for invalid directories
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

# conftest.py adds tools/scripts to sys.path
from build_manifest import (
    GENERATOR_NAME,
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    build_manifest,
    _classify_file,
    _sha256_file,
    _strip_at,
    _infer_platform,
    _build_citation_label,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOOD_DIR = (
    FIXTURES / "accounts" / "example_user" / "tweets" / "2026" / "2026-07"
    / "20260708_180000_1234567890"
)


# ── build_manifest() integration ──────────────────────────────────────────

class TestBuildManifest:
    """Integration tests using the good fixture directory."""

    def test_writes_manifest_json(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        build_manifest(d, write=True)
        assert (d / MANIFEST_FILENAME).is_file()

    def test_manifest_has_required_fields(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        required = (
            "manifest_version", "item_id", "source_platform", "source_url",
            "captured_at", "generated_at", "generator", "files", "transforms",
            "trust_flags", "summary",
        )
        for key in required:
            assert key in m, f"Missing required field: {key}"

    def test_manifest_version_is_1_0(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["manifest_version"] == MANIFEST_VERSION
        assert m["manifest_version"] == "1.0"

    def test_generator_name(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["generator"] == GENERATOR_NAME

    def test_item_id_matches_tweet_id(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["item_id"] == "1234567890"

    def test_source_platform_is_x(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["source_platform"] == "x"

    def test_source_url_present(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert "x.com" in m["source_url"]

    def test_author_handle_without_at(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["author_handle"] == "example_user"
        assert not m["author_handle"].startswith("@")


# ── File inventory ────────────────────────────────────────────────────────

class TestFileInventory:
    """Tests for the file inventory section."""

    def test_includes_tweet_json(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        paths = [f["path"] for f in m["files"]]
        assert "tweet.json" in paths

    def test_includes_media_files(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        paths = [f["path"] for f in m["files"]]
        assert "media/images/01.png" in paths
        assert "media/images/02.png" in paths

    def test_includes_export_files(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        paths = [f["path"] for f in m["files"]]
        assert "exports/article_md.pdf" in paths
        assert "exports/article_md_extract.json" in paths

    def test_excludes_manifest_from_inventory(self, tmp_path: Path):
        """manifest.json should not be in its own file inventory."""
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        # First run writes manifest.json
        build_manifest(d, write=True)
        # Second run should still exclude manifest.json
        m = build_manifest(d, write=False)
        paths = [f["path"] for f in m["files"]]
        assert MANIFEST_FILENAME not in paths

    def test_all_files_have_sha256(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        for f in m["files"]:
            assert len(f["sha256"]) == 64
            assert all(c in "0123456789abcdef" for c in f["sha256"])

    def test_sha256_matches_actual_file(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        for f in m["files"]:
            actual = hashlib.sha256(
                (d / f["path"]).read_bytes()
            ).hexdigest()
            assert f["sha256"] == actual

    def test_all_files_have_size_bytes(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        for f in m["files"]:
            assert f["size_bytes"] > 0

    def test_export_files_have_derived_from(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        exports = [f for f in m["files"] if f["kind"] == "export"]
        assert len(exports) > 0
        for f in exports:
            assert "derived_from" in f
            assert "tweet.json" in f["derived_from"]

    def test_file_kinds_classified(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        kinds = {f["kind"] for f in m["files"]}
        assert "metadata" in kinds
        assert "media" in kinds
        assert "export" in kinds


# ── Transform chain ───────────────────────────────────────────────────────

class TestTransforms:
    """Tests for the transform chain inference."""

    def test_capture_always_present(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        steps = [t["step"] for t in m["transforms"]]
        assert "capture" in steps

    def test_manifest_step_always_last(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["transforms"][-1]["step"] == "manifest"

    def test_article_md_present_when_exports_exist(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        steps = [t["step"] for t in m["transforms"]]
        assert "article_md" in steps

    def test_pdf_derived_from_extract_not_itself(self, tmp_path: Path):
        """The article_pdf transform input should be the extract.json,
        not the PDF file itself."""
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        pdf_transform = [
            t for t in m["transforms"] if t["step"] == "article_pdf"
        ]
        if pdf_transform:
            inputs = pdf_transform[0]["inputs"]
            # Input should NOT be a .pdf file
            assert all(not i.endswith(".pdf") for i in inputs)

    def test_capture_outputs_include_media(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        capture = [t for t in m["transforms"] if t["step"] == "capture"][0]
        outputs = capture["outputs"]
        assert "tweet.json" in outputs
        # Media files should be in capture outputs
        media_outputs = [o for o in outputs if o.startswith("media/")]
        assert len(media_outputs) > 0

    def test_all_transforms_have_ids(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        for t in m["transforms"]:
            assert "id" in t
            assert len(t["id"]) > 0

    def test_all_transforms_have_status(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        for t in m["transforms"]:
            assert t["status"] in ("success", "warning", "error", "skipped")


# ── Trust flags ───────────────────────────────────────────────────────────

class TestTrustFlags:
    """Tests for the trust flags."""

    def test_has_metadata_true_for_good_fixture(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["trust_flags"]["has_metadata"] is True

    def test_has_media_true_for_good_fixture(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["trust_flags"]["has_media"] is True

    def test_has_exports_true_for_good_fixture(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["trust_flags"]["has_exports"] is True

    def test_has_ocr_false_for_good_fixture(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["trust_flags"]["has_ocr"] is False

    def test_all_files_hashed_true(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["trust_flags"]["all_files_hashed"] is True

    def test_media_verified_true(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["trust_flags"]["media_verified"] is True


# ── Summary ───────────────────────────────────────────────────────────────

class TestSummary:
    """Tests for the summary aggregation."""

    def test_total_files_matches_inventory(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["summary"]["total_files"] == len(m["files"])

    def test_total_bytes_matches_sum(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        expected = sum(f["size_bytes"] for f in m["files"])
        assert m["summary"]["total_bytes"] == expected

    def test_media_count_matches(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        expected = sum(1 for f in m["files"] if f["kind"] == "media")
        assert m["summary"]["media_count"] == expected

    def test_export_count_matches(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        expected = sum(1 for f in m["files"] if f["kind"] == "export")
        assert m["summary"]["export_count"] == expected

    def test_transform_count_matches(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        m = build_manifest(d, write=False)
        assert m["summary"]["transform_count"] == len(m["transforms"])


# ── Edge cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_raises_on_nonexistent_dir(self, tmp_path: Path):
        with pytest.raises(NotADirectoryError):
            build_manifest(tmp_path / "nonexistent")

    def test_raises_on_dir_without_tweet_json(self, tmp_path: Path):
        d = tmp_path / "empty"
        d.mkdir()
        (d / "random.txt").write_text("hello")
        with pytest.raises(NotADirectoryError):
            build_manifest(d)

    def test_empty_item_dir(self, tmp_path: Path):
        """An item dir with only tweet.json should produce a valid manifest."""
        d = tmp_path / "item"
        d.mkdir()
        tweet = {
            "tweet_id": "999",
            "tweet_url": "https://x.com/user/status/999",
            "datetime_utc": "2026-07-09T10:00:00Z",
            "author_handle": "user",
            "text": "Hello",
            "media": [],
        }
        (d / "tweet.json").write_text(json.dumps(tweet))
        m = build_manifest(d, write=False)
        assert m["item_id"] == "999"
        assert m["trust_flags"]["has_media"] is False
        assert m["summary"]["total_files"] == 1
        assert m["summary"]["media_count"] == 0

    def test_dry_run_does_not_write(self, tmp_path: Path):
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        build_manifest(d, write=False)
        assert not (d / MANIFEST_FILENAME).exists()

    def test_handles_item_with_ocr(self, tmp_path: Path):
        """An item with OCR files should set has_ocr=True."""
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        ocr_dir = d / "ocr"
        ocr_dir.mkdir(exist_ok=True)
        (ocr_dir / "01.txt").write_text("OCR text content")
        m = build_manifest(d, write=False)
        assert m["trust_flags"]["has_ocr"] is True


# ── Helper functions ──────────────────────────────────────────────────────

class TestHelpers:
    """Tests for internal helper functions."""

    def test_classify_tweet_json(self):
        assert _classify_file("tweet.json") == "metadata"

    def test_classify_manifest_json(self):
        assert _classify_file("manifest.json") == "manifest"

    def test_classify_media_image(self):
        assert _classify_file("media/images/01.png") == "media"

    def test_classify_media_video(self):
        assert _classify_file("media/video/clip.mp4") == "media"

    def test_classify_media_raw(self):
        assert _classify_file("media/raw/original.mov") == "media_raw"

    def test_classify_export(self):
        assert _classify_file("exports/article.pdf") == "export"

    def test_classify_ocr(self):
        assert _classify_file("ocr/01.txt") == "ocr"

    def test_classify_article_md(self):
        assert _classify_file("articles/article.md") == "article"

    def test_classify_other(self):
        assert _classify_file("notes.txt") == "other"

    def test_sha256_file(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert _sha256_file(f) == expected

    def test_strip_at(self):
        assert _strip_at("@user") == "user"
        assert _strip_at("user") == "user"
        assert _strip_at("") == ""

    def test_infer_platform_x(self):
        assert _infer_platform("https://x.com/user/status/1") == "x"

    def test_infer_platform_twitter(self):
        assert _infer_platform("https://twitter.com/user/status/1") == "twitter"

    def test_infer_platform_web(self):
        assert _infer_platform("https://example.com/page") == "web"

    def test_infer_platform_empty(self):
        assert _infer_platform("") == "web"

    def test_build_citation_label(self):
        meta = {"author_handle": "user", "datetime_utc": "2026-07-08T18:00:00Z"}
        assert _build_citation_label(meta) == "@user, 2026-07-08"

    def test_build_citation_label_no_date(self):
        meta = {"author_handle": "user", "datetime_utc": ""}
        assert _build_citation_label(meta) == "@user"

    def test_build_citation_label_empty(self):
        assert _build_citation_label({}) == ""


# ── CLI smoke test ────────────────────────────────────────────────────────

class TestCLISmoke:
    """Smoke test for the manifest CLI subcommand."""

    def test_manifest_via_cli(self, tmp_path: Path):
        """Run `x_media_ci manifest --tweet-dir <path>` via subprocess."""
        import subprocess
        d = shutil.copytree(GOOD_DIR, tmp_path / "item")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "x_media_ci.py"),
                "manifest",
                "--tweet-dir", str(d),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert (d / MANIFEST_FILENAME).is_file()
        # Verify the written manifest is valid JSON
        data = json.loads((d / MANIFEST_FILENAME).read_text("utf-8"))
        assert data["manifest_version"] == "1.0"

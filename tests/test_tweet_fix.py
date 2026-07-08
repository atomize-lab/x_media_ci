"""Tests for ``tweet_fix.py`` - fuzzy fix-up of tweet.json files.

Verifies that ``plan_fix`` detects issues, ``apply_fix`` writes changes,
and the dry-run vs apply distinction works correctly.
"""
from __future__ import annotations

import json
from pathlib import Path

from tweet_fix import apply_fix, plan_fix, FixChange, FixReport


# ── plan_fix: detection ─────────────────────────────────────────────────────

class TestPlanFix:
    def test_detects_at_prefix_in_handle(self, dirty_tweet_dir: Path):
        report = plan_fix(dirty_tweet_dir)
        handle_changes = [c for c in report.changes if c.path == "author_handle"]
        assert len(handle_changes) == 1
        assert handle_changes[0].before == "@example_user"
        assert handle_changes[0].after == "example_user"

    def test_no_changes_on_good_tweet(self, good_tweet_dir: Path):
        report = plan_fix(good_tweet_dir)
        assert report.has_changes is False

    def test_report_for_non_tweet_dir(self, tmp_path: Path):
        report = plan_fix(tmp_path)
        assert report.has_changes is False
        assert any("not a tweet dir" in n for n in report.notes)

    def test_report_for_invalid_json(self, tmp_path: Path):
        (tmp_path / "tweet.json").write_text("{broken", encoding="utf-8")
        report = plan_fix(tmp_path)
        assert report.has_changes is False
        assert any("invalid" in n.lower() for n in report.notes)


# ── apply_fix: writing ──────────────────────────────────────────────────────

class TestApplyFix:
    def test_strips_at_prefix_and_writes(self, dirty_tweet_dir: Path, tmp_path: Path):
        """Apply fix on a COPY to avoid mutating the committed fixture."""
        import shutil
        dst = tmp_path / "dirty_copy"
        shutil.copytree(dirty_tweet_dir, dst)

        report = apply_fix(dst)
        assert report.has_changes is True

        # Verify the file was actually written
        meta = json.loads((dst / "tweet.json").read_text(encoding="utf-8"))
        assert meta["author_handle"] == "example_user"
        assert not meta["author_handle"].startswith("@")

    def test_apply_is_idempotent(self, dirty_tweet_dir: Path, tmp_path: Path):
        """Running apply_fix twice should produce no changes the second time."""
        import shutil
        dst = tmp_path / "dirty_copy"
        shutil.copytree(dirty_tweet_dir, dst)

        apply_fix(dst)
        report2 = apply_fix(dst)
        assert report2.has_changes is False

    def test_apply_on_good_tweet_no_changes(self, good_tweet_dir: Path, tmp_path: Path):
        """Apply on a copy of the good fixture should produce no changes."""
        import shutil
        dst = tmp_path / "good_copy"
        shutil.copytree(good_tweet_dir, dst)

        original = (dst / "tweet.json").read_text(encoding="utf-8")
        report = apply_fix(dst)
        assert report.has_changes is False
        assert (dst / "tweet.json").read_text(encoding="utf-8") == original


# ── media path resolution ───────────────────────────────────────────────────

class TestMediaPathFix:
    def test_resolves_media_prefix_path(self, tmp_tweet_dir: Path):
        """``media/images/01.png`` should resolve to bare ``01.png``."""
        # Create media file
        img_dir = tmp_tweet_dir / "media" / "images"
        img_dir.mkdir(parents=True)
        (img_dir / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        meta = {
            "tweet_id": "123",
            "tweet_url": "https://x.com/test/status/123",
            "author_handle": "test",
            "datetime_utc": "2026-07-08T10:00:00Z",
            "media": [{"file": "media/images/photo.png", "type": "image"}],
        }
        (tmp_tweet_dir / "tweet.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )

        report = plan_fix(tmp_tweet_dir)
        media_changes = [c for c in report.changes if "media" in c.path]
        assert len(media_changes) == 1
        assert media_changes[0].after == "photo.png"


# ── FixChange / FixReport rendering ─────────────────────────────────────────

class TestFixRendering:
    def test_change_render_with_note(self):
        c = FixChange(path="media[0].file", before="a/b.png", after="b.png",
                      note="resolved")
        rendered = c.render()
        assert "media[0].file" in rendered
        assert "a/b.png" in rendered
        assert "b.png" in rendered
        assert "resolved" in rendered

    def test_change_render_without_note(self):
        c = FixChange(path="author_handle", before="@x", after="x")
        rendered = c.render()
        assert "author_handle" in rendered
        assert "(@x" not in rendered  # no note suffix

    def test_report_has_changes_property(self, tmp_path: Path):
        r = FixReport(tweet_dir=tmp_path)
        assert r.has_changes is False
        r.changes.append(FixChange("a", "b", "c"))
        assert r.has_changes is True

"""Tests for the synthetic sample archive generator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# scripts/ is importable via conftest or path tweak
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tools" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from sample_archive import generate_archive, generate_item, main as sample_main  # noqa: E402
from tweet_schema import validate_tweet_dir  # noqa: E402


def test_generate_item_valid(tmp_path: Path):
    d = generate_item(tmp_path, 0, with_media=True)
    assert (d / "tweet.json").is_file()
    assert (d / "media" / "images" / "01.png").is_file()
    report = validate_tweet_dir(d)
    assert report.ok, [i.render() for i in report.errors]


def test_generate_archive_count(tmp_path: Path):
    out = tmp_path / "sample-archive"
    dirs = generate_archive(out, count=4, validate=True)
    assert len(dirs) == 4
    assert all((d / "tweet.json").is_file() for d in dirs)
    # first item has media
    meta0 = json.loads((dirs[0] / "tweet.json").read_text(encoding="utf-8"))
    assert meta0["media"]
    # later items can be text-only
    meta1 = json.loads((dirs[1] / "tweet.json").read_text(encoding="utf-8"))
    assert meta1["author_handle"] == "demo_user"
    assert not meta1["author_handle"].startswith("@")


def test_cli_sample_main(tmp_path: Path):
    out = tmp_path / "cli-out"
    rc = sample_main(["--output", str(out), "--count", "2"])
    assert rc == 0
    accounts = out / "accounts"
    assert accounts.is_dir()
    tweet_jsons = list(accounts.rglob("tweet.json"))
    assert len(tweet_jsons) == 2


def test_citeseal_sample_subcommand(tmp_path: Path):
    """Smoke: unified CLI wires sample → sample_archive.py."""
    sys.path.insert(0, str(ROOT / "tools"))
    from citeseal import build_parser  # type: ignore

    parser = build_parser()
    ns = parser.parse_args(["sample", "--output", str(tmp_path / "x"), "--count", "1"])
    assert ns.command == "sample"
    assert callable(ns.func)

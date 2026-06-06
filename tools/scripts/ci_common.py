"""Shared helpers for the x_media CI tools.

This module is intentionally tiny and dependency-free so that any of the
existing scripts can ``from ci_common import ...`` without breaking the
``python path/to/script.py`` invocation style.

Conventions used across the CI tools:

* Tweet content lives under::

      <CI_ROOT>/accounts/<handle>/tweets/YYYY/YYYY-MM/<ts>_<tweet_id>/

* Exports live in ``exports/`` of the tweet directory; media in ``media/``.
* ``tweet.json`` is the single source of truth for metadata.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


MEDIA_SUBDIRS = ("images", "video", "audio", "raw")
EXPORTS_DIRNAME = "exports"
TWEET_JSON_NAME = "tweet.json"


@dataclass(frozen=True)
class TweetPaths:
    """Resolved paths for a single tweet directory."""

    root: Path
    images_dir: Path
    video_dir: Path
    audio_dir: Path
    raw_dir: Path
    exports_dir: Path
    tweet_json: Path

    @property
    def handle(self) -> str:
        # .../accounts/<handle>/tweets/...
        try:
            return self.root.parts[-4]
        except IndexError:
            return ""

    def extract_json(self) -> Optional[Path]:
        """Return the most relevant *extract.json* inside ``exports/``."""
        if not self.exports_dir.exists():
            return None
        # Prefer non-OCR extract if present, else OCR one.
        candidates = sorted(self.exports_dir.glob("article_*_extract.json"))
        candidates = [p for p in candidates if "_ocr_" not in p.name]
        if candidates:
            return candidates[0]
        ocr = sorted(self.exports_dir.glob("article_*_ocr_extract.json"))
        if ocr:
            return ocr[0]
        return None

    def ocr_txt(self) -> Optional[Path]:
        if not self.exports_dir.exists():
            return None
        candidates = sorted(self.exports_dir.glob("article_*_ocr_full.txt"))
        return candidates[0] if candidates else None


def is_tweet_dir(path: Path) -> bool:
    """A tweet dir is recognized by a ``tweet.json`` file inside it."""
    return path.is_dir() and (path / TWEET_JSON_NAME).is_file()


def find_tweet_dirs(root: Path) -> list[Path]:
    """Recursively find all tweet directories under ``root``.

    A directory qualifies when it contains ``tweet.json``.
    """
    if not root.exists():
        return []
    out: list[Path] = []
    for p in root.rglob(TWEET_JSON_NAME):
        if p.is_file():
            out.append(p.parent)
    out.sort()
    return out


def tweet_paths(tweet_dir: Path) -> TweetPaths:
    media_dir = tweet_dir / "media"
    return TweetPaths(
        root=tweet_dir,
        images_dir=media_dir / "images",
        video_dir=media_dir / "video",
        audio_dir=media_dir / "audio",
        raw_dir=media_dir / "raw",
        exports_dir=tweet_dir / EXPORTS_DIRNAME,
        tweet_json=tweet_dir / TWEET_JSON_NAME,
    )


def load_tweet_meta(tweet_dir: Path) -> dict:
    """Load and return the ``tweet.json`` content (empty dict if missing)."""
    p = tweet_dir / TWEET_JSON_NAME
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def safe_filename(name: str) -> str:
    """Make ``name`` safe to embed in a filename across platforms."""
    name = name.strip() or "untitled"
    # Replace path separators and a few problematic characters.
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", name)
    # Avoid trailing dots/spaces (Windows would refuse them).
    name = name.rstrip(" .")
    return name or "untitled"


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for p in paths:
        if p and p.is_file():
            return p
    return None


def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable (``1/true/yes`` on, else off)."""
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "y")

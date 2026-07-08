"""Export an archived item as a self-describing agent bundle.

An agent bundle is a directory containing:

* ``bundle.json`` — the manifest with metadata, text, provenance, and asset list
* ``media/`` — copied media files (images, video, audio, raw)
* ``article.md`` — article markdown (if available)
* ``ocr_text.txt`` — full OCR text (if available)
* ``tweet.json`` — the original source metadata (for reference)

The bundle is designed for direct consumption by AI agents (Claude, Hermes,
Codex, etc.) without needing to understand the project's internal directory
layout.

Usage (as a script)::

    python tools/scripts/build_agent_bundle.py \\
        --tweet-dir tests/fixtures/.../20260708_180000_1234567890 \\
        --output my_bundle

Usage (as a module)::

    from build_agent_bundle import build_bundle
    build_bundle(tweet_dir=Path("..."), output_dir=Path("..."))
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Support both ``from ci_common import ...`` and direct script execution.
try:
    from ci_common import (
        TWEET_JSON_NAME,
        is_tweet_dir,
        load_tweet_meta,
        tweet_paths,
    )
except ImportError:
    _here = Path(__file__).resolve().parent
    sys.path.insert(0, str(_here))
    from ci_common import (  # type: ignore[no-redef]
        TWEET_JSON_NAME,
        is_tweet_dir,
        load_tweet_meta,
        tweet_paths,
    )


BUNDLE_VERSION = "1.0"
EXPORT_TOOL_NAME = "x_media_ci build_agent_bundle"
MAX_EXCERPT_CHARS = 280


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_bundle(
    tweet_dir: Path,
    output_dir: Path,
    *,
    max_excerpt: int = MAX_EXCERPT_CHARS,
    hash_media: bool = False,
    overwrite: bool = True,
) -> Path:
    """Build an agent bundle from a tweet directory.

    Args:
        tweet_dir: Source tweet directory (must contain ``tweet.json``).
        output_dir: Destination directory for the bundle.
        max_excerpt: Maximum character length for ``text_excerpt``.
        hash_media: If True, compute SHA-256 hashes for media files.
        overwrite: If True (default), remove existing output_dir first.

    Returns:
        Path to the written ``bundle.json``.

    Raises:
        NotADirectoryError: If ``tweet_dir`` is not a valid tweet directory.
    """
    tweet_dir = tweet_dir.resolve()
    if not is_tweet_dir(tweet_dir):
        raise NotADirectoryError(
            f"Not a valid tweet directory (missing {TWEET_JSON_NAME}): {tweet_dir}"
        )

    output_dir = output_dir.resolve()
    if overwrite and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    meta = load_tweet_meta(tweet_dir)
    tp = tweet_paths(tweet_dir)

    # --- Text ---
    full_text = meta.get("text", "")
    excerpt, text_full = _build_excerpt(full_text, max_excerpt)

    # --- Media ---
    media_entries, media_verified = _collect_media(meta, tp, output_dir, hash_media)

    # --- OCR ---
    ocr_text = _read_ocr(tp)

    # --- Article ---
    article_md_path = _copy_article(tp, output_dir)

    # --- Copy original tweet.json ---
    src_json = tp.tweet_json
    dst_json = output_dir / TWEET_JSON_NAME
    shutil.copy2(src_json, dst_json)

    # --- Build asset list ---
    assets = _build_asset_list(output_dir, media_entries, article_md_path, ocr_text)

    # --- Trust flags ---
    trust_flags = {
        "validated": _check_validated(tweet_dir),
        "has_media": len(media_entries) > 0,
        "has_ocr": bool(ocr_text),
        "has_article": article_md_path is not None,
        "media_verified": media_verified,
    }

    # --- Citation label ---
    citation_label = _build_citation_label(meta)

    # --- Provenance ---
    provenance = {
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "export_tool": f"{EXPORT_TOOL_NAME} v0.1.0",
        "source_dir": str(tweet_dir),
    }

    # --- Bundle ---
    bundle: dict = {
        "bundle_version": BUNDLE_VERSION,
        "item_id": str(meta.get("tweet_id", "")),
        "source_platform": _infer_platform(meta.get("tweet_url", "")),
        "source_url": meta.get("tweet_url", ""),
        "captured_at": meta.get("datetime_utc", ""),
        "author_handle": (meta.get("author_handle", "") or "").lstrip("@"),
        "text_excerpt": excerpt,
        "assets": assets,
        "provenance": provenance,
        "trust_flags": trust_flags,
    }

    if text_full:
        bundle["text_full"] = text_full
    if media_entries:
        bundle["media"] = media_entries
    if ocr_text:
        bundle["ocr_text"] = ocr_text
    if article_md_path:
        bundle["article_md_path"] = article_md_path
    if citation_label:
        bundle["citation_label"] = citation_label

    # Related items from replies
    related = _extract_related(meta)
    if related:
        bundle["related_items"] = related

    # --- Write bundle.json ---
    bundle_json_path = output_dir / "bundle.json"
    bundle_json_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )

    # --- Self-check: verify all referenced files exist ---
    _self_check(output_dir, bundle)

    return bundle_json_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_excerpt(full_text: str, max_chars: int) -> tuple[str, Optional[str]]:
    """Return (excerpt, text_full_or_None)."""
    if not full_text:
        return "", None
    if len(full_text) <= max_chars:
        return full_text, None
    return full_text[:max_chars] + "...", full_text


def _collect_media(
    meta: dict, tp, output_dir: Path, hash_media: bool
) -> tuple[list[dict], bool]:
    """Copy media files into the bundle and return media entries.

    Returns (entries, all_verified).
    """
    media_list = meta.get("media") or []
    if not isinstance(media_list, list):
        return [], False

    entries: list[dict] = []
    all_verified = True
    bundle_media_dir = output_dir / "media"
    bundle_media_dir.mkdir(exist_ok=True)

    for idx, m in enumerate(media_list):
        if not isinstance(m, dict):
            all_verified = False
            continue

        rel = m.get("file", "")
        if not rel:
            all_verified = False
            continue

        # Resolve source path
        src = _resolve_media_source(rel, tp)
        if src is None or not src.is_file():
            all_verified = False
            continue

        # Copy into bundle
        dst = bundle_media_dir / src.name
        # Handle name collisions
        if dst.exists() and dst != src:
            stem, suffix = src.stem, src.suffix
            dst = bundle_media_dir / f"{stem}_{idx}{suffix}"
        if dst != src:
            shutil.copy2(src, dst)

        entry: dict = {
            "file": rel,
            "type": m.get("type", "image"),
            "path": f"media/{dst.name}",
        }
        alt = m.get("alt_text")
        if alt:
            entry["alt_text"] = alt
        if hash_media:
            entry["sha256"] = _sha256(dst)
        entries.append(entry)

    return entries, all_verified


def _resolve_media_source(rel: str, tp) -> Optional[Path]:
    """Find the actual media file on disk given a media[].file value."""
    # media/images/01.png  ->  tp.root / media / images / 01.png
    if "/" in rel or "\\" in rel:
        p = (tp.root / rel).resolve()
        if p.is_file():
            return p
        # Also try stripping media/<sub>/ prefix
        for sub in ("images", "video", "audio", "raw"):
            prefix = f"media/{sub}/"
            if rel.startswith(prefix):
                p2 = (tp.root / "media" / sub / rel[len(prefix):]).resolve()
                if p2.is_file():
                    return p2
        return None

    # Bare filename: search in media subdirs
    for sub in ("images", "video", "audio", "raw"):
        p = (tp.root / "media" / sub / rel).resolve()
        if p.is_file():
            return p
    return None


def _read_ocr(tp) -> str:
    """Read OCR text from the tweet's exports directory, if available."""
    ocr_path = tp.ocr_txt()
    if ocr_path and ocr_path.is_file():
        return ocr_path.read_text(encoding="utf-8")
    return ""


def _copy_article(tp, output_dir: Path) -> Optional[str]:
    """Copy article markdown into the bundle, return relative path or None."""
    # Look for article_md.md or similar in exports/
    if not tp.exports_dir.exists():
        return None
    candidates = sorted(tp.exports_dir.glob("article_md*.md"))
    if not candidates:
        candidates = sorted(tp.exports_dir.glob("*.md"))
    if not candidates:
        return None
    src = candidates[0]
    dst = output_dir / "article.md"
    if src != dst:
        shutil.copy2(src, dst)
    return "article.md"


def _build_asset_list(
    output_dir: Path,
    media_entries: list[dict],
    article_md_path: Optional[str],
    ocr_text: str,
) -> list[dict]:
    """Scan the output directory and build the assets list."""
    assets: list[dict] = []
    for p in sorted(output_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(output_dir).as_posix()
        kind = _classify_asset(rel, p.name)
        entry: dict = {"path": rel, "kind": kind}
        try:
            entry["size_bytes"] = p.stat().st_size
        except OSError:
            pass
        assets.append(entry)
    return assets


def _classify_asset(rel_path: str, filename: str) -> str:
    if rel_path == "bundle.json":
        return "manifest"
    if rel_path == TWEET_JSON_NAME:
        return "metadata"
    if rel_path == "article.md":
        return "article"
    if rel_path == "ocr_text.txt":
        return "ocr"
    if rel_path.startswith("media/"):
        return "media"
    if rel_path.startswith("exports/"):
        return "export"
    return "context"


def _check_validated(tweet_dir: Path) -> bool:
    """Check if the tweet.json passes basic structural validation.

    We do a lightweight check here rather than importing the full validator,
    to avoid circular imports. The full validator is run separately in CI.
    """
    meta = load_tweet_meta(tweet_dir)
    required = ("tweet_id", "tweet_url", "author_handle", "datetime_utc")
    return all(meta.get(k) for k in required)


def _build_citation_label(meta: dict) -> str:
    handle = (meta.get("author_handle", "") or "").lstrip("@")
    dt = meta.get("datetime_utc", "")
    date_part = dt[:10] if dt else ""
    if handle and date_part:
        return f"@{handle}, {date_part}"
    if handle:
        return f"@{handle}"
    return ""


def _extract_related(meta: dict) -> list[dict]:
    """Extract related items from replies field."""
    replies = meta.get("replies") or []
    if not isinstance(replies, list):
        return []
    related = []
    for r in replies:
        if isinstance(r, dict) and r.get("tweet_id"):
            related.append({
                "item_id": str(r["tweet_id"]),
                "relation": "reply",
            })
        elif isinstance(r, str):
            related.append({"item_id": r, "relation": "reply"})
    return related


def _infer_platform(url: str) -> str:
    if "x.com" in url:
        return "x"
    if "twitter.com" in url:
        return "twitter"
    return "web"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _self_check(output_dir: Path, bundle: dict) -> None:
    """Verify that all file paths referenced in the bundle exist on disk."""
    # Check media paths
    for m in bundle.get("media") or []:
        p = output_dir / m["path"]
        if not p.is_file():
            raise FileNotFoundError(
                f"Self-check failed: media file missing in bundle: {m['path']}"
            )
    # Check article path
    article = bundle.get("article_md_path")
    if article and not (output_dir / article).is_file():
        raise FileNotFoundError(
            f"Self-check failed: article file missing in bundle: {article}"
        )
    # Check all assets exist
    for a in bundle.get("assets") or []:
        p = output_dir / a["path"]
        if not p.is_file():
            raise FileNotFoundError(
                f"Self-check failed: asset missing in bundle: {a['path']}"
            )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="build_agent_bundle",
        description="Export a tweet directory as an agent bundle.",
    )
    parser.add_argument(
        "--tweet-dir",
        type=Path,
        required=True,
        help="Source tweet directory (must contain tweet.json).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output directory for the agent bundle.",
    )
    parser.add_argument(
        "--max-excerpt",
        type=int,
        default=MAX_EXCERPT_CHARS,
        help=f"Maximum text excerpt length (default: {MAX_EXCERPT_CHARS}).",
    )
    parser.add_argument(
        "--hash-media",
        action="store_true",
        help="Compute SHA-256 hashes for media files.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not remove existing output directory before writing.",
    )

    args = parser.parse_args(argv)

    try:
        bundle_path = build_bundle(
            tweet_dir=args.tweet_dir,
            output_dir=args.output,
            max_excerpt=args.max_excerpt,
            hash_media=args.hash_media,
            overwrite=not args.no_overwrite,
        )
    except (NotADirectoryError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    file_count = sum(1 for _ in bundle_path.parent.rglob("*") if _.is_file())
    print(f"Agent bundle written to: {bundle_path}")
    print(f"  Files in bundle: {file_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

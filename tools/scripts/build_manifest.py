"""Generate a provenance manifest for an archived item.

A manifest records:

* **Files** — every file in the item directory, classified and hashed (SHA-256).
* **Transforms** — the processing chain from capture to export.
* **Trust flags** — quick booleans for data-quality assessment.
* **Summary** — aggregate counts and sizes.

The manifest is written to ``manifest.json`` in the item directory and can
be consumed by AI agents or audit workflows to verify provenance.

Usage::

    python tools/scripts/build_manifest.py <tweet_dir>
    python tools/scripts/build_manifest.py <tweet_dir> --pretty
    python tools/scripts/build_manifest.py <tweet_dir> --dry-run

The manifest is also exposed as a library function ``build_manifest()``
for programmatic use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Support both ``from ci_common import ...`` and direct script execution.
try:
    from ci_common import (
        TWEET_JSON_NAME,
        is_tweet_dir,
        load_tweet_meta,
    )
except ImportError:
    _here = Path(__file__).resolve().parent
    sys.path.insert(0, str(_here))
    from ci_common import (  # type: ignore[no-redef]
        TWEET_JSON_NAME,
        is_tweet_dir,
        load_tweet_meta,
    )


MANIFEST_VERSION = "1.0"
GENERATOR_NAME = "citeseal build_manifest"
MANIFEST_FILENAME = "manifest.json"

# File kind classification based on path relative to item directory.
_KIND_MAP = {
    "tweet.json": "metadata",
    "manifest.json": "manifest",
}
# Subdirectory prefixes -> file kind
_PREFIX_KIND_MAP = {
    "media/images/": "media",
    "media/video/": "media",
    "media/audio/": "media",
    "media/raw/": "media_raw",
    "exports/": "export",
    "ocr/": "ocr",
    "articles/": "article",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_manifest(
    item_dir: Path,
    *,
    pretty: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    """Build a provenance manifest for an item directory.

    Args:
        item_dir: Path to the tweet/item directory (must contain tweet.json).
        pretty: If True, indent JSON output.
        write: If True, write manifest.json to item_dir. If False, only return the dict.

    Returns:
        The manifest as a dictionary.

    Raises:
        NotADirectoryError: If item_dir is not a valid tweet directory.
    """
    item_dir = Path(item_dir).resolve()

    if not is_tweet_dir(item_dir):
        raise NotADirectoryError(
            f"Not a valid tweet directory (missing tweet.json): {item_dir}"
        )

    meta = load_tweet_meta(item_dir)

    # Gather all files (excluding manifest.json itself if it already exists)
    all_files = _collect_files(item_dir)

    # Build file entries with hashes
    file_entries = []
    for rel_path, abs_path in all_files:
        entry = _build_file_entry(rel_path, abs_path, item_dir)
        file_entries.append(entry)

    # Infer transforms from file structure
    transforms = _infer_transforms(item_dir, meta, file_entries)

    # Build trust flags
    trust_flags = _build_trust_flags(item_dir, meta, file_entries)

    # Build citation label
    citation = _build_citation_label(meta)

    # Build summary
    summary = {
        "total_files": len(file_entries),
        "total_bytes": sum(f["size_bytes"] for f in file_entries),
        "media_count": sum(1 for f in file_entries if f["kind"] == "media"),
        "export_count": sum(1 for f in file_entries if f["kind"] == "export"),
        "transform_count": len(transforms),
    }

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "item_id": str(meta.get("tweet_id", "")),
        "source_platform": _infer_platform(meta.get("tweet_url", "")),
        "source_url": meta.get("tweet_url", ""),
        "captured_at": meta.get("datetime_utc", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": GENERATOR_NAME,
        "author_handle": _strip_at(meta.get("author_handle", "")),
        "citation_label": citation,
        "files": file_entries,
        "transforms": transforms,
        "components": meta.get("components", []),
        "trust_flags": trust_flags,
        "summary": summary,
    }

    if write:
        manifest_path = item_dir / MANIFEST_FILENAME
        indent = 2 if pretty else None
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=indent) + "\n",
            encoding="utf-8",
        )

    return manifest


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_files(item_dir: Path) -> list[tuple[str, Path]]:
    """Collect all files in the item directory, sorted by relative path.

    Returns list of (relative_path_str, absolute_path) tuples.
    Excludes manifest.json (we don't hash our own output).
    """
    result = []
    for f in sorted(item_dir.rglob("*")):
        if not f.is_file():
            continue
        # Skip .gitkeep files
        if f.name == ".gitkeep":
            continue
        rel = f.relative_to(item_dir).as_posix()
        # Skip existing manifest.json (will be overwritten)
        if rel == MANIFEST_FILENAME:
            continue
        result.append((rel, f))
    return result


def _classify_file(rel_path: str) -> str:
    """Classify a file by its relative path."""
    # Exact match first
    if rel_path in _KIND_MAP:
        return _KIND_MAP[rel_path]
    # Prefix match
    for prefix, kind in _PREFIX_KIND_MAP.items():
        if rel_path.startswith(prefix):
            return kind
    # Heuristic by extension
    ext = Path(rel_path).suffix.lower()
    if ext == ".json" and "ocr" not in rel_path:
        return "metadata"
    if ext == ".md":
        return "article"
    if ext == ".pdf":
        return "export"
    if ext == ".txt" and "ocr" in rel_path:
        return "ocr"
    return "other"


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_file_entry(
    rel_path: str, abs_path: Path, item_dir: Path
) -> dict[str, Any]:
    """Build a single file entry for the manifest."""
    entry: dict[str, Any] = {
        "path": rel_path,
        "kind": _classify_file(rel_path),
        "size_bytes": abs_path.stat().st_size,
        "sha256": _sha256_file(abs_path),
    }
    # Add derived_from if the file is in exports/
    if rel_path.startswith("exports/"):
        entry["derived_from"] = ["tweet.json"]
    return entry


def _infer_transforms(
    item_dir: Path,
    meta: dict[str, Any],
    file_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Infer the transform chain from the files present.

    Since we don't have runtime logs for past transforms, we infer them
    from the file structure. This is a best-effort reconstruction.
    """
    transforms: list[dict[str, Any]] = []
    captured_at = meta.get("datetime_utc", "")

    # Step 1: Capture (always present if tweet.json exists)
    media_files = [f for f in file_entries if f["kind"] == "media"]
    transforms.append({
        "id": "t1_capture",
        "step": "capture",
        "tool": "manual/fetch_x",
        "started_at": captured_at,
        "completed_at": captured_at,
        "status": "success",
        "inputs": [],
        "outputs": ["tweet.json"] + [f["path"] for f in media_files],
        "notes": "Original capture of tweet metadata and media.",
    })

    # Step 2: Article markdown (if article_md_extract.json or .md exists)
    article_files = [
        f for f in file_entries
        if f["kind"] == "export" and "article_md" in f["path"]
    ]
    if article_files:
        transforms.append({
            "id": "t2_article_md",
            "step": "article_md",
            "tool": "gen_article_md.py",
            "started_at": captured_at,
            "completed_at": captured_at,
            "status": "success",
            "inputs": ["tweet.json"],
            "outputs": [f["path"] for f in article_files],
            "notes": "Generated article markdown extract from tweet text.",
        })

    # Step 3: Article PDF (if .pdf exists in exports/)
    pdf_files = [
        f for f in file_entries
        if f["kind"] == "export" and f["path"].endswith(".pdf")
    ]
    if pdf_files:
        # PDF is derived from the article_md_extract.json, not from itself
        md_json = [
            f for f in article_files
            if not f["path"].endswith(".pdf")
        ]
        md_output = md_json[0]["path"] if md_json else "tweet.json"
        transforms.append({
            "id": "t3_article_pdf",
            "step": "article_pdf",
            "tool": "make_article_pdf.py",
            "started_at": captured_at,
            "completed_at": captured_at,
            "status": "success",
            "inputs": [md_output],
            "outputs": [f["path"] for f in pdf_files],
            "notes": "Rendered article markdown to PDF.",
        })

    # Step 4: OCR (if ocr text files exist)
    ocr_files = [f for f in file_entries if f["kind"] == "ocr"]
    if ocr_files:
        transforms.append({
            "id": "t4_ocr",
            "step": "ocr",
            "tool": "write_ocr_exports.py",
            "started_at": captured_at,
            "completed_at": captured_at,
            "status": "success",
            "inputs": [f["path"] for f in media_files],
            "outputs": [f["path"] for f in ocr_files],
            "notes": "OCR extraction from media images.",
        })

    # Step 5: Transcode (if video files exist in media/video/)
    video_files = [
        f for f in file_entries
        if f["kind"] == "media" and f["path"].startswith("media/video/")
    ]
    if video_files:
        raw_files = [
            f for f in file_entries if f["kind"] == "media_raw"
        ]
        transforms.append({
            "id": "t5_transcode",
            "step": "transcode",
            "tool": "transcode_to_mp4.py",
            "started_at": captured_at,
            "completed_at": captured_at,
            "status": "success",
            "inputs": [f["path"] for f in raw_files] or ["(raw media)"],
            "outputs": [f["path"] for f in video_files],
            "notes": "Transcoded raw video to MP4.",
        })

    # Step 6: Manifest (this run)
    transforms.append({
        "id": "t_manifest",
        "step": "manifest",
        "tool": GENERATOR_NAME,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "inputs": [f["path"] for f in file_entries],
        "outputs": [MANIFEST_FILENAME],
        "notes": "Generated this provenance manifest.",
    })

    return transforms


def _build_trust_flags(
    item_dir: Path,
    meta: dict[str, Any],
    file_entries: list[dict[str, Any]],
) -> dict[str, bool]:
    """Build trust flags from the file inventory and metadata."""
    kinds = {f["kind"] for f in file_entries}

    # Check if all declared media files exist
    declared_media = meta.get("media") or []
    media_verified = True
    for m in declared_media:
        mfile = m.get("file", "")
        # Find the media file in the inventory
        found = any(
            f["path"].endswith(mfile) for f in file_entries
        )
        if not found:
            media_verified = False
            break

    return {
        "has_metadata": "metadata" in kinds or TWEET_JSON_NAME in [f["path"] for f in file_entries],
        "has_media": "media" in kinds,
        "has_exports": "export" in kinds,
        "has_ocr": "ocr" in kinds,
        "has_article": "article" in kinds,
        "media_verified": media_verified if declared_media else True,
        "all_files_hashed": all(f.get("sha256") for f in file_entries),
    }


def _build_citation_label(meta: dict[str, Any]) -> str:
    """Build a human-readable citation label."""
    handle = _strip_at(meta.get("author_handle", ""))
    dt = meta.get("datetime_utc", "")
    if dt:
        date_part = dt[:10]  # YYYY-MM-DD
    else:
        date_part = ""
    if handle and date_part:
        return f"@{handle}, {date_part}"
    elif handle:
        return f"@{handle}"
    return ""


def _strip_at(handle: str) -> str:
    """Strip leading @ from a handle."""
    return handle.lstrip("@")


def _infer_platform(url: str) -> str:
    """Infer platform from URL."""
    if not url:
        return "web"
    if "x.com" in url:
        return "x"
    if "twitter.com" in url:
        return "twitter"
    return "web"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a provenance manifest for an archived item."
    )
    parser.add_argument(
        "tweet_dir",
        help="Path to the tweet/item directory (must contain tweet.json).",
    )
    parser.add_argument(
        "--pretty", action="store_true", default=True,
        help="Pretty-print JSON output (default: true).",
    )
    parser.add_argument(
        "--no-pretty", dest="pretty", action="store_false",
        help="Compact JSON output.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print manifest to stdout without writing to disk.",
    )
    args = parser.parse_args(argv)

    item_dir = Path(args.tweet_dir)
    if not item_dir.is_dir():
        print(f"Error: not a directory: {item_dir}", file=sys.stderr)
        return 1

    try:
        manifest = build_manifest(
            item_dir,
            pretty=args.pretty,
            write=not args.dry_run,
        )
    except NotADirectoryError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        indent = 2 if args.pretty else None
        print(json.dumps(manifest, ensure_ascii=False, indent=indent))
    else:
        manifest_path = item_dir / MANIFEST_FILENAME
        file_count = manifest["summary"]["total_files"]
        print(f"Manifest written to: {manifest_path}")
        print(f"  Files inventoried: {file_count}")
        print(f"  Transforms: {manifest['summary']['transform_count']}")
        print(f"  Total size: {manifest['summary']['total_bytes']:,} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())

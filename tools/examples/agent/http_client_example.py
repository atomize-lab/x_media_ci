#!/usr/bin/env python3
"""Fetch and display an agent bundle via the local HTTP server.

Prerequisites:
    1. Start the local server:  cs serve
    2. Have at least one archived item in the CI root.

Usage:
    python http_client_example.py
    python http_client_example.py --handle example_user --tweet-id 1234567890
    python http_client_example.py --base-url http://localhost:8000

This script uses only the Python standard library (no pip install needed).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime


def fetch_bundle(base_url: str, handle: str, tweet_id: str) -> dict:
    """Fetch a bundle from the local server."""
    url = f"{base_url.rstrip('/')}/agent-bundle/{handle}/{tweet_id}"
    print(f"Fetching: {url}", file=sys.stderr)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        if e.code == 404:
            print("Hint: Make sure the server is running and the item exists.",
                  file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}", file=sys.stderr)
        print("Hint: Start the server with 'cs serve' first.", file=sys.stderr)
        sys.exit(1)


def display_bundle(bundle: dict) -> None:
    """Pretty-print key fields from a bundle."""
    print("=" * 60)
    print("  Agent Bundle Summary")
    print("=" * 60)
    print()

    print(f"  Item ID       : {bundle.get('item_id', 'N/A')}")
    print(f"  Platform      : {bundle.get('source_platform', 'N/A')}")
    print(f"  Source URL    : {bundle.get('source_url', 'N/A')}")
    print(f"  Author        : @{bundle.get('author_handle', 'N/A')}")
    print(f"  Captured at   : {bundle.get('captured_at', 'N/A')}")
    print(f"  Citation      : {bundle.get('citation_label', 'N/A')}")
    print()

    # Text
    excerpt = bundle.get("text_excerpt", "")
    print("[Text]")
    print(f"  {excerpt}")
    if bundle.get("text_full") and bundle["text_full"] != excerpt:
        print(f"  (full text available in text_full field)")
    print()

    # Media
    media = bundle.get("media") or []
    if media:
        print(f"[Media] ({len(media)} item(s))")
        for m in media:
            sha = m.get("sha256", "")[:12] + "..." if m.get("sha256") else "N/A"
            print(f"  {m['type']:8s} {m['file']:20s} sha256={sha}")
    else:
        print("[Media] None")
    print()

    # Trust flags
    flags = bundle.get("trust_flags") or {}
    print("[Trust Flags]")
    for key in ("validated", "has_media", "has_ocr", "has_article",
                "media_verified"):
        val = flags.get(key, False)
        status = "[OK]" if val else "[--]"
        print(f"  {status} {key}")
    print()

    # Provenance
    prov = bundle.get("provenance") or {}
    print("[Provenance]")
    print(f"  Exported at  : {prov.get('exported_at', 'N/A')}")
    print(f"  Export tool  : {prov.get('export_tool', 'N/A')}")
    print(f"  Source dir   : {prov.get('source_dir', 'N/A')}")
    print()

    # Assets
    assets = bundle.get("assets") or []
    print(f"[Assets] ({len(assets)} file(s))")
    for a in assets:
        size = a.get("size_bytes", 0)
        size_str = f"{size:,} bytes" if size else "N/A"
        print(f"  {a['kind']:10s} {a['path']:30s} {size_str}")
    print()

    # Related items
    related = bundle.get("related_items") or []
    if related:
        print(f"[Related Items] ({len(related)})")
        for r in related:
            print(f"  {r['relation']:8s} {r['item_id']}")
    else:
        print("[Related Items] None")
    print()

    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and display an agent bundle from the local server."
    )
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Base URL of the citeseal server.")
    parser.add_argument("--handle", default="example_user",
                        help="Author handle (without @).")
    parser.add_argument("--tweet-id", default="1234567890",
                        help="Tweet ID to fetch.")
    parser.add_argument("--raw", action="store_true",
                        help="Print raw JSON instead of formatted summary.")
    args = parser.parse_args(argv)

    bundle = fetch_bundle(args.base_url, args.handle, args.tweet_id)

    if args.raw:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        display_bundle(bundle)

    return 0


if __name__ == "__main__":
    sys.exit(main())

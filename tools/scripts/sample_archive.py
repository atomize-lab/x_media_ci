"""Generate a small synthetic CiteSeal archive for demos and onboarding.

Creates fully synthetic items (no real social media content) so new users can
try ``cs serve``, ``cs export-agent``, and ``cs manifest`` without capturing
anything first.

Usage:
    python tools/scripts/sample_archive.py --output ./sample-archive --count 3
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as a script from tools/ or tools/scripts/
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ci_common import MEDIA_SUBDIRS  # noqa: E402
from tweet_schema import validate_tweet_dir  # noqa: E402


HANDLE = "demo_user"
DEFAULT_COUNT = 3


def _placeholder_png(path: Path) -> None:
    """Write a minimal valid 1x1 PNG (no external deps)."""
    # 1x1 transparent PNG
    data = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )
    path.write_bytes(data)


def _item_dir(root: Path, handle: str, dt: datetime, tweet_id: str) -> Path:
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    return (
        root
        / "accounts"
        / handle
        / "tweets"
        / dt.strftime("%Y")
        / dt.strftime("%Y-%m")
        / f"{stamp}_{tweet_id}"
    )


def generate_item(
    root: Path,
    index: int,
    handle: str = HANDLE,
    with_media: bool = False,
    base_time: datetime | None = None,
) -> Path:
    """Create one synthetic tweet directory under *root*."""
    base = base_time or datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    dt = base + timedelta(days=index, hours=index)
    tweet_id = str(10_000_000_000 + index)
    tweet_dir = _item_dir(root, handle, dt, tweet_id)
    tweet_dir.mkdir(parents=True, exist_ok=True)

    media_root = tweet_dir / "media"
    for sub in MEDIA_SUBDIRS:
        (media_root / sub).mkdir(parents=True, exist_ok=True)
    (tweet_dir / "exports").mkdir(parents=True, exist_ok=True)

    media_entries: list[dict] = []
    if with_media:
        img = media_root / "images" / "01.png"
        _placeholder_png(img)
        media_entries.append({"file": "01.png", "type": "image", "alt_text": "sample placeholder"})

    meta = {
        "tweet_id": tweet_id,
        "tweet_url": f"https://x.com/{handle}/status/{tweet_id}",
        "author_handle": handle,
        "datetime_utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datetime_local": (dt + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "text": (
            f"[SYNTHETIC] Sample archive item #{index + 1} for CiteSeal demos. "
            f"This is not real social media content. #citeseal #sample"
        ),
        "media": media_entries,
        "exports": [],
        "components": ["text"] + (["images"] if with_media else []),
        "replies": [],
    }
    (tweet_dir / "tweet.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return tweet_dir


def generate_archive(
    output: Path,
    count: int = DEFAULT_COUNT,
    handle: str = HANDLE,
    validate: bool = True,
) -> list[Path]:
    """Generate *count* synthetic items under *output* and optionally validate."""
    if count < 1:
        raise ValueError("count must be >= 1")
    output = output.expanduser().resolve()
    if output.exists():
        # Only wipe if it looks like a previous sample archive
        accounts = output / "accounts"
        if accounts.is_dir():
            shutil.rmtree(accounts)
    output.mkdir(parents=True, exist_ok=True)

    dirs: list[Path] = []
    for i in range(count):
        # First item always includes a placeholder image
        dirs.append(generate_item(output, i, handle=handle, with_media=(i == 0)))

    if validate:
        errors = 0
        for d in dirs:
            report = validate_tweet_dir(d)
            if not report.ok:
                errors += 1
                for issue in report.errors:
                    print(f"  {issue.render()}", file=sys.stderr)
        if errors:
            raise SystemExit(f"sample archive validation failed for {errors} item(s)")

    return dirs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("./sample-archive"),
        help="Output directory (default: ./sample-archive)",
    )
    ap.add_argument(
        "--count",
        "-n",
        type=int,
        default=DEFAULT_COUNT,
        help="Number of synthetic items (default: 3)",
    )
    ap.add_argument(
        "--handle",
        default=HANDLE,
        help=f"Synthetic author handle (default: {HANDLE})",
    )
    ap.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip tweet_validate on generated items",
    )
    args = ap.parse_args(argv)

    dirs = generate_archive(
        args.output,
        count=args.count,
        handle=args.handle.lstrip("@"),
        validate=not args.no_validate,
    )
    print(f"Generated {len(dirs)} sample item(s) under {args.output.resolve()}")
    for d in dirs:
        print(f"  - {d}")
    print("Try: python tools/citeseal.py validate --root", args.output / "accounts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

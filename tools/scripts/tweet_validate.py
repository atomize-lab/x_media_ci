"""CLI wrapper around :mod:`tweet_schema` so the unified CLI can call it.

Standalone usage:

    python tools/scripts/tweet_validate.py <tweet_dir> [<tweet_dir> ...]
    python tools/scripts/tweet_validate.py --root <accounts_root> [--strict]

Exit codes:
    0  all OK
    1  one or more errors found
    2  invalid arguments / I/O error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ci_common import find_tweet_dirs
from tweet_schema import validate_tweet_dir


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", help="Recursively validate every tweet dir under ROOT.")
    ap.add_argument("dirs", nargs="*", help="One or more tweet directories.")
    ap.add_argument("--strict", action="store_true",
                    help="Treat warnings as errors for the exit code.")
    ap.add_argument("--quiet", action="store_true",
                    help="Only print tweet dirs that have issues.")
    args = ap.parse_args(argv)

    if not args.root and not args.dirs:
        ap.error("one of --root or DIRS is required")

    if args.root:
        root = Path(args.root).expanduser().resolve()
        if not root.is_dir():
            print(f"ERROR: --root is not a directory: {root}", file=sys.stderr)
            return 2
        targets = find_tweet_dirs(root)
        if not targets:
            print(f"No tweet dirs under: {root}", file=sys.stderr)
            return 0
    else:
        targets = [Path(d).expanduser().resolve() for d in args.dirs]

    total_errors = 0
    total_warnings = 0
    bad = 0
    for td in targets:
        report = validate_tweet_dir(td)
        total_errors += len(report.errors)
        total_warnings += len(report.warnings)
        if not report.ok:
            bad += 1
        if report.issues and not args.quiet:
            print(f"\n== {td}")
            for issue in report.issues:
                print("   " + issue.render())

    summary = (
        f"\nSummary: {len(targets)} dirs | "
        f"{total_errors} error(s) | {total_warnings} warning(s) | "
        f"{bad} dir(s) with errors"
    )
    print(summary)
    if total_errors:
        return 1
    if args.strict and total_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

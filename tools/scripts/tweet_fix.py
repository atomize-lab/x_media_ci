"""Fuzzy-fix ``tweet.json`` files so they match the CI conventions.

The "convention" we normalize to is:

* ``media[*].file`` is the file **name** (no ``media/<sub>/`` prefix)
* ``exports[*].file`` is the file **name** (no ``exports/`` prefix)
* ``author_handle`` does **not** start with ``@``

For media files we resolve the actual on-disk location under the known
subdirectories (``media/{images,video,audio,raw}``) and only re-write the
field if a unique match is found. Ambiguous matches are left alone and
reported.

The fix is **safe by default** — pass ``--apply`` to actually write
changes; otherwise only a report is printed.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ci_common import (
    EXPORTS_DIRNAME,
    MEDIA_SUBDIRS,
    find_tweet_dirs,
    is_tweet_dir,
    load_tweet_meta,
)


@dataclass
class FixChange:
    path: str          # JSON path like "media[3].file"
    before: str
    after: str
    note: str = ""

    def render(self) -> str:
        extra = f"  ({self.note})" if self.note else ""
        return f"  {self.path}: {self.before!r} -> {self.after!r}{extra}"


@dataclass
class FixReport:
    tweet_dir: Path
    changes: list[FixChange] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)


# ---------------------------------------------------------------------------
# Per-field fixers
# ---------------------------------------------------------------------------

def _fix_media_files(tweet_dir: Path, media: list, report: FixReport) -> None:
    for idx, m in enumerate(media):
        if not isinstance(m, dict):
            continue
        rel = m.get("file")
        if not isinstance(rel, str) or not rel:
            continue

        # Already a bare filename -> nothing to do.
        if "/" not in rel and "\\" not in rel:
            # But make sure the file actually exists somewhere known.
            if not any((tweet_dir / "media" / sub / rel).is_file()
                       for sub in MEDIA_SUBDIRS):
                report.notes.append(
                    f"media[{idx}].file={rel!r}: bare name not found under media/*"
                )
            continue

        # Normalize Windows path separators.
        norm = rel.replace("\\", "/")
        # Try to locate the file under known media subdirs.
        resolved: Optional[Path] = None
        if norm.startswith("media/"):
            tail = norm[len("media/"):]
            for sub in MEDIA_SUBDIRS:
                if tail.startswith(f"{sub}/"):
                    candidate = tweet_dir / "media" / sub / tail[len(sub) + 1:]
                    if candidate.is_file():
                        resolved = candidate
                        break
        if resolved is None:
            # As a last resort, take the basename and look for it under any subdir.
            base = norm.rsplit("/", 1)[-1]
            hits = []
            for sub in MEDIA_SUBDIRS:
                p = tweet_dir / "media" / sub / base
                if p.is_file():
                    hits.append(p)
            if len(hits) == 1:
                resolved = hits[0]
            elif len(hits) > 1:
                report.notes.append(
                    f"media[{idx}].file={rel!r}: ambiguous basename, "
                    f"found under {len(hits)} subdirs; left unchanged"
                )
                continue
            else:
                report.notes.append(
                    f"media[{idx}].file={rel!r}: cannot resolve on disk; left unchanged"
                )
                continue

        new_rel = resolved.name
        if new_rel != rel:
            report.changes.append(FixChange(
                path=f"media[{idx}].file",
                before=rel,
                after=new_rel,
                note=f"resolved to {resolved.relative_to(tweet_dir)}",
            ))
            m["file"] = new_rel


def _fix_exports_files(tweet_dir: Path, exports: list, report: FixReport) -> None:
    for idx, e in enumerate(exports):
        if not isinstance(e, dict):
            continue
        rel = e.get("file")
        if not isinstance(rel, str) or not rel:
            continue
        norm = rel.replace("\\", "/")
        if not norm.startswith(f"{EXPORTS_DIRNAME}/"):
            # bare name or different shape — leave alone (user might store
            # exports in another location on purpose)
            continue
        tail = norm[len(EXPORTS_DIRNAME) + 1:]
        candidate = tweet_dir / EXPORTS_DIRNAME / tail
        if not candidate.is_file():
            report.notes.append(
                f"exports[{idx}].file={rel!r}: not found on disk; left unchanged"
            )
            continue
        if tail != rel:
            report.changes.append(FixChange(
                path=f"exports[{idx}].file",
                before=rel,
                after=tail,
                note=f"resolved to exports/{tail}",
            ))
            e["file"] = tail


def _fix_author_handle(meta: dict, report: FixReport) -> None:
    h = meta.get("author_handle")
    if isinstance(h, str) and h.startswith("@"):
        new = h.lstrip("@")
        report.changes.append(FixChange(
            path="author_handle",
            before=h,
            after=new,
            note="strip leading '@'",
        ))
        meta["author_handle"] = new


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def plan_fix(tweet_dir: Path) -> FixReport:
    """Return a :class:`FixReport` describing what *would* change."""
    report = FixReport(tweet_dir=tweet_dir)
    if not is_tweet_dir(tweet_dir):
        report.notes.append("not a tweet dir (missing tweet.json)")
        return report

    meta = load_tweet_meta(tweet_dir)
    if not meta:
        report.notes.append("tweet.json missing or invalid JSON")
        return report

    _fix_author_handle(meta, report)
    if isinstance(meta.get("media"), list):
        _fix_media_files(tweet_dir, meta["media"], report)
    if isinstance(meta.get("exports"), list):
        _fix_exports_files(tweet_dir, meta["exports"], report)
    return report


def apply_fix(tweet_dir: Path) -> FixReport:
    """Compute the plan and, if non-empty, write the file back to disk."""
    report = plan_fix(tweet_dir)
    if report.has_changes and (tweet_dir / "tweet.json").is_file():
        out = tweet_dir / "tweet.json"
        meta = json.loads(out.read_text(encoding="utf-8"))
        # Re-run plan against the on-disk meta so we mutate the right object.
        _fix_author_handle(meta, report)
        if isinstance(meta.get("media"), list):
            _fix_media_files(tweet_dir, meta["media"], report)
        if isinstance(meta.get("exports"), list):
            _fix_exports_files(tweet_dir, meta["exports"], report)
        out.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--root", help="Recursively fix every tweet dir under ROOT.")
    g.add_argument("dirs", nargs="*", help="One or more tweet directories.")
    ap.add_argument("--apply", action="store_true",
                    help="Actually write changes (default: dry run).")
    ap.add_argument("--quiet", action="store_true",
                    help="Only print tweet dirs that have changes.")
    args = ap.parse_args(argv)

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

    total_changes = 0
    total_notes = 0
    changed_dirs = 0
    runner = apply_fix if args.apply else plan_fix
    mode = "APPLY" if args.apply else "DRY-RUN"
    for td in targets:
        r = runner(td)
        total_changes += len(r.changes)
        total_notes += len(r.notes)
        if r.has_changes:
            changed_dirs += 1
        if (r.changes or r.notes) and not args.quiet:
            print(f"\n== [{mode}] {td}")
            for c in r.changes:
                print(c.render())
            for n in r.notes:
                print(f"  note: {n}")

    print(
        f"\nSummary [{mode}]: {len(targets)} dirs | "
        f"{total_changes} change(s) | {total_notes} note(s) | "
        f"{changed_dirs} dir(s) with changes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Unified CLI entry point for the CiteSeal tools.

This script does **not** re-implement the existing helpers; it delegates
to them by spawning them as subprocesses (using ``sys.executable``) so the
original ``python tools/scripts/foo.py --flag value`` usage continues to
work unchanged.

Typical usage (from anywhere)::

    python tools/citeseal.py md   --tweet-dir <...>/<tweet_id_dir>
    python tools/citeseal.py pdf  --tweet-dir <...>
    python tools/citeseal.py ocr  --tweet-dir <...> --screenshots-glob 'media/images/*.png'
    python tools/citeseal.py all  --tweet-dir <...>

Run ``python tools/citeseal.py --help`` for the full sub-command list.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

# Make the bundled ``scripts/`` package importable when this file is run
# directly (``python tools/citeseal.py``).
_HERE = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HERE / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ci_common import (  # noqa: E402  (sys.path tweak above)
    ensure_dir,
    find_tweet_dirs,
    is_tweet_dir,
    load_tweet_meta,
    tweet_paths,
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _python_executable() -> str:
    """Prefer the current interpreter; fall back to ``python`` on PATH."""
    return sys.executable or "python"


def _run_script(script: str, args: Sequence[str], *, cwd: Optional[Path] = None) -> int:
    """Run ``tools/scripts/<script>.py`` with the given args and stream output."""
    cmd = [_python_executable(), str(_SCRIPTS_DIR / script), *args]
    pretty = " ".join(shlex.quote(c) for c in cmd)
    print(f"[citeseal] $ {pretty}", file=sys.stderr)
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    return proc.returncode


def _ensure_extract_json(tp, args: argparse.Namespace) -> Optional[Path]:
    extract = tp.extract_json()
    if extract and extract.is_file():
        return extract

    meta = load_tweet_meta(tp.root)
    if not meta:
        return None

    ensure_dir(tp.exports_dir)

    text = (meta.get("text") or "").strip()
    first_line = ""
    if text:
        first_line = (text.splitlines()[0] or "").strip()
    if first_line and len(first_line) > 80:
        first_line = first_line[:80].rstrip() + "…"
    tweet_id = meta.get("tweet_id") or tp.root.name.split("_")[-1]
    arg_title = getattr(args, "title", None)
    arg_url = getattr(args, "url", None)
    arg_author = getattr(args, "author", None)
    arg_dt_utc = getattr(args, "datetime_utc", None)

    title = arg_title or meta.get("title") or (first_line if first_line else f"Tweet {tweet_id}")
    url = arg_url or meta.get("tweet_url") or meta.get("url", "")
    author = arg_author or meta.get("author_handle", "")
    dt_utc = arg_dt_utc or meta.get("datetime_utc", "")

    nodes: list[dict] = []
    if text:
        for para in text.split("\n\n"):
            p = para.strip()
            if p:
                nodes.append({"type": "p", "text": p})

    media = meta.get("media") or []
    for m in media:
        if not isinstance(m, dict):
            continue
        if m.get("type") == "image" and m.get("source_url"):
            nodes.append({"type": "img", "src": str(m.get("source_url"))})

    extract_payload = {
        "title": title,
        "url": url,
        "author_handle": author,
        "datetime_utc": dt_utc,
        "nodes": nodes,
    }
    out = tp.exports_dir / f"article_{tp.root.name}_extract.json"
    out.write_text(json.dumps(extract_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _resolve_tweet_dir(arg: str) -> Path:
    """Accept either a tweet directory or a file that lives inside one."""
    p = Path(arg).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"tweet-dir does not exist: {p}")
    if is_tweet_dir(p):
        return p
    # Walk up until we find a tweet.json
    cur = p if p.is_dir() else p.parent
    for parent in [cur, *cur.parents]:
        if is_tweet_dir(parent):
            return parent
    raise SystemExit(
        f"Could not locate a tweet directory (no tweet.json) from: {p}"
    )


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_md(args: argparse.Namespace) -> int:
    tp = tweet_paths(args.tweet_dir)
    extract = args.extract or _ensure_extract_json(tp, args) or tp.extract_json()
    if not extract or not extract.is_file():
        print(f"[citeseal] skip (no extract.json): {args.tweet_dir}", file=sys.stderr)
        return 0
    out = args.out or (tp.exports_dir / f"{extract.stem.replace('_extract','')}_full.md")
    if out.exists() and not args.force:
        print(f"[citeseal] exists, pass --force to overwrite: {out}", file=sys.stderr)
        return 0
    return _run_script(
        "gen_article_md.py",
        ["--extract", str(extract), "--images-dir", str(tp.images_dir), "--out", str(out)],
        cwd=args.tweet_dir,
    )


def cmd_pdf(args: argparse.Namespace) -> int:
    tp = tweet_paths(args.tweet_dir)
    extract = args.extract or _ensure_extract_json(tp, args) or tp.extract_json()
    if not extract or not extract.is_file():
        print(f"[citeseal] skip (no extract.json): {args.tweet_dir}", file=sys.stderr)
        return 0
    out = args.out or (tp.exports_dir / f"{extract.stem.replace('_extract','')}_full.pdf")
    if out.exists() and not args.force:
        print(f"[citeseal] exists, pass --force to overwrite: {out}", file=sys.stderr)
        return 0
    return _run_script(
        "make_article_pdf.py",
        ["--extract", str(extract), "--images-dir", str(tp.images_dir), "--out", str(out)],
        cwd=args.tweet_dir,
    )


def cmd_ocr(args: argparse.Namespace) -> int:
    """Run the full OCR pipeline for a single tweet:

        screenshots glob -> ocr_screens_to_text -> make_ocr_extract -> write_ocr_exports
    """
    tp = tweet_paths(args.tweet_dir)
    glob = args.screenshots_glob
    if not glob:
        # Default: look for any image under media/images
        glob = "media/images/*.png"
    title, url, author, dt_utc = _meta_for_filename(args.tweet_dir, args)

    txt_out = tp.exports_dir / f"article_{tp.root.name}_ocr_full.txt"
    md_out = tp.exports_dir / f"article_{tp.root.name}_ocr_full.md"
    extract_out = tp.exports_dir / f"article_{tp.root.name}_ocr_extract.json"

    rc = _run_script(
        "ocr_screens_to_text.py",
        [
            "--glob", glob,
            "--out-txt", str(txt_out),
            "--out-md", str(md_out),
            "--title", title,
            "--url", url,
            "--author", author,
            "--datetime-utc", dt_utc,
        ],
        cwd=args.tweet_dir,
    )
    if rc != 0:
        return rc

    rc = _run_script(
        "make_ocr_extract.py",
        [
            "--ocr-txt", str(txt_out),
            "--out-json", str(extract_out),
            "--title", title,
            "--url", url,
            "--author", author,
            "--datetime-utc", dt_utc,
            "--screenshots-glob", glob,
        ],
        cwd=args.tweet_dir,
    )
    if rc != 0:
        return rc

    rc = _run_script(
        "write_ocr_exports.py",
        [
            "--ocr-txt", str(txt_out),
            "--out-md", str(md_out),
            "--out-txt", str(txt_out),
            "--title", title,
            "--url", url,
            "--author", author,
            "--datetime-utc", dt_utc,
            "--images-dir", str(tp.images_dir),
        ],
        cwd=args.tweet_dir,
    )
    return rc


def cmd_ocr_long(args: argparse.Namespace) -> int:
    return _run_script(
        "ocr_long_image.py",
        ["--image", args.image, "--out", args.out,
         "--chunk-height", str(args.chunk_height), "--overlap", str(args.overlap)],
        cwd=args.tweet_dir if getattr(args, "tweet_dir", None) else None,
    )


def cmd_ocr_md(args: argparse.Namespace) -> int:
    """Re-emit *ocr_full.md* / *ocr_full.txt* from an existing OCR txt."""
    tp = tweet_paths(args.tweet_dir)
    title, url, author, dt_utc = _meta_for_filename(args.tweet_dir, args)
    txt = args.ocr_txt or tp.ocr_txt()
    if not txt or not txt.is_file():
        raise SystemExit("No OCR txt found. Run `ocr` first or pass --ocr-txt.")
    md_out = args.out_md or (tp.exports_dir / f"{txt.stem.replace('_ocr_full.txt','')}_ocr_full.md")
    txt_out = args.out_txt or txt
    return _run_script(
        "write_ocr_exports.py",
        [
            "--ocr-txt", str(txt),
            "--out-md", str(md_out),
            "--out-txt", str(txt_out),
            "--title", title,
            "--url", url,
            "--author", author,
            "--datetime-utc", dt_utc,
            "--images-dir", str(tp.images_dir),
        ],
        cwd=args.tweet_dir,
    )


def cmd_all(args: argparse.Namespace) -> int:
    """md + pdf + (optionally) ocr in one shot for a single tweet."""
    for fn in (cmd_md, cmd_pdf):
        rc = fn(args)
        if rc != 0 and not args.keep_going:
            return rc
    if args.with_ocr:
        rc = cmd_ocr(args)
        if rc != 0 and not args.keep_going:
            return rc
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Iterate over every tweet dir under a root and run a sub-command."""
    root = Path(args.root).expanduser().resolve()
    tweet_dirs = find_tweet_dirs(root)
    if not tweet_dirs:
        print(f"[citeseal] no tweet dirs under {root}", file=sys.stderr)
        return 1
    failures = 0
    for td in tweet_dirs:
        sub_args = argparse.Namespace(
            tweet_dir=td,
            extract=getattr(args, "extract", None),
            out=getattr(args, "out", None),
            out_md=getattr(args, "out_md", None),
            out_txt=getattr(args, "out_txt", None),
            ocr_txt=getattr(args, "ocr_txt", None),
            screenshots_glob=getattr(args, "screenshots_glob", None),
            title=getattr(args, "title", None),
            url=getattr(args, "url", None),
            author=getattr(args, "author", None),
            datetime_utc=getattr(args, "datetime_utc", None),
            force=getattr(args, "force", False),
            with_ocr=getattr(args, "with_ocr", False),
            keep_going=True,
            image=None,
            chunk_height=2200,
            overlap=220,
        )
        rc = args.handler(sub_args)
        if rc != 0:
            failures += 1
            print(f"[citeseal] FAIL {td} rc={rc}", file=sys.stderr)
    return 0 if failures == 0 else 2


# ---------------------------------------------------------------------------
# Meta helpers
# ---------------------------------------------------------------------------

def _meta_for_filename(tweet_dir: Path, args: argparse.Namespace) -> tuple[str, str, str, str]:
    """Return (title, url, author, datetime_utc) for filename templates.

    Values come from explicit CLI args, else from ``tweet.json`` if present,
    else fall back to safe defaults derived from the directory name.
    """
    meta = load_tweet_meta(tweet_dir)
    title = args.title or meta.get("title") or f"X Article {tweet_dir.name}"
    url = args.url or meta.get("tweet_url") or meta.get("url", "")
    author = args.author or meta.get("author_handle", "")
    dt_utc = args.datetime_utc or meta.get("datetime_utc", "")
    return title, url, author, dt_utc


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------

def _add_io_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--tweet-dir", required=True,
                   help="Path to a single tweet directory (containing tweet.json).")
    p.add_argument("--extract", help="Override path to the extract.json file.")
    p.add_argument("--out", help="Override output path.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite the output file if it already exists.")


def _add_meta_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--title", help="Override article title (default: from tweet.json).")
    p.add_argument("--url", help="Override article URL (default: from tweet.json).")
    p.add_argument("--author", help="Override author handle (default: from tweet.json).")
    p.add_argument("--datetime-utc", help="Override UTC datetime (default: from tweet.json).")


def cmd_lint(args: argparse.Namespace) -> int:
    """Run ``pyflakes`` on the bundled scripts and report issues.

    pyflakes is an optional dev dependency; if missing we return a clear
    error code so CI pipelines can surface it.
    """
    import shutil

    pyflakes = shutil.which("pyflakes") or shutil.which("pyflakes3")
    if not pyflakes:
        print(
            "[citeseal] pyflakes not found. Install with:\n"
            "    python -m pip install pyflakes",
            file=sys.stderr,
        )
        return 2

    cmd = [pyflakes, str(_SCRIPTS_DIR), str(_HERE / "citeseal.py")]
    pretty = " ".join(shlex.quote(c) for c in cmd)
    print(f"[citeseal] $ {pretty}", file=sys.stderr)
    proc = subprocess.run(cmd)
    return proc.returncode


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check environment: Python version, external tools, and project layout.

    Reports which optional dependencies are present and which are missing.
    Exits 0 if all critical checks pass, 1 if any critical check fails.
    """
    import platform
    import shutil
    import importlib

    print("=" * 60)
    print("  citeseal doctor - environment diagnostics")
    print("=" * 60)
    print()

    errors = 0
    warnings = 0

    # --- Python version ---
    print("[Python]")
    print(f"  Executable : {sys.executable}")
    print(f"  Version    : {platform.python_version()}")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        print(f"  [!] Python 3.10+ recommended (you have {major}.{minor})")
        warnings += 1
    else:
        print(f"  [OK] Python {major}.{minor} meets minimum (3.10)")
    print()

    # --- External tools ---
    print("[External tools]")
    tools_check = [
        ("ffmpeg", "Video transcoding (optional)", "critical_optional"),
        ("ffprobe", "Media probing (optional)", "critical_optional"),
        ("playwright", "Web capture via Playwright", "critical_optional"),
        ("adb", "Android device bridge (Flutter dev only)", "optional"),
    ]

    for name, desc, severity in tools_check:
        path = shutil.which(name)
        if path:
            # Get version if possible
            try:
                result = subprocess.run(
                    [name, "-version"], capture_output=True, text=True, timeout=5
                )
                version_line = result.stdout.split("\n")[0].strip()[:60]
                print(f"  [OK] {name:12s} {version_line}")
            except Exception:
                print(f"  [OK] {name:12s} found at {path}")
        else:
            if severity == "critical_optional":
                print(f"  [X] {name:12s} NOT FOUND — {desc}")
                warnings += 1
            else:
                print(f"  - {name:12s} not found — {desc}")
    print()

    # --- Python packages ---
    print("[Python packages]")
    packages_check = [
        ("pyflakes", "Linting (dev)", True),
        ("pytest", "Testing (dev)", True),
        ("fastapi", "Local API server", False),
        ("uvicorn", "ASGI server", False),
        ("PIL", "Image processing (Pillow)", False),
        ("fitz", "PDF generation (PyMuPDF)", False),
    ]

    for modname, desc, is_dev in packages_check:
        try:
            importlib.import_module(modname)
            print(f"  [OK] {modname:12s} — {desc}")
        except ImportError:
            label = "(dev)" if is_dev else ""
            print(f"  [X] {modname:12s} NOT FOUND — {desc} {label}")
            if is_dev:
                warnings += 1
            else:
                # Non-dev packages are only needed for specific features
                warnings += 1
    print()

    # --- Playwright browsers ---
    print("[Playwright browsers]")
    try:
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as p:
                # Just check if chromium is available
                browser = p.chromium.launch(headless=True)
                browser.close()
            print("  [OK] Chromium browser installed")
        except Exception as e:
            print(f"  [X] Chromium browser not installed: {e}")
            print("    Run: python -m playwright install chromium")
            warnings += 1
    except ImportError:
        print("  - playwright module not installed (skipping browser check)")
    print()

    # --- Project layout ---
    print("[Project layout]")
    project_root = _HERE.parent  # tools/ -> project root
    layout_checks = [
        ("tools/citeseal.py", True),
        ("tools/scripts/ci_common.py", True),
        ("tools/scripts/tweet_schema.py", True),
        ("tools/scripts/tweet_validate.py", True),
        ("tools/server/app.py", False),
        ("tests/", True),
        ("tests/fixtures/", True),
        (".github/workflows/ci.yml", False),
    ]

    for rel_path, is_critical in layout_checks:
        full_path = project_root / rel_path
        exists = full_path.exists()
        if exists:
            print(f"  [OK] {rel_path}")
        else:
            if is_critical:
                print(f"  [X] {rel_path} MISSING (critical)")
                errors += 1
            else:
                print(f"  - {rel_path} (optional)")
    print()

    # --- Summary ---
    print("=" * 60)
    if errors > 0:
        print(f"  FAIL: {errors} critical error(s), {warnings} warning(s)")
        print("  Fix critical errors before proceeding.")
    elif warnings > 0:
        print(f"  PASS with warnings: {warnings} warning(s)")
        print("  Core functionality works. Install missing optional deps as needed.")
    else:
        print("  ALL CHECKS PASSED")
    print("=" * 60)

    return 1 if errors > 0 else 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate tweet.json files under a root (or for explicit dirs)."""
    sub_args = [
        *(["--root", str(Path(args.root).expanduser().resolve())] if args.root else []),
        *([str(d) for d in args.dirs]),
        *(["--strict"] if args.strict else []),
        *(["--quiet"] if args.quiet else []),
    ]
    return _run_script("tweet_validate.py", sub_args, cwd=args.root and Path(args.root))


def cmd_fix(args: argparse.Namespace) -> int:
    """Normalize tweet.json files (paths + author_handle) — dry run by default."""
    sub_args = [
        *(["--root", str(Path(args.root).expanduser().resolve())] if args.root else []),
        *([str(d) for d in args.dirs]),
        *(["--apply"] if args.apply else []),
        *(["--quiet"] if args.quiet else []),
    ]
    return _run_script("tweet_fix.py", sub_args, cwd=args.root and Path(args.root))


def cmd_transcode(args: argparse.Namespace) -> int:
    """Transcode media/* into phone-friendly MP4 (H.264 + AAC)."""
    sub_args = []
    if args.root:
        sub_args += ["--root", str(Path(args.root).expanduser().resolve())]
    if args.tweet_dir:
        sub_args += ["--tweet-dir", str(args.tweet_dir)]
    if args.src:
        sub_args += ["--in", str(args.src)]
    if args.dst:
        sub_args += ["--out", str(args.dst)]
    if args.apply:
        sub_args += ["--apply"]
    if args.force:
        sub_args += ["--force"]
    if args.probe:
        sub_args += ["--probe"]
    if args.verbose:
        sub_args += ["--verbose"]
    return _run_script("transcode_to_mp4.py", sub_args)


def cmd_export_agent(args: argparse.Namespace) -> int:
    """Export a tweet directory as an agent bundle."""
    sub_args = [
        "--tweet-dir", str(args.tweet_dir),
        "--output", str(args.output),
    ]
    if args.hash_media:
        sub_args.append("--hash-media")
    if args.no_overwrite:
        sub_args.append("--no-overwrite")
    if args.max_excerpt is not None:
        sub_args += ["--max-excerpt", str(args.max_excerpt)]
    return _run_script("build_agent_bundle.py", sub_args)


def cmd_manifest(args: argparse.Namespace) -> int:
    """Generate a provenance manifest for a tweet directory."""
    sub_args = [str(args.tweet_dir)]
    if args.dry_run:
        sub_args.append("--dry-run")
    if args.no_pretty:
        sub_args.append("--no-pretty")
    return _run_script("build_manifest.py", sub_args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="citeseal",
        description="Unified CLI for the CiteSeal tools (delegates to tools/scripts/*.py).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # md ----------------------------------------------------------------
    p_md = sub.add_parser("md", help="Generate *full.md* from an extract.json.")
    _add_io_args(p_md)
    p_md.set_defaults(func=cmd_md)

    # pdf ---------------------------------------------------------------
    p_pdf = sub.add_parser("pdf", help="Generate *full.pdf* from an extract.json.")
    _add_io_args(p_pdf)
    p_pdf.set_defaults(func=cmd_pdf)

    # ocr ---------------------------------------------------------------
    p_ocr = sub.add_parser(
        "ocr",
        help="Run the full OCR pipeline (screenshots -> txt/md -> ocr_extract.json).",
    )
    p_ocr.add_argument("--tweet-dir", required=True)
    p_ocr.add_argument("--screenshots-glob",
                       help="Glob (relative to tweet-dir) for screenshot images.")
    _add_meta_args(p_ocr)
    p_ocr.set_defaults(func=cmd_ocr)

    # ocr-md ------------------------------------------------------------
    p_ocrmd = sub.add_parser(
        "ocr-md",
        help="Re-emit *ocr_full.md* / *ocr_full.txt* from an existing OCR txt.",
    )
    p_ocrmd.add_argument("--tweet-dir", required=True)
    p_ocrmd.add_argument("--ocr-txt")
    p_ocrmd.add_argument("--out-md")
    p_ocrmd.add_argument("--out-txt")
    _add_meta_args(p_ocrmd)
    p_ocrmd.set_defaults(func=cmd_ocr_md)

    # ocr-long ----------------------------------------------------------
    p_long = sub.add_parser("ocr-long", help="OCR a single long screenshot by chunking.")
    p_long.add_argument("--image", required=True)
    p_long.add_argument("--out", required=True)
    p_long.add_argument("--chunk-height", type=int, default=2200)
    p_long.add_argument("--overlap", type=int, default=220)
    p_long.set_defaults(func=cmd_ocr_long)

    # all ---------------------------------------------------------------
    p_all = sub.add_parser("all", help="Run md + pdf (and optionally ocr) for a single tweet.")
    _add_io_args(p_all)
    p_all.add_argument("--with-ocr", action="store_true")
    p_all.add_argument("--screenshots-glob")
    p_all.add_argument("--keep-going", action="store_true")
    _add_meta_args(p_all)
    p_all.set_defaults(func=cmd_all)

    # batch -------------------------------------------------------------
    p_batch = sub.add_parser(
        "batch",
        help="Run md/pdf/all/ocr across every tweet directory under ROOT.",
    )
    p_batch.add_argument("--root", required=True,
                         help="Directory to recurse into (typically CI/accounts).")
    p_batch.add_argument("--op", choices=["md", "pdf", "all"], default="all")
    p_batch.add_argument("--with-ocr", action="store_true")
    p_batch.add_argument("--screenshots-glob")
    p_batch.add_argument("--force", action="store_true")
    _add_meta_args(p_batch)
    p_batch.set_defaults(func=lambda ns: _batch_dispatch(ns))

    # validate ---------------------------------------------------------
    p_val = sub.add_parser(
        "validate",
        help="Validate tweet.json files for a single dir, a list, or recursively under --root.",
    )
    p_val.add_argument("--root",
                       help="Recursively validate every tweet dir under ROOT.")
    p_val.add_argument("dirs", nargs="*", help="One or more tweet directories.")
    p_val.add_argument("--strict", action="store_true",
                       help="Treat warnings as errors for the exit code.")
    p_val.add_argument("--quiet", action="store_true",
                       help="Only print tweet dirs that have issues.")
    p_val.set_defaults(func=cmd_validate)

    # lint -------------------------------------------------------------
    p_lint = sub.add_parser(
        "lint",
        help="Run pyflakes over the bundled scripts and CLI entry point.",
    )
    p_lint.set_defaults(func=cmd_lint)

    # doctor -----------------------------------------------------------
    p_doc = sub.add_parser(
        "doctor",
        help="Check environment: Python, external tools, and project layout.",
    )
    p_doc.set_defaults(func=cmd_doctor)

    # fix ---------------------------------------------------------------
    p_fix = sub.add_parser(
        "fix",
        help="Normalize tweet.json (path conventions + author_handle). Dry-run by default.",
    )
    p_fix.add_argument("--root",
                       help="Recursively fix every tweet dir under ROOT.")
    p_fix.add_argument("dirs", nargs="*", help="One or more tweet directories.")
    p_fix.add_argument("--apply", action="store_true",
                       help="Write changes to disk (default: dry run).")
    p_fix.add_argument("--quiet", action="store_true",
                       help="Only print tweet dirs that have changes.")
    p_fix.set_defaults(func=cmd_fix)

    # transcode ---------------------------------------------------------
    p_tr = sub.add_parser(
        "transcode",
        help="Transcode media/* into phone-friendly MP4 (H.264 + AAC).",
    )
    g = p_tr.add_mutually_exclusive_group(required=False)
    g.add_argument("--root", help="Recurse every tweet dir under ROOT.")
    g.add_argument("--tweet-dir", help="Single tweet dir to process.")
    p_tr.add_argument("--in", dest="src", help="Single input file (with --out).")
    p_tr.add_argument("--out", dest="dst", help="Single output file (with --in).")
    p_tr.add_argument("--apply", action="store_true",
                      help="Actually run ffmpeg (default: dry run).")
    p_tr.add_argument("--force", action="store_true",
                      help="Transcode even when the source looks Android-friendly.")
    p_tr.add_argument("--probe", action="store_true",
                      help="Only print ffprobe info, do not transcode.")
    p_tr.add_argument("--verbose", action="store_true",
                      help="Print extra info for skipped files.")
    p_tr.set_defaults(func=cmd_transcode)

    # export-agent ------------------------------------------------------
    p_ea = sub.add_parser(
        "export-agent",
        help="Export a tweet directory as an agent bundle (bundle.json + media).",
    )
    p_ea.add_argument("--tweet-dir", required=True,
                      help="Source tweet directory (must contain tweet.json).")
    p_ea.add_argument("--output", "-o", required=True,
                      help="Output directory for the agent bundle.")
    p_ea.add_argument("--max-excerpt", type=int, default=None,
                      help="Maximum text excerpt length (default: 280).")
    p_ea.add_argument("--hash-media", action="store_true",
                      help="Compute SHA-256 hashes for media files.")
    p_ea.add_argument("--no-overwrite", action="store_true",
                      help="Do not remove existing output directory.")
    p_ea.set_defaults(func=cmd_export_agent)

    # manifest -----------------------------------------------------------
    p_man = sub.add_parser(
        "manifest",
        help="Generate a provenance manifest for a tweet directory.",
    )
    p_man.add_argument("--tweet-dir", required=True,
                       help="Source tweet directory (must contain tweet.json).")
    p_man.add_argument("--dry-run", action="store_true",
                       help="Print manifest to stdout without writing to disk.")
    p_man.add_argument("--no-pretty", action="store_true",
                       help="Compact JSON output.")
    p_man.set_defaults(func=cmd_manifest)

    return p


def _batch_dispatch(ns: argparse.Namespace) -> int:
    handler = {"md": cmd_md, "pdf": cmd_pdf, "all": cmd_all}[ns.op]
    return cmd_batch(argparse.Namespace(
        root=ns.root,
        handler=handler,
        extract=None,
        out=None,
        out_md=None,
        out_txt=None,
        ocr_txt=None,
        screenshots_glob=ns.screenshots_glob,
        title=ns.title,
        url=ns.url,
        author=ns.author,
        datetime_utc=ns.datetime_utc,
        force=ns.force,
        with_ocr=ns.with_ocr,
        keep_going=True,
    ))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "tweet_dir", None):
        args.tweet_dir = _resolve_tweet_dir(args.tweet_dir)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

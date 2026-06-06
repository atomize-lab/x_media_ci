"""Transcode media files to phone-friendly MP4 (H.264 + AAC).

The script wraps ``ffmpeg`` (must be on PATH) and supports:

* single-file mode: ``--in foo.mov --out foo.mp4``
* tweet-dir mode: recurse a tweet directory and transcode every
  ``media/video/`` and ``media/audio/`` file in place, writing
  ``*_transcoded.mp4`` siblings so we never overwrite the source.

By default we **only** transcode containers/codecs that are known to be
problematic on Android (``.mov``, ``.mkv``, ``.webm``, ``.m4a`` with
non-MP4 video, HEVC/H.265, etc.). Everything else is left untouched —
use ``--force`` to override.

Use ``--probe`` to only print the ffmpeg ``-i`` banner (dry run) and
``--apply`` to actually run the transcode.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ci_common import find_tweet_dirs, tweet_paths


VIDEO_EXTS = {".mov", ".mkv", ".webm", ".avi", ".flv", ".m4v", ".ts", ".m3u8"}
AUDIO_EXTS = {".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav"}
SKIP_IF_ALREADY = {".mp4"}  # already Android-friendly


@dataclass
class ProbeResult:
    path: Path
    container: str = ""
    video_codec: str = ""
    audio_codec: str = ""
    raw: str = ""

    @property
    def needs_transcode(self) -> bool:
        ext = self.path.suffix.lower()
        if ext in SKIP_IF_ALREADY and self.video_codec in ("", "h264"):
            return False
        if ext in VIDEO_EXTS:
            return True
        if self.video_codec and self.video_codec != "h264":
            return True
        return False


def _ffmpeg_bin() -> str:
    p = shutil.which("ffmpeg")
    if not p:
        raise RuntimeError(
            "ffmpeg not found. Install ffmpeg and make sure it is on PATH."
        )
    return p


def _ffprobe_bin() -> str:
    p = shutil.which("ffprobe")
    return p or ""


def probe(path: Path) -> ProbeResult:
    """Return a best-effort :class:`ProbeResult` for the given file."""
    res = ProbeResult(path=path)
    ffprobe = _ffprobe_bin()
    if ffprobe:
        try:
            p = subprocess.run(
                [ffprobe, "-v", "error", "-print_format", "json",
                 "-show_format", "-show_streams", str(path)],
                capture_output=True, text=True, timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            p = None
        if p and p.returncode == 0 and p.stdout.strip():
            import json
            try:
                info = json.loads(p.stdout)
            except json.JSONDecodeError:
                info = {}
            res.container = (info.get("format") or {}).get("format_name", "")
            for s in info.get("streams") or []:
                if s.get("codec_type") == "video" and not res.video_codec:
                    res.video_codec = s.get("codec_name", "")
                elif s.get("codec_type") == "audio" and not res.audio_codec:
                    res.audio_codec = s.get("codec_name", "")
            return res

    # Fallback: parse the `-i` banner when ffprobe is missing.
    try:
        p = subprocess.run(
            [_ffmpeg_bin(), "-hide_banner", "-i", str(path)],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return res
    out = (p.stderr or "") + "\n" + (p.stdout or "")
    res.raw = out[:2000]
    m = re.search(r"Input #\d+,\s*([^,]+),", out)
    if m:
        res.container = m.group(1).strip()
    m = re.search(r"Video:\s*([A-Za-z0-9_]+)", out)
    if m:
        res.video_codec = m.group(1)
    m = re.search(r"Audio:\s*([A-Za-z0-9_]+)", out)
    if m:
        res.audio_codec = m.group(1)
    return res


def transcode(src: Path, dst: Path, *, overwrite: bool = False) -> Path:
    """Transcode ``src`` to ``dst`` (Android-friendly MP4). Returns ``dst``."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg_bin(),
        "-y" if overwrite else "-n",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(src),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed for {src} -> {dst}:\n"
            f"{(p.stderr or p.stdout)[:1000]}"
        )
    return dst


def iter_media(tweet_dir: Path) -> Iterable[Path]:
    tp = tweet_paths(tweet_dir)
    for sub in ("video", "audio"):
        d = tp.root / "media" / sub
        if d.is_dir():
            for p in sorted(d.glob("*")):
                if p.is_file():
                    yield p


def process_tweet(tweet_dir: Path, *, force: bool, apply: bool, verbose: bool) -> tuple[int, int, int]:
    """Return (probed, would_transcode, transcoded)."""
    probed = 0
    would = 0
    done = 0
    for src in iter_media(tweet_dir):
        probed += 1
        info = probe(src)
        if not force and not info.needs_transcode:
            if verbose:
                print(f"  skip (already friendly): {src.relative_to(tweet_dir)} "
                      f"[v={info.video_codec} a={info.audio_codec} cont={info.container}]")
            continue
        dst = src.with_name(f"{src.stem}_transcoded.mp4")
        if dst.exists() and not force:
            if verbose:
                print(f"  skip (exists): {dst.name}")
            continue
        would += 1
        print(f"  {'[APPLY] ' if apply else '[DRY]   '}"
              f"{src.relative_to(tweet_dir)} -> {dst.name} "
              f"[v={info.video_codec} a={info.audio_codec} cont={info.container}]")
        if apply:
            transcode(src, dst, overwrite=force)
            done += 1
    return probed, would, done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--root", help="Recurse every tweet dir under ROOT.")
    g.add_argument("--tweet-dir", help="Single tweet dir to process.")
    ap.add_argument("--in", dest="src", help="Single input file (with --out).")
    ap.add_argument("--out", dest="dst", help="Single output file (with --in).")
    ap.add_argument("--apply", action="store_true",
                    help="Actually run ffmpeg (default: dry run).")
    ap.add_argument("--force", action="store_true",
                    help="Transcode even if the source looks Android-friendly.")
    ap.add_argument("--probe", action="store_true",
                    help="Only print ffprobe info, don't transcode.")
    ap.add_argument("--verbose", action="store_true",
                    help="Print extra info for skipped files.")
    args = ap.parse_args(argv)

    mode = "APPLY" if args.apply else "DRY-RUN"

    if args.src and args.dst:
        info = probe(Path(args.src))
        print(f"probe: {args.src} cont={info.container} "
              f"v={info.video_codec} a={info.audio_codec}")
        if args.probe:
            return 0
        if not args.apply:
            print(f"[{mode}] would transcode -> {args.dst}")
            return 0
        transcode(Path(args.src), Path(args.dst), overwrite=args.force)
        print(f"[{mode}] wrote {args.dst}")
        return 0

    targets: list[Path] = []
    if args.root:
        root = Path(args.root).expanduser().resolve()
        if not root.is_dir():
            print(f"ERROR: --root is not a directory: {root}", file=sys.stderr)
            return 2
        targets = find_tweet_dirs(root)
        if not targets:
            print(f"No tweet dirs under: {root}", file=sys.stderr)
            return 0
    elif args.tweet_dir:
        targets = [Path(args.tweet_dir).expanduser().resolve()]
    else:
        ap.error("Provide --root, --tweet-dir, or both --in and --out")

    total_probed = total_would = total_done = 0
    for td in targets:
        print(f"\n== [{mode}] {td}")
        p, w, d = process_tweet(td, force=args.force, apply=args.apply,
                                verbose=args.verbose)
        total_probed += p
        total_would += w
        total_done += d

    print(
        f"\nSummary [{mode}]: {len(targets)} dirs | "
        f"{total_probed} probed | {total_would} would transcode | "
        f"{total_done} transcoded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

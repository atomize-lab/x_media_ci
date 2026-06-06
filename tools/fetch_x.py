"""去 X 拉内容（Playwright 抓取器）

你指出得完全正确：`tools/scripts/` 里现有脚本都是“已落盘内容 → md/pdf/OCR”的转换器，
目前缺的是真正“去 x.com 把内容拉下来并落盘到 CI 结构”的抓取器。

本脚本补齐这一块（不走 X API，走浏览器自动化）：
  - 支持单条 URL（tweet / status）
  - 支持账号时间线抓取（滚动收集 N 条 status URL）
  - 下载媒体：图片（pbs.twimg.com 原图优先）、视频（优先 mp4；否则 m3u8→ffmpeg）
  - 写入 tweet.json，并维护 indices/*.jsonl 便于检索

依赖：
  - pip install playwright
  - python -m playwright install chromium
  - （可选，下载 m3u8 时）安装 ffmpeg 并确保在 PATH

示例：
  1) 抓单条（自动落盘到 CI/accounts/...）：
     python tools/fetch_x.py url --url "https://x.com/<handle>/status/<id>" --headed

  2) 抓单条（指定输出目录，兼容桌面 GUI 的调用习惯）：
     python tools/fetch_x.py url --url "https://x.com/<handle>/status/<id>" --out "<tweet_dir>" --headed

  3) 抓时间线（N 条）：
     python tools/fetch_x.py timeline --handle "<handle>" --limit 20 --headed

提示（登录态复用）：
  - 传入 --user-data-dir 可持久化登录态（首次会弹出浏览器，你手动登录一次即可）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Imports from tools/scripts (keep this file runnable via `python tools/fetch_x.py`)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HERE / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ci_common import ensure_dir, safe_filename  # noqa: E402
from tweet_schema import write_tweet_json  # noqa: E402


_TWEET_URL_RE = re.compile(
    r"^https?://(www\.)?(x\.com|twitter\.com)/([^/]+)/status/(\d+)",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_beijing_iso(dt_utc: _dt.datetime) -> str:
    bj = dt_utc.astimezone(_dt.timezone(_dt.timedelta(hours=8)))
    # 2026-05-25T18:29:28+08:00
    return bj.replace(microsecond=0).isoformat()


def _parse_iso_datetime(dt: str) -> Optional[_dt.datetime]:
    dt = (dt or "").strip()
    if not dt:
        return None
    # X often gives "2026-05-25T10:29:28.000Z"
    if dt.endswith("Z"):
        dt = dt[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(dt)
    except ValueError:
        return None


def _format_ci_stamp(dt_utc: _dt.datetime) -> str:
    # YYYYMMDDThhmmssZ
    return dt_utc.astimezone(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _guess_ci_root(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    # default: tools/ is inside CI/
    return _HERE.parent.resolve()


def _build_tweet_dir(ci_root: Path, handle: str, dt_utc: _dt.datetime, tweet_id: str) -> Path:
    yyyy = dt_utc.astimezone(_dt.timezone.utc).strftime("%Y")
    ym = dt_utc.astimezone(_dt.timezone.utc).strftime("%Y-%m")
    stamp = _format_ci_stamp(dt_utc)
    return ci_root / "accounts" / handle / "tweets" / yyyy / ym / f"{stamp}_{tweet_id}"


def _find_existing_tweet_dir(ci_root: Path, handle: str, tweet_id: str) -> Optional[Path]:
    base = ci_root / "accounts" / handle / "tweets"
    if not base.exists():
        return None
    suffix = f"_{tweet_id}"
    for p in base.rglob("*" + suffix):
        if p.is_dir():
            tj = p / "tweet.json"
            if tj.is_file():
                return p
    return None


def _http_get(url: str, out: Path, *, referer: str = "https://x.com/") -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Referer": referer,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status = getattr(r, "status", 200)
            if status and int(status) >= 400:
                raise RuntimeError(f"HTTP {status} for {url}")
            ct = (getattr(r, "headers", None) or {}).get("Content-Type", "")
            if ct and ("text/html" in ct or "application/json" in ct):
                data = r.read(2000)
                raise RuntimeError(f"unexpected content-type {ct} for {url}; head={data[:200]!r}")
            expected_len = None
            try:
                expected_len = int((getattr(r, "headers", None) or {}).get("Content-Length") or "0") or None
            except Exception:
                expected_len = None
            with out.open("wb") as f:
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            if expected_len is not None and out.stat().st_size < expected_len:
                raise RuntimeError(f"download truncated: got {out.stat().st_size} < {expected_len} bytes for {url}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {url}") from e
    except Exception as e:
        raise RuntimeError(f"download failed for {url}: {type(e).__name__}: {e}") from e


def _mp4_looks_incomplete(path: Path) -> bool:
    try:
        size = path.stat().st_size
    except Exception:
        return True
    if size < 200 * 1024:
        # Many X video URLs captured from the player are segment/init MP4s.
        # Those tend to be tiny and not suitable as the final saved video.
        try:
            head = path.read_bytes()
        except Exception:
            return True
        if b"ftyp" in head and b"mdat" not in head:
            return True
        return True
    # Quick scan for 'mdat' in the first 2MB.
    try:
        with path.open("rb") as f:
            buf = f.read(2 * 1024 * 1024)
        if b"ftyp" in buf and b"mdat" not in buf:
            return True
    except Exception:
        return True
    return False


def _pbs_to_orig(url: str) -> str:
    """Convert a pbs.twimg.com/media URL to original size where possible."""
    try:
        u = urllib.parse.urlsplit(url)
    except Exception:
        return url
    if "pbs.twimg.com" not in (u.netloc or ""):
        return url
    q = urllib.parse.parse_qs(u.query)
    # Ensure name=orig
    q["name"] = ["orig"]
    # Keep format if present; else infer from path suffix (rare)
    query = urllib.parse.urlencode({k: v[-1] for k, v in q.items()})
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, query, u.fragment))


def _pick_best_mp4(urls: Iterable[str]) -> Optional[str]:
    """Pick the 'largest' mp4 URL by parsing .../vid/<WxH>/... if present."""
    best = None
    best_area = -1
    for u in urls:
        if ".mp4" not in u:
            continue
        m = re.search(r"/vid/(\d+)x(\d+)/", u)
        area = 0
        if m:
            area = int(m.group(1)) * int(m.group(2))
        if area > best_area:
            best_area = area
            best = u
    return best


def _ffmpeg_bin() -> Optional[str]:
    return shutil.which("ffmpeg")


def _http_get_text(url: str, *, referer: str = "https://x.com/") -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Referer": referer,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {url}") from e
    except Exception as e:
        raise RuntimeError(f"download failed for {url}: {type(e).__name__}: {e}") from e
    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _pick_best_m3u8(m3u8_urls: Iterable[str]) -> Optional[str]:
    """Pick the best quality stream from a set of m3u8 URLs.

    If a URL is a master playlist (#EXT-X-STREAM-INF), pick the highest
    resolution/bitrate variant explicitly (ffmpeg otherwise often picks
    the first/lowest variant).
    """

    best: tuple[int, int, str] | None = None  # (area, bandwidth, url)

    for u in m3u8_urls:
        try:
            txt = _http_get_text(u)
        except Exception:
            continue

        # Master playlist: contains variants.
        if "#EXT-X-STREAM-INF" in txt:
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            i = 0
            while i < len(lines):
                ln = lines[i]
                if not ln.startswith("#EXT-X-STREAM-INF:"):
                    i += 1
                    continue
                attrs = ln.split(":", 1)[1]
                bw = 0
                area = 0
                m_bw = re.search(r"BANDWIDTH=(\d+)", attrs)
                if m_bw:
                    try:
                        bw = int(m_bw.group(1))
                    except Exception:
                        bw = 0
                m_res = re.search(r"RESOLUTION=(\d+)x(\d+)", attrs)
                if m_res:
                    try:
                        area = int(m_res.group(1)) * int(m_res.group(2))
                    except Exception:
                        area = 0
                # Next non-comment line is the variant URL.
                j = i + 1
                while j < len(lines) and lines[j].startswith("#"):
                    j += 1
                if j >= len(lines):
                    break
                variant = urllib.parse.urljoin(u, lines[j])
                cand = (area, bw, variant)
                if best is None or cand > best:
                    best = cand
                i = j + 1
            continue

        # Variant playlist already.
        cand = (0, 0, u)
        if best is None or cand > best:
            best = cand

    return best[2] if best else None


def _ffmpeg_from_m3u8(m3u8_url: str, out_mp4: Path) -> None:
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH (needed for m3u8).")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    # Best-effort: most public X video m3u8 works without headers/cookies.
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        m3u8_url,
        "-c",
        "copy",
        str(out_mp4),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "")[:1500])


@dataclass
class ExtractedTweet:
    tweet_id: str
    handle: str
    url: str
    datetime_utc_raw: str = ""
    text: str = ""
    image_urls: list[str] = None  # type: ignore[assignment]
    mp4_urls: list[str] = None  # type: ignore[assignment]
    m3u8_urls: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.image_urls = self.image_urls or []
        self.mp4_urls = self.mp4_urls or []
        self.m3u8_urls = self.m3u8_urls or []


# ---------------------------------------------------------------------------
# Playwright extraction
# ---------------------------------------------------------------------------


def _extract_from_page(page, url: str, handle_hint: str = "", tweet_id_hint: str = "") -> ExtractedTweet:
    """Extract core fields (text/time/images) from the currently loaded tweet page."""
    # tweet_id / handle from URL if possible
    tweet_id = tweet_id_hint
    handle = handle_hint
    m = _TWEET_URL_RE.match(url)
    if m:
        handle = handle or m.group(3)
        tweet_id = tweet_id or m.group(4)

    # Wait for at least one tweet article.
    page.wait_for_selector("article", timeout=45_000)
    art = page.query_selector("article")
    if not art:
        raise RuntimeError("no <article> found")

    # datetime
    dt_raw = ""
    try:
        t = art.query_selector("time")
        if t:
            dt_raw = t.get_attribute("datetime") or ""
    except Exception:
        pass

    # text
    text_parts: list[str] = []
    for sel in ('div[data-testid="tweetText"]', "div[lang]"):
        try:
            nodes = art.query_selector_all(sel) or []
            for n in nodes:
                s = (n.inner_text() or "").strip()
                if s and s not in text_parts:
                    text_parts.append(s)
        except Exception:
            continue
    text = "\n".join(text_parts).strip()

    # images (pbs.twimg.com/media)
    img_urls: list[str] = []
    try:
        imgs = art.query_selector_all("img") or []
        for im in imgs:
            src = (im.get_attribute("src") or "").strip()
            if not src:
                continue
            if "pbs.twimg.com/media" in src:
                src = _pbs_to_orig(src)
                if src not in img_urls:
                    img_urls.append(src)
    except Exception:
        pass

    return ExtractedTweet(
        tweet_id=tweet_id or "",
        handle=handle or "",
        url=url,
        datetime_utc_raw=dt_raw,
        text=text,
        image_urls=img_urls,
    )


def _looks_like_login_wall(page) -> bool:
    try:
        u = (page.url or "").lower()
    except Exception:
        u = ""
    if any(s in u for s in ("/login", "flow/login", "/i/flow/login")):
        return True
    for sel in (
        'a[href="/login"]',
        'a[href="/i/flow/login"]',
        'input[name="text"]',
        'input[name="password"]',
        'div[data-testid="LoginForm_Login_Button"]',
        "text=Log in",
        "text=Sign in",
        "text=登录",
        "text=登入",
    ):
        try:
            if page.query_selector(sel):
                return True
        except Exception:
            continue
    return False


def _wait_for_login_then_tweet(page, url: str, *, timeout_ms: int = 600_000) -> None:
    start = time.time()
    warned = False
    while (time.time() - start) * 1000 < timeout_ms:
        if _looks_like_login_wall(page) and not warned:
            print("[login] Please log in to x.com in the opened browser window, then wait here…", file=sys.stderr)
            warned = True
        if not _looks_like_login_wall(page):
            try:
                if page.url != url:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_selector("article", timeout=5000)
                page.wait_for_timeout(800)
                return
            except Exception:
                pass
        try:
            page.wait_for_timeout(800)
        except Exception:
            time.sleep(0.8)
    raise RuntimeError("login required (timed out waiting for manual login)")


def _video_group_key(url: str) -> str:
    for pat in (
        r"/amplify_video/(\d+)/",
        r"/ext_tw_video/(\d+)/",
        r"/tweet_video/(\d+)/",
    ):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return url.split("?", 1)[0]


def _collect_video_urls(page, *, settle_ms: int = 6000, max_items: int = 6) -> dict[str, dict[str, list[str]]]:
    grouped_mp4: dict[str, set[str]] = {}
    grouped_m3u8: dict[str, set[str]] = {}

    def on_resp(resp):
        try:
            u = resp.url
        except Exception:
            return
        if "video.twimg.com" not in u:
            return
        k = _video_group_key(u)
        if ".m3u8" in u:
            grouped_m3u8.setdefault(k, set()).add(u)
        elif ".mp4" in u:
            grouped_mp4.setdefault(k, set()).add(u)

    page.on("response", on_resp)

    opened = False
    for sel in ('div[data-testid="videoPlayer"]', 'video'):
        try:
            if page.query_selector(sel):
                page.click(sel, timeout=2500)
                opened = True
                break
        except Exception:
            continue
    if not opened:
        for sel in ('div[data-testid="playButton"]', 'button[aria-label="Play"]', 'button[aria-label="播放"]'):
            try:
                if page.query_selector(sel):
                    page.click(sel, timeout=2500)
                    opened = True
                    break
            except Exception:
                continue

    no_new = 0
    prev_n = 0
    for _ in range(max_items):
        for sel in ('div[data-testid="playButton"]', 'button[aria-label="Play"]', 'button[aria-label="播放"]', 'video'):
            try:
                if page.query_selector(sel):
                    page.click(sel, timeout=1500)
                    break
            except Exception:
                continue

        page.wait_for_timeout(settle_ms)
        cur_n = sum(len(v) for v in grouped_mp4.values()) + sum(len(v) for v in grouped_m3u8.values())
        if cur_n == prev_n:
            no_new += 1
        else:
            no_new = 0
        prev_n = cur_n
        if no_new >= 2:
            break

        moved = False
        for sel in (
            'button[aria-label="Next"]',
            'button[aria-label="下一条"]',
            'button[aria-label="下一个"]',
            'div[role="button"][aria-label="Next"]',
        ):
            try:
                if page.query_selector(sel):
                    page.click(sel, timeout=2000)
                    page.wait_for_timeout(900)
                    moved = True
                    break
            except Exception:
                continue
        if not moved:
            break

    out: dict[str, dict[str, list[str]]] = {}
    keys = sorted(set(grouped_mp4.keys()) | set(grouped_m3u8.keys()))
    for k in keys:
        out[k] = {
            "mp4": sorted(grouped_mp4.get(k, set())),
            "m3u8": sorted(grouped_m3u8.get(k, set())),
        }
    return out


# ---------------------------------------------------------------------------
# CI writing (tweet.json + indices)
# ---------------------------------------------------------------------------

def _apply_x_session(context, *, auth_token: str = "", ct0: str = "") -> None:
    auth_token = (auth_token or "").strip()
    ct0 = (ct0 or "").strip()
    if not auth_token and not ct0:
        return
    cookies = []
    if auth_token:
        cookies.append({"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"})
        cookies.append({"name": "auth_token", "value": auth_token, "domain": ".twitter.com", "path": "/"})
    if ct0:
        cookies.append({"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"})
        cookies.append({"name": "ct0", "value": ct0, "domain": ".twitter.com", "path": "/"})
    if cookies:
        try:
            context.add_cookies(cookies)
        except Exception:
            pass
    if ct0:
        try:
            context.set_extra_http_headers({"x-csrf-token": ct0})
        except Exception:
            pass


def _rel_to_ci(ci_root: Path, p: Path) -> str:
    rel = p.resolve().relative_to(ci_root.resolve())
    return str(rel).replace("\\", "/")


def _jsonl_prepend_unique(path: Path, row: dict, *, key: str = "tweet_id") -> None:
    """Prepend a row to JSONL if key not present; keep existing content."""
    ensure_dir(path.parent)
    new_line = json.dumps(row, ensure_ascii=False) + "\n"
    if not path.exists():
        path.write_text(new_line, encoding="utf-8")
        return
    try:
        old = path.read_text(encoding="utf-8")
    except Exception:
        old = ""
    # If already present, do nothing.
    needle = f'"{key}":"{row.get(key,"")}"'
    if needle and needle in old:
        return
    path.write_text(new_line + old, encoding="utf-8")


def _update_indices(ci_root: Path, tweet_dir: Path, meta: dict) -> None:
    tid = meta.get("tweet_id", "")
    handle = (meta.get("author_handle", "") or "").lstrip("@")
    dt_utc = meta.get("datetime_utc", "")
    dt_bj = meta.get("datetime_beijing", "")
    text = meta.get("text", "") or ""
    media = meta.get("media") or []
    exports = meta.get("exports") or []

    media_types = sorted({(m or {}).get("type", "") for m in media if (m or {}).get("type")})
    images_found = sum(1 for m in media if (m or {}).get("type") == "image")
    videos_found = sum(1 for m in media if (m or {}).get("type") == "video")

    row = {
        "tweet_id": tid,
        "tweet_url": meta.get("tweet_url", ""),
        "author_handle": meta.get("author_handle", ""),
        "datetime_utc": dt_utc,
        "datetime_beijing": dt_bj,
        "folder": _rel_to_ci(ci_root, tweet_dir),
        "tweet_json": _rel_to_ci(ci_root, tweet_dir / "tweet.json"),
        "text_preview": (text[:80] + "…") if len(text) > 80 else text,
        "media_types": media_types,
        "images_found": images_found,
        "videos_found": videos_found,
    }
    if exports:
        row["exports"] = [e.get("file", "") for e in exports if isinstance(e, dict) and e.get("file")]

    # tweets.jsonl (global)
    _jsonl_prepend_unique(ci_root / "indices" / "tweets.jsonl", row, key="tweet_id")
    # by_handle
    if handle:
        _jsonl_prepend_unique(ci_root / "indices" / "by_handle" / f"{handle}.jsonl", row, key="tweet_id")
    # by_date (YYYY-MM)
    dtp = _parse_iso_datetime(dt_utc)
    if dtp:
        ym = dtp.astimezone(_dt.timezone.utc).strftime("%Y-%m")
        yyyy = dtp.astimezone(_dt.timezone.utc).strftime("%Y")
        _jsonl_prepend_unique(ci_root / "indices" / "by_date" / yyyy / f"{ym}.jsonl", row, key="tweet_id")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def fetch_one(context, url: str, *, ci_root: Path, out_dir: Optional[Path], headed: bool, sleep_s: float = 0.5) -> Path:
    """Fetch a single tweet URL. Returns the tweet_dir."""
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    # Try to let X hydrate
    page.wait_for_timeout(1200)

    if headed and _looks_like_login_wall(page):
        _wait_for_login_then_tweet(page, url, timeout_ms=600_000)

    extracted = _extract_from_page(page, url)
    if not extracted.tweet_id:
        raise RuntimeError(f"cannot parse tweet id from url: {url}")
    if not extracted.handle:
        # Fallback: infer from any status link in page
        try:
            a = page.query_selector(f'a[href*="/status/{extracted.tweet_id}"]')
            if a:
                href = a.get_attribute("href") or ""
                m = re.search(r"^/([^/]+)/status/", href)
                if m:
                    extracted.handle = m.group(1)
        except Exception:
            pass
    if not extracted.handle:
        raise RuntimeError("cannot determine author handle (need it for CI path)")

    dtp = _parse_iso_datetime(extracted.datetime_utc_raw) or _dt.datetime.now(tz=_dt.timezone.utc)
    tweet_dir = out_dir.resolve() if out_dir else _build_tweet_dir(ci_root, extracted.handle, dtp, extracted.tweet_id)

    # Skip if already exists (idempotent)
    if (tweet_dir / "tweet.json").is_file():
        return tweet_dir

    # Prepare dirs
    images_dir = ensure_dir(tweet_dir / "media" / "images")
    video_dir = ensure_dir(tweet_dir / "media" / "video")
    ensure_dir(tweet_dir / "media" / "audio")
    raw_dir = ensure_dir(tweet_dir / "media" / "raw")
    ensure_dir(tweet_dir / "exports")

    media_entries: list[dict] = []

    # Download images
    for idx, img_url in enumerate(extracted.image_urls, start=1):
        u = _pbs_to_orig(img_url)
        base = u.split("/media/")[-1].split("?")[0]
        ext = ""
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
        if "format" in q and q["format"]:
            ext = "." + q["format"][-1].strip(".")
        if not ext:
            ext = Path(base).suffix or ".jpg"
        fname = f"{idx:02d}_{safe_filename(Path(base).stem)}{ext}"
        out = images_dir / fname
        try:
            _http_get(u, out)
            media_entries.append(
                {
                    "type": "image",
                    "mime": "image/" + ext.lstrip(".").lower(),
                    "file": f"media/images/{fname}",
                    "source_url": u,
                }
            )
        except Exception as e:
            # Leave a breadcrumb for debugging
            (raw_dir / f"image_{idx:02d}_error.txt").write_text(str(e), encoding="utf-8")

    videos = _collect_video_urls(page)
    if videos:
        (raw_dir / "video_urls.json").write_text(
            json.dumps(videos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    max_videos = 6
    for idx, key in enumerate(sorted(videos.keys())[:max_videos], start=1):
        mp4_urls = videos.get(key, {}).get("mp4", []) or []
        m3u8_urls = videos.get(key, {}).get("m3u8", []) or []

        vname = f"{extracted.tweet_id}_video_{idx:02d}.mp4"
        vout = video_dir / vname
        err_mp4 = raw_dir / f"video_download_error_{idx:02d}.txt"
        err_m3u8 = raw_dir / f"m3u8_ffmpeg_error_{idx:02d}.txt"
        chosen_log = raw_dir / f"video_m3u8_chosen_{idx:02d}.txt"

        mp4_vid = [u for u in mp4_urls if "/vid/" in u and "/aud/" not in u]
        best_mp4 = _pick_best_mp4(mp4_vid or mp4_urls)
        if best_mp4:
            try:
                _http_get(best_mp4, vout)
                if _mp4_looks_incomplete(vout) and m3u8_urls:
                    try:
                        vout.unlink(missing_ok=True)  # type: ignore[arg-type]
                    except Exception:
                        pass
                    raise RuntimeError("mp4 looks incomplete (segment/init); falling back to m3u8")
                media_entries.append(
                    {
                        "type": "video",
                        "mime": "video/mp4",
                        "file": f"media/video/{vname}",
                        "source_url": best_mp4,
                    }
                )
                continue
            except Exception as e:
                err_mp4.write_text(str(e), encoding="utf-8")

        if m3u8_urls:
            try:
                chosen = _pick_best_m3u8(m3u8_urls) or m3u8_urls[0]
                chosen_log.write_text(chosen, encoding="utf-8")
                _ffmpeg_from_m3u8(chosen, vout)
                media_entries.append(
                    {
                        "type": "video",
                        "mime": "video/mp4",
                        "file": f"media/video/{vname}",
                        "source_url": chosen,
                        "derived_from": "m3u8",
                    }
                )
            except Exception as e:
                err_m3u8.write_text(str(e), encoding="utf-8")

    meta = {
        "source": "x.com",
        "ci_version": "1.0",
        "tweet_id": extracted.tweet_id,
        "tweet_url": url,
        "author_handle": "@" + extracted.handle,
        "datetime_utc": dtp.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "datetime_beijing": _to_beijing_iso(dtp),
        "fetched_at": _dt.date.today().isoformat(),
        "text": extracted.text,
        "media": media_entries,
        "exports": [],
        "note": "fetched via Playwright (no X API).",
    }
    write_tweet_json(tweet_dir, meta, validate=True)
    _update_indices(ci_root, tweet_dir, meta)

    # polite sleep (anti-rate-limit)
    if sleep_s:
        time.sleep(sleep_s)
    return tweet_dir


def cmd_url(args: argparse.Namespace) -> int:
    ci_root = _guess_ci_root(args.ci_root)
    ci_root.mkdir(parents=True, exist_ok=True)

    # Playwright import is intentionally inside the command so the script
    # can still print --help without playwright installed.
    from playwright.sync_api import sync_playwright  # type: ignore

    user_data = args.user_data_dir
    headed = bool(args.headed)
    out_dir = Path(args.out).expanduser().resolve() if args.out else None

    with sync_playwright() as p:
        if user_data:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(Path(user_data).expanduser().resolve()),
                headless=not headed,
                viewport={"width": 1280, "height": 900},
                channel=args.channel,
            )
        else:
            browser = p.chromium.launch(headless=not headed, channel=args.channel)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            _apply_x_session(context, auth_token=args.auth_token, ct0=args.ct0)
            td = fetch_one(context, args.url, ci_root=ci_root, out_dir=out_dir, headed=headed)
            print(str(td))
        finally:
            context.close()
    return 0


def _collect_timeline_urls(page, handle: str, limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    handle = handle.lstrip("@")
    # Keep scrolling until enough unique status URLs are found.
    for _ in range(200):  # hard cap
        # Grab all links that look like /<handle>/status/<id>
        try:
            links = page.query_selector_all(f'a[href^="/{handle}/status/"]') or []
        except Exception:
            links = []
        for a in links:
            try:
                href = (a.get_attribute("href") or "").strip()
            except Exception:
                continue
            if not href:
                continue
            m = re.match(rf"^/{re.escape(handle)}/status/(\d+)", href)
            if not m:
                continue
            tid = m.group(1)
            full = f"https://x.com/{handle}/status/{tid}"
            if tid not in seen:
                seen.add(tid)
                out.append(full)
                if len(out) >= limit:
                    return out
        # Scroll down a bit
        try:
            page.mouse.wheel(0, 2400)
        except Exception:
            try:
                page.evaluate("window.scrollBy(0, 2400)")
            except Exception:
                pass
        page.wait_for_timeout(900)
    return out


def cmd_timeline(args: argparse.Namespace) -> int:
    ci_root = _guess_ci_root(args.ci_root)
    ci_root.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright  # type: ignore

    handle = args.handle.lstrip("@")
    limit = int(args.limit)
    headed = bool(args.headed)
    user_data = args.user_data_dir

    with sync_playwright() as p:
        if user_data:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(Path(user_data).expanduser().resolve()),
                headless=not headed,
                viewport={"width": 1280, "height": 900},
                channel=args.channel,
            )
        else:
            browser = p.chromium.launch(headless=not headed, channel=args.channel)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            _apply_x_session(context, auth_token=args.auth_token, ct0=args.ct0)
            page = context.new_page()
            page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1500)
            urls = _collect_timeline_urls(page, handle, limit)
            if not urls:
                print("No tweet URLs collected. (May require login.)", file=sys.stderr)
                return 2
            ok = 0
            for u in urls:
                m = _TWEET_URL_RE.match(u)
                tid = m.group(4) if m else ""
                if tid:
                    existing = _find_existing_tweet_dir(ci_root, handle, tid)
                    if existing:
                        continue
                try:
                    td = fetch_one(context, u, ci_root=ci_root, out_dir=None, headed=headed, sleep_s=0.8)
                    print(str(td))
                    ok += 1
                except Exception as e:
                    print(f"[ERR] {u}: {e}", file=sys.stderr)
            if ok == 0:
                return 3
        finally:
            context.close()
    return 0


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Playwright 抓取 X → CI 落盘")
    ap.add_argument("--ci-root", help="CI 根目录（默认推断为 tools/ 的上一级）")
    ap.add_argument("--headed", action="store_true", help="打开可见浏览器窗口（便于你手动登录）")
    ap.add_argument(
        "--user-data-dir",
        help="持久化浏览器 user-data 目录（用于复用登录态）；建议放到 CI/tools/.pw-userdata",
    )
    ap.add_argument("--auth-token", help="x.com cookie: auth_token（可选，用于跳过登录流程）")
    ap.add_argument("--ct0", help="x.com cookie: ct0（可选，用于跳过登录流程）")
    ap.add_argument(
        "--channel",
        choices=["chromium", "chrome", "msedge"],
        default="chromium",
        help="Playwright 启动的浏览器通道（可选）。chrome/msedge 更像真实浏览器，但需要本机已安装。",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_url = sub.add_parser("url", help="抓取单条 tweet URL")
    p_url.add_argument("--url", required=True, help="https://x.com/<handle>/status/<id>")
    p_url.add_argument("--out", help="指定输出 tweet_dir（不指定则自动按 CI 结构生成）")
    p_url.set_defaults(func=cmd_url)

    p_tl = sub.add_parser("timeline", help="抓取账号时间线（滚动收集 N 条）")
    p_tl.add_argument("--handle", required=True, help="账号 handle（不含@）")
    p_tl.add_argument("--limit", type=int, default=20, help="抓取条数（默认 20）")
    p_tl.set_defaults(func=cmd_timeline)
    return ap


def main(argv=None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

"""兼容 GUI 的“抓单条 URL → 落盘”入口。

桌面端 `app_desktop/tweet_fetcher.py` 会尝试调用一个外置脚本：

    python fetch_tweet.py <tweet_url> --out <tweet_dir>

它要求这个脚本负责真正去 x.com 抓内容并把目录填满（media/ + tweet.json）。

本文件只是一个薄封装：把参数转发给 `tools/fetch_x.py url ...`。
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path


# Exit codes — the GUI looks at these to decide what to tell the user.
RC_OK              = 0
RC_NEEDS_PLAYWRIGHT = 10   # ModuleNotFoundError: playwright
RC_NEEDS_CHROMIUM   = 11   # playwright is installed but chromium browser missing
RC_NEEDS_LOGIN      = 20   # everything installed, but x.com said "log in"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fetch one tweet URL into a CI tweet_dir (GUI compatible).")
    ap.add_argument("url", help="https://x.com/<handle>/status/<id>")
    ap.add_argument("--out", required=True, help="tweet_dir output (CI-shaped folder path)")
    ap.add_argument("--ci-root", help="CI root; default inferred by fetch_x.py")
    ap.add_argument("--headed", action="store_true", help="show browser window")
    ap.add_argument("--user-data-dir", help="persistent browser user-data-dir (login reuse)")
    args = ap.parse_args(argv)

    # Import sibling module (tools/fetch_x.py)
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    try:
        import fetch_x  # noqa: E402
    except Exception as e:  # noqa: BLE001
        print(f"[fetch_tweet] FATAL: failed to import fetch_x: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 1

    cmd = [
        "--ci-root",
        args.ci_root,
    ] if args.ci_root else []
    if args.headed:
        cmd.append("--headed")
    if args.user_data_dir:
        cmd += ["--user-data-dir", args.user_data_dir]
    auth_token = (os.environ.get("X_AUTH_TOKEN") or "").strip()
    ct0 = (os.environ.get("X_CT0") or "").strip()
    channel = (os.environ.get("X_BROWSER_CHANNEL") or "").strip()
    if auth_token:
        cmd += ["--auth-token", auth_token]
    if ct0:
        cmd += ["--ct0", ct0]
    if channel:
        cmd += ["--channel", channel]
    cmd += ["url", "--url", args.url, "--out", args.out]

    try:
        return fetch_x.main(cmd)
    except ModuleNotFoundError as e:
        # Most common cause: the *system* Python the GUI shells out to
        # does not have playwright installed.
        missing = e.name or str(e)
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"[fetch_tweet] MISSING DEPENDENCY: {missing}", file=sys.stderr)
        print("  The fetcher needs Playwright + a Chromium browser.", file=sys.stderr)
        print("  Fix:", file=sys.stderr)
        print("    pip install playwright", file=sys.stderr)
        print("    playwright install chromium", file=sys.stderr)
        print("  (run the above in the SAME Python that runs this script)", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        return RC_NEEDS_PLAYWRIGHT
    except Exception as e:  # noqa: BLE001
        print(f"[fetch_tweet] ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

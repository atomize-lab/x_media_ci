import json
from pathlib import Path


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr-txt", required=True, help="Merged OCR text file (one line per line)")
    ap.add_argument("--out-json", required=True, help="Output extract json")
    ap.add_argument("--title", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--datetime-utc", required=True)
    ap.add_argument("--screenshots-glob", required=True, help="Glob used to generate this OCR")
    args = ap.parse_args()

    lines = Path(args.ocr_txt).read_text(encoding="utf-8").splitlines()
    blocks = [{"type": "p", "text": ln} for ln in lines if ln.strip()]

    meta = {
        "url": args.url,
        "tweet_url": args.url,
        "author_handle": args.author,
        "datetime_utc": args.datetime_utc,
        "title": args.title,
        "extract_method": "screenshot_ocr",
        "screenshots_glob": args.screenshots_glob,
        "blocks": blocks,
    }

    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {out} blocks={len(blocks)}")


if __name__ == "__main__":
    main()


import os
import re
import subprocess
import glob
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageOps, ImageFilter


def resolve_tesseract_cmd() -> str:
    v = os.environ.get("TESSERACT_CMD")
    if v:
        return v
    return "tesseract"


def resolve_tessdata_prefix() -> str | None:
    v = os.environ.get("TESSDATA_PREFIX")
    return v or None


def md_escape(text: str) -> str:
    if not text:
        return text
    out = []
    prev = ""
    for ch in text:
        if ch == "$" and prev != "\\":
            out.append("\\$")
        elif ch == "`" and prev != "\\":
            out.append("\\`")
        else:
            out.append(ch)
        prev = ch
    return "".join(out)


def preprocess(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    img = ImageOps.grayscale(img)
    # Upscale for better OCR
    w, h = img.size
    scale = 2
    img = img.resize((w * scale, h * scale), resample=Image.Resampling.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    # Simple threshold
    img = img.point(lambda p: 255 if p > 180 else 0)
    return img


def ocr_image(img: Image.Image, lang: str = "chi_sim") -> str:
    env = os.environ.copy()
    tessdata_prefix = resolve_tessdata_prefix()
    if tessdata_prefix:
        env["TESSDATA_PREFIX"] = tessdata_prefix
    tmp_dir = Path(tempfile.gettempdir()) / "x_media_ci_ocr_screens"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / "screen.png"
    img.save(tmp_path, format="PNG", optimize=True)

    cmd = [resolve_tesseract_cmd(), str(tmp_path), "stdout", "-l", lang, "--psm", "6"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except FileNotFoundError as e:
        raise RuntimeError(
            "tesseract not found. Install it and ensure it is in PATH, "
            "or set TESSERACT_CMD to the executable path."
        ) from e
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:800])
    return p.stdout


def normalize_lines(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Drop very short noise lines
    lines = []
    for ln in text.split("\n"):
        ln = ln.strip()
        ln = re.sub(r"[ \t]+", " ", ln)
        if not ln:
            continue
        # remove obvious OCR garbage-only lines
        if len(ln) <= 1:
            continue
        lines.append(ln)
    return lines


def overlap_k(prev: list[str], cur: list[str], max_k: int = 50) -> int:
    if not prev or not cur:
        return 0
    max_k = min(max_k, len(prev), len(cur))
    for k in range(max_k, 5, -1):
        a = "\n".join(prev[-k:])
        b = "\n".join(cur[:k])
        if a == b:
            return k
        r = SequenceMatcher(None, a, b).ratio()
        if r >= 0.88:
            return k
    return 0


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True, help="Glob pattern for screenshots (ordered by filename)")
    ap.add_argument("--out-txt", required=True, help="Output merged text file (utf-8)")
    ap.add_argument("--out-md", required=True, help="Output markdown file (utf-8)")
    ap.add_argument("--title", default="X Article (OCR)")
    ap.add_argument("--url", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--datetime-utc", default="")
    args = ap.parse_args()

    paths = [Path(p) for p in sorted(glob.glob(args.glob))]
    if not paths:
        raise SystemExit(f"No files matched: {args.glob}")

    merged: list[str] = []

    for _, p in enumerate(paths, start=1):
        img = Image.open(p)
        txt = ocr_image(preprocess(img))
        cur = normalize_lines(txt)
        k = overlap_k(merged, cur, max_k=60)
        if k:
            cur = cur[k:]
        merged.extend(cur)

    # light de-dup consecutive identical lines
    cleaned: list[str] = []
    for ln in merged:
        if cleaned and cleaned[-1] == ln:
            continue
        cleaned.append(ln)

    out_txt = "\n".join(cleaned).strip() + "\n"
    Path(args.out_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_txt).write_text(out_txt, encoding="utf-8")

    md_lines = []
    md_lines.append(f"# {md_escape(args.title)}")
    md_lines.append("")
    if args.author:
        md_lines.append(f"- 作者：{md_escape(args.author)}")
    if args.url:
        md_lines.append(f"- 文章链接：{args.url}")
    if args.datetime_utc:
        md_lines.append(f"- 时间（UTC）：{args.datetime_utc}")
    md_lines.append("")
    md_lines.append("> 说明：以下正文由分段截图 OCR 合并生成，可能存在少量识别误差。")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    for ln in cleaned:
        md_lines.append(md_escape(ln))
    md_lines.append("")

    out_md = "\n".join(md_lines)
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text(out_md, encoding="utf-8")

    print(f"OK: {len(paths)} screenshots -> {len(cleaned)} lines")


if __name__ == "__main__":
    main()

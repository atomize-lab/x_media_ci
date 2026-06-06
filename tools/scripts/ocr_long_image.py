import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def resolve_tesseract_cmd() -> str:
    v = os.environ.get("TESSERACT_CMD")
    if v:
        return v
    return "tesseract"


def resolve_tessdata_prefix() -> str | None:
    v = os.environ.get("TESSDATA_PREFIX")
    return v or None


def ocr_image_chunk(img: Image.Image, lang: str = "chi_sim+eng") -> str:
    env = os.environ.copy()
    tessdata_prefix = resolve_tessdata_prefix()
    if tessdata_prefix:
        env["TESSDATA_PREFIX"] = tessdata_prefix

    # Write a temporary png for this chunk (tesseract works best with file paths)
    tmp_dir = Path(tempfile.gettempdir()) / "x_media_ci_ocr_chunks"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / "chunk.png"
    img.save(tmp_path, format="PNG", optimize=True)

    cmd = [
        resolve_tesseract_cmd(),
        str(tmp_path),
        "stdout",
        "-l",
        lang,
        "--psm",
        "6",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except FileNotFoundError as e:
        raise RuntimeError(
            "tesseract not found. Install it and ensure it is in PATH, "
            "or set TESSERACT_CMD to the executable path."
        ) from e
    if p.returncode != 0:
        raise RuntimeError(f"tesseract failed: {p.stderr[:500]}")
    return p.stdout


def normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # normalize spaces
    s = re.sub(r"[ \t]+", " ", s)
    # keep blank lines but reduce too many
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="Path to a long screenshot")
    ap.add_argument("--out", required=True, help="Output txt path")
    ap.add_argument("--chunk-height", type=int, default=2200)
    ap.add_argument("--overlap", type=int, default=220)
    args = ap.parse_args()

    img_path = Path(args.image)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(img_path).convert("RGB")
    w, h = img.size

    chunk_h = args.chunk_height
    overlap = args.overlap

    texts = []
    y = 0
    while y < h:
        y2 = min(h, y + chunk_h)
        crop = img.crop((0, y, w, y2))
        t = ocr_image_chunk(crop)
        texts.append(t)
        if y2 >= h:
            break
        y = y2 - overlap

    merged = "\n\n".join(texts)
    merged = normalize_text(merged)

    out_path.write_text(merged, encoding="utf-8")
    print(f"OK: wrote {out_path} ({len(merged)} chars)")


if __name__ == "__main__":
    main()

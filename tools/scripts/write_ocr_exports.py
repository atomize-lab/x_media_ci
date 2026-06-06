from pathlib import Path


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr-txt", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-txt", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--datetime-utc", required=True)
    ap.add_argument("--images-dir", required=True)
    args = ap.parse_args()

    txt_path = Path(args.ocr_txt)
    text = txt_path.read_text(encoding="utf-8").strip() + "\n"

    out_txt = Path(args.out_txt)
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_txt.write_text(text, encoding="utf-8")

    images_dir = Path(args.images_dir)
    imgs = sorted([p.name for p in images_dir.glob("*.*")])

    md = []
    md.append(f"# {args.title}（OCR补全）")
    md.append("")
    md.append(f"- 作者：[{args.author}](https://x.com/{args.author.lstrip('@')})")
    md.append(f"- 链接：{args.url}")
    md.append(f"- 时间（UTC）：{args.datetime_utc}")
    md.append("")
    md.append("> 说明：以下正文来自“分段截图 + OCR 合并”，可能有少量识别误差，但会尽量覆盖全文。")
    md.append("")
    if imgs:
        md.append("## 图片（原图）")
        md.append("")
        for n in imgs:
            md.append(f"![{n}](../media/images/{n})")
        md.append("")
    md.append("---")
    md.append("")
    md.append("## 正文（OCR）")
    md.append("")
    md.append("```text")
    md.append(text.rstrip("\n"))
    md.append("```")
    md.append("")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"OK: wrote {out_md} and {out_txt}")


if __name__ == "__main__":
    main()


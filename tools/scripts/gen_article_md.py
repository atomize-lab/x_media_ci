import json
import os
import re
from pathlib import Path


def media_id_from_url(url: str) -> str | None:
    m = re.search(r"/media/([^?]+)", url)
    return m.group(1) if m else None


def find_local_image(images_dir: Path, media_url: str) -> str:
    mid = media_id_from_url(media_url)
    if not mid:
        return media_url
    matches = list(images_dir.glob(f"*_{mid}.*"))
    if not matches:
        # fallback: any file containing mid
        matches = list(images_dir.glob(f"*{mid}*"))
    if not matches:
        return media_url
    # prefer stable ordering
    matches.sort()
    # md file is in exports/, so use ../media/images/<file>
    return f"../media/images/{matches[0].name}"


def md_escape(text: str) -> str:
    """
    对 Markdown 做最小必要转义，避免在某些渲染器里出现异常：
    - \$... \$ 可能被当作数学公式，所以将未转义的 $ 转成 \\$
    - 反引号用于代码块，转义为 \\`
    注意：这是“兼容性优先”的策略（有些 Markdown 渲染器本身不需要转义 $）。
    """
    if not text:
        return text

    # 逐字符处理，避免把已经转义的 \$ 再次转义
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


def render_md(meta: dict, images_dir: Path) -> str:
    title = meta.get("title") or "X Article"
    url = meta.get("url", "")
    author = meta.get("author_handle", "")
    dt = meta.get("datetime_utc", "")

    out = []
    out.append(f"# {md_escape(title)}")
    out.append("")
    out.append(f"- 作者：[{author}](https://x.com/{author.lstrip('@')})" if author else "- 作者：")
    out.append(f"- 文章链接：{url}")
    out.append(f"- 时间（UTC）：{dt}")
    out.append("")
    out.append("---")
    out.append("")

    def heading_prefix(t: str) -> str:
        return {"h1": "##", "h2": "###", "h3": "####"}.get(t, "##")

    in_list = False
    for n in meta.get("nodes", []):
        t = n.get("type")
        if t == "img":
            # close any running list
            if in_list:
                out.append("")
                in_list = False
            local = find_local_image(images_dir, n.get("src", ""))
            alt = os.path.basename(local)
            out.append(f"![{alt}]({local})")
            out.append("")
        elif t in ("h1", "h2", "h3"):
            if in_list:
                out.append("")
                in_list = False
            text = (n.get("text") or "").strip()
            if not text:
                continue
            out.append(f"{heading_prefix(t)} {md_escape(text)}")
            out.append("")
        elif t == "li":
            text = (n.get("text") or "").strip()
            if not text:
                continue
            out.append(f"- {md_escape(text)}")
            in_list = True
        elif t == "p":
            if in_list:
                out.append("")
                in_list = False
            text = (n.get("text") or "").strip()
            if not text:
                continue
            out.append(md_escape(text))
            out.append("")

    # Deduplicate excessive blank lines
    cleaned = []
    for line in out:
        if line == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)

    return "\n".join(cleaned).rstrip() + "\n"


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", required=True, help="Path to article_*_extract.json")
    ap.add_argument("--images-dir", required=True, help="Path to media/images")
    ap.add_argument("--out", help="Write markdown to this path (utf-8). If omitted, print to stdout.")
    args = ap.parse_args()

    extract_path = Path(args.extract)
    images_dir = Path(args.images_dir)

    meta = json.loads(extract_path.read_text(encoding="utf-8"))
    md = render_md(meta, images_dir)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    else:
        print(md, end="")


if __name__ == "__main__":
    main()


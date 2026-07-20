import json
import os
import glob
import platform

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
    KeepTogether,
    ListFlowable,
    ListItem,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont


PRIMARY_COLOR = HexColor("#1a365d")
ACCENT_COLOR = HexColor("#2b6cb0")


def register_cjk_font():
    env_font = os.environ.get("CJK_FONT_PATH")
    if env_font and os.path.exists(env_font):
        pdfmetrics.registerFont(TTFont("CJKFont", env_font, subfontIndex=0))
        return "CJKFont"

    font_paths = []
    if platform.system() == "Windows":
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # Microsoft YaHei
            "C:/Windows/Fonts/simsun.ttc",  # SimSun
        ]
    else:
        font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]

    for p in font_paths:
        if os.path.exists(p):
            pdfmetrics.registerFont(TTFont("CJKFont", p, subfontIndex=0))
            return "CJKFont"
    # ReportLab ships metrics/encoding support for this standard Chinese CID
    # font. It keeps PDF generation functional on minimal Linux systems where
    # no CJK TTF/TTC is installed; an explicit/system font above remains the
    # preferred embedded-font path.
    fallback = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return fallback


def styles(cjk_font="CJKFont"):
    return {
        "title": ParagraphStyle(
            "Title",
            fontName=cjk_font,
            fontSize=20,
            leading=26,
            textColor=PRIMARY_COLOR,
            spaceAfter=12,
            alignment=1,
            wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            fontName=cjk_font,
            fontSize=10,
            leading=14,
            textColor=HexColor("#4a5568"),
            spaceAfter=18,
            alignment=1,
            wordWrap="CJK",
        ),
        "h1": ParagraphStyle(
            "H1",
            fontName=cjk_font,
            fontSize=14,
            leading=18,
            textColor=ACCENT_COLOR,
            spaceBefore=14,
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "H2",
            fontName=cjk_font,
            fontSize=12,
            leading=16,
            textColor=PRIMARY_COLOR,
            spaceBefore=10,
            spaceAfter=6,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "Body",
            fontName=cjk_font,
            fontSize=10.5,
            leading=16,
            textColor=HexColor("#2d3748"),
            spaceAfter=6,
            wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "Caption",
            fontName=cjk_font,
            fontSize=9,
            leading=12,
            textColor=HexColor("#718096"),
            alignment=1,
            spaceBefore=6,
            spaceAfter=10,
            wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            fontName=cjk_font,
            fontSize=10.2,
            leading=14,
            textColor=HexColor("#2d3748"),
            leftIndent=14,
            spaceAfter=4,
            wordWrap="CJK",
        ),
    }


def safe(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_pdf(out_pdf: str, meta: dict, images_dir: str):
    cjk = register_cjk_font()
    st = styles(cjk)

    doc = SimpleDocTemplate(
        out_pdf,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []
    story.append(Spacer(1, 1.1 * inch))
    story.append(Paragraph(safe(meta["title"]), st["title"]))
    story.append(
        Paragraph(
            f"作者：{safe(meta.get('author_handle',''))}<br/>链接：{safe(meta.get('url',''))}<br/>时间（UTC）：{safe(meta.get('datetime_utc',''))}",
            st["subtitle"],
        )
    )
    story.append(PageBreak())

    # Content
    story.append(Paragraph("正文（结构化提取）", st["h1"]))
    bullets = []

    blocks = meta.get("blocks")
    if not blocks:
        # Backward-compat: some extract.json uses "nodes" with inline images.
        blocks = []
        for n in meta.get("nodes", []):
            t = n.get("type")
            if t == "img":
                continue
            blocks.append({"type": t, "text": n.get("text", "")})

    for b in blocks:
        t = b.get("type")
        text = (b.get("text") or "").strip()
        if not text:
            continue
        if t == "h1":
            story.append(Paragraph(safe(text), st["h1"]))
        elif t == "h2":
            story.append(Paragraph(safe(text), st["h2"]))
        elif t == "li":
            bullets.append(ListItem(Paragraph(safe(text), st["bullet"]), bulletText="•"))
        elif t == "p":
            story.append(Paragraph(safe(text).replace("\n", "<br/>"), st["body"]))

        # flush bullets when we hit a new heading
        if t in ("h1", "h2") and bullets:
            story.insert(-1, ListFlowable(bullets, bulletType="bullet", leftIndent=0))
            bullets = []

    if bullets:
        story.append(ListFlowable(bullets, bulletType="bullet", leftIndent=0))

    story.append(PageBreak())

    # Images / tables
    story.append(Paragraph("图片 / 表格（原图）", st["h1"]))
    img_paths = sorted(glob.glob(os.path.join(images_dir, "*.*")))
    max_w = A4[0] - doc.leftMargin - doc.rightMargin
    if not img_paths:
        story.append(Paragraph("未检测到图片。", st["body"]))
    for idx, p in enumerate(img_paths, start=1):
        img = Image(p)
        w, h = img.imageWidth, img.imageHeight
        if w > max_w:
            scale = max_w / float(w)
            img.drawWidth = w * scale
            img.drawHeight = h * scale
        story.append(
            KeepTogether([img, Paragraph(f"图 {idx}：{safe(os.path.basename(p))}", st["caption"])])
        )

    doc.build(story)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", required=True, help="Path to article_*_extract.json")
    ap.add_argument("--images-dir", required=True, help="Path to media/images")
    ap.add_argument("--out", required=True, help="Output PDF path")
    args = ap.parse_args()

    extract_json = args.extract
    images_dir = args.images_dir
    out_pdf = args.out

    if not os.path.exists(extract_json):
        raise RuntimeError(f"Missing extract json: {extract_json}")

    with open(extract_json, "r", encoding="utf-8") as f:
        meta = json.load(f)

    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    build_pdf(out_pdf, meta, images_dir)
    print(out_pdf)

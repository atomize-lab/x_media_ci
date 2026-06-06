# X Media CI 工具代码说明

这套“CI”目录是为**长期保存 X（Twitter）内容**而设计的可检索存储规范：按账号/月份分片落盘，每条内容一个独立文件夹，并维护 JSONL 索引方便后续 agent 批处理。

## 1) 代码在哪里？

我已把本次会话中用到的脚本整理到（你可以直接打开查看/复用）：

- `x_media/CI/tools/scripts/`

> 注：之前我运行脚本时放在临时工作区；为方便你查看与复用，我已复制到 CI 目录下的 `tools/scripts/`。

## 2) 目录结构（CI）简述

```
x_media/
  CI/
    README.md                         # CI 规范说明（总览）
    indices/
      tweets.jsonl                    # 全量索引（每行一条 tweet/article 记录）
      by_handle/
        <handle>.jsonl                # 按账号索引
      by_date/
        YYYY/
          YYYY-MM.jsonl               # 按月份索引
    accounts/
      <handle>/
        tweets/
          YYYY/
            YYYY-MM/
              <timestamp>_<tweet_id>/
                tweet.json            # 本条内容的元信息（含导出物/媒体清单）
                exports/              # 导出文件（md/pdf/json/txt 等）
                media/
                  images/             # 图片原图
                  video/              # 视频（如有）
                  audio/              # 音频（如有）
                  raw/                # 原始分片/中间产物（可选）
                replies/              # 作者回复（如有）
```

### 每条内容的关键文件

- `tweet.json`
  - 统一入口：记录 tweet_url、时间、作者、媒体文件列表、导出文件列表、备注等。
- `exports/`
  - `article_*_full.md / .pdf / _extract.json`：**结构化提取**版本（能保持段落/标题/图片顺序时优先用它）。
  - `article_*_ocr_full.md / .pdf / .txt / _ocr_extract.json`：**OCR 补全**版本（当网页 DOM 抽取失败或缺字时，用截图+OCR保证覆盖全文；可能有少量识别误差）。
- `media/images/`
  - 保存文章/推文中的图片原图（优先 `name=orig`）。

## 3) 具体脚本与功能说明

转换器脚本都在 `x_media/CI/tools/scripts/`（**把已落盘内容转 md/pdf/OCR**）：

### A. gen_article_md.py
**用途**：把 `exports/article_*_extract.json` 生成 Markdown。

特点：
- 按节点顺序插入图片（尽量保持原文图片位置）
- 对 `$`、反引号等做最小转义，避免部分 Markdown 渲染器（MathJax/KaTeX）把 `$` 当公式导致显示异常

用法示例：
```
python gen_article_md.py --extract <extract.json> --images-dir <media/images> --out <out.md>
```

### B. make_article_pdf.py
**用途**：把 `exports/article_*_extract.json` 生成 PDF（中文字体已处理）。

特点：
- 正文（blocks/nodes）+ 图片列表页
- 支持 Windows 下微软雅黑/宋体作为 CJK 字体

用法示例：
```
python make_article_pdf.py --extract <extract.json> --images-dir <media/images> --out <out.pdf>
```

### C. ocr_screens_to_text.py
**用途**：把“分段截图”批量 OCR，然后做重叠去重合并为 TXT/MD。

特点：
- 对截图做简单预处理（灰度/放大/阈值/锐化）提升 OCR 成功率
- 用相似度匹配消除段与段之间的重复内容

用法示例：
```
python ocr_screens_to_text.py --glob "<screenshots_glob>" --out-txt out.txt --out-md out.md --title "..." --url "..." --author "@xxx" --datetime-utc "..."
```

### D. make_ocr_extract.py
**用途**：把 OCR 合并出的 `txt` 转成可被 PDF 脚本消费的 `ocr_extract.json`（blocks 结构）。

用法示例：
```
python make_ocr_extract.py --ocr-txt ocr.txt --out-json article_ocr_extract.json --title "..." --url "..." --author "@xxx" --datetime-utc "..." --screenshots-glob "<glob>"
```

### E. write_ocr_exports.py
**用途**：把 OCR 的 txt 写入标准的 `*_ocr_full.md` / `*_ocr_full.txt`（并附上本条的原图列表）。

### F. ocr_long_image.py
**用途**：对“超长整页截图”按高度切片 OCR（适合一次性 fullPage 截图的场景）。

## 3.5) 真正“去 X 拉内容”的抓取脚本（新增）

你指出的缺口在这里：之前只有转换器，没有“去 x.com 拉内容并落盘”的抓取器。

已新增两个入口（都在 `x_media/CI/tools/`）：

- `fetch_x.py`
  - **用途**：Playwright 抓取器（不走 X API），支持：
    - 单条 URL：抓 tweet/status → 下载图片/视频 → 写 `tweet.json` → 更新 `indices/*.jsonl`
    - 账号时间线：滚动收集 N 条 status URL 并逐条落盘
  - 依赖：
    - `pip install playwright`
    - `python -m playwright install chromium`
    - （可选）下载 m3u8 时需要 `ffmpeg`
  - 示例：
    - `python tools/fetch_x.py url --url "https://x.com/<handle>/status/<id>" --headed`
    - `python tools/fetch_x.py timeline --handle "<handle>" --limit 20 --headed`
    - 如需复用登录态：加 `--user-data-dir tools/.pw-userdata`

- `fetch_tweet.py`
  - **用途**：兼容桌面 GUI（`app_desktop/tweet_gui.py`）的固定调用方式：
    - `python fetch_tweet.py <tweet_url> --out <tweet_dir>`
  - 内部会转发到 `fetch_x.py url ...`

## 4) 推荐工作流（实战）

1. 优先用网页结构化提取生成：
   - `article_*_extract.json` → `gen_article_md.py` → `*_full.md`
   - `article_*_extract.json` → `make_article_pdf.py` → `*_full.pdf`
2. 若发现“缺字/不全”，用 OCR 补齐：
   - 分段截图 → `ocr_screens_to_text.py` → `ocr_full.txt / ocr_full.md`
   - `make_ocr_extract.py` → `ocr_extract.json`
   - `make_article_pdf.py` 用 `ocr_extract.json` 生成 `ocr_full.pdf`

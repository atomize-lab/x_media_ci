# CiteSeal Tools

CLI tools and scripts for the CiteSeal research archive.

## Capture

- `fetch_x.py` — Playwright-based capture of X/Twitter posts (single URL or timeline). Saves text, images, video, metadata, and source URLs with SHA-256 hashes.
- `fetch_tweet.py` — Compatibility wrapper for desktop GUI (`app_desktop/tweet_gui.py`), forwards to `fetch_x.py url`.

```bash
# Capture a single post
python tools/fetch_x.py url \
  --url "https://x.com/<handle>/status/<tweet_id>" \
  --ci-root ./citeseal \
  --user-data-dir tools/.pw-userdata

# Capture recent timeline posts
python tools/fetch_x.py timeline \
  --handle "<handle>" \
  --limit 20 \
  --ci-root ./citeseal
```

## Unified CLI

- `citeseal.py` — Unified CLI for export, validation, batch operations, and diagnostics.

```bash
python tools/citeseal.py validate --root ./citeseal/accounts
python tools/citeseal.py batch --root ./citeseal/accounts --op all --force
python tools/citeseal.py md --tweet-dir <item_dir>
python tools/citeseal.py pdf --tweet-dir <item_dir>
python tools/citeseal.py ocr --tweet-dir <item_dir>
python tools/citeseal.py export-agent --tweet-dir <item_dir>
python tools/citeseal.py manifest --tweet-dir <item_dir>
python tools/citeseal.py doctor
```

## Scripts (`scripts/`)

- `gen_article_md.py` — Generate Markdown from structured extract JSON.
- `make_article_pdf.py` — Generate PDF (CJK font support).
- `ocr_screens_to_text.py` — Batch OCR of screenshots with overlap deduplication.
- `make_ocr_extract.py` — Convert OCR text to extract JSON for PDF generation.
- `write_ocr_exports.py` — Write OCR results to standard export files.
- `ocr_long_image.py` — Slice and OCR full-page screenshots.
- `build_agent_bundle.py` — Build agent bundle (v1.0 spec) for a single item.
- `build_manifest.py` — Build provenance manifest (v1.0 spec) for a single item.
- `tweet_validate.py` — Validate tweet.json schema for archive items.

## Server (`server/`)

- `run_server.sh` — Start the FastAPI local API server.
- Endpoints: `/api/index/items`, `/api/item/{id}/context`, `/api/export/agent_bundle`, `/api/validate/item/{id}`

## Examples (`examples/`)

- `agent/` — Claude/Hermes prompt examples and HTTP client reference.
- `run_one_tweet_pipeline.sh` — End-to-end single-item pipeline script.

## Dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
# Optional: ffmpeg for video handling
```

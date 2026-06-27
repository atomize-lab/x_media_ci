# X Media CI

**Local-first X/Twitter media archiver for AI-agent content workflows.**

X Media CI turns public X/Twitter posts that you can already access into a durable local archive: text, images, videos, metadata, OCR/export artifacts, and JSONL indices that humans and AI agents can search later.

It is designed for builders who use X as a research, product, market, or content signal source and need a reproducible way to preserve useful posts before they disappear from the feed.

![X Media CI architecture](docs/assets/architecture.svg)

> Status: early-stage but functional. The current repo includes a Playwright-based X capture tool, a structured storage layout, Markdown/PDF/OCR/export helpers, a FastAPI local server, GitHub Actions validation, and a Flutter client skeleton for mobile/desktop browsing.

---

## Why this exists

X is full of useful but fragile context:

- product launches and demos
- agent/coding-tool workflows
- technical threads
- screenshots, videos, charts, and replies
- early signals for opportunity research and content creation

Normal bookmarks are not enough. They do not preserve media reliably, are hard to batch-process, and are not friendly to AI agents.

X Media CI stores each captured post as a small local package with stable metadata and indices, so later tools can:

- search by handle, date, tag, or tweet ID
- run OCR/export jobs
- turn posts into Markdown/PDF research notes
- browse archived posts from a phone
- feed selected items into AI-agent review, summary, and content pipelines

---

## What it does

| Capability | Current state |
|---|---|
| Capture a single X status URL | Implemented in `tools/fetch_x.py` |
| Capture recent posts from a timeline | Implemented in `tools/fetch_x.py timeline` |
| Save text + metadata | Implemented via `tweet.json` |
| Save images | Implemented, prefers original-size `pbs.twimg.com` media |
| Save video | Implemented best-effort, with MP4/HLS handling and optional `ffmpeg` |
| Maintain JSONL indices | Implemented: global, by-handle, by-date |
| Export to Markdown/PDF | Implemented for landed content |
| OCR screenshots / long images | Implemented helpers |
| Local HTTP API | Implemented FastAPI server under `tools/server/` |
| Mobile/desktop client | Flutter app skeleton under `tools/app/`; browse/remote/edit flows are started, local-device fetch is WIP |
| CI validation | GitHub Actions for Python lint/validation on Ubuntu + Windows |

---

## Responsible use

This project is **local-first** and intended for personal research, documentation, and maintainer workflows.

X Media CI does **not** provide an API bypass, credential bypass, paywall bypass, or public scraping service. Use it only for content you are authorized to access, with your own browser session, and respect platform terms, copyright, privacy, and deletion requests.

See [`SECURITY.md`](SECURITY.md) for the security and responsible-use policy.

---

## Repository layout

```text
.
├── README.md
├── SECURITY.md
├── docs/
│   ├── vision.md
│   ├── architecture.md
│   ├── roadmap.md
│   └── openai-oss-application.md
└── tools/
    ├── fetch_x.py              # Playwright X capture: URL + timeline
    ├── fetch_tweet.py          # Compatibility wrapper for desktop GUI
    ├── x_media_ci.py           # Unified CLI for export/validate/batch operations
    ├── scripts/                # Markdown/PDF/OCR/transcode/schema helpers
    ├── server/                 # FastAPI local API for phone/desktop clients
    ├── app/                    # Flutter client skeleton
    ├── android/                # adb sync + local serve helpers
    └── examples/               # Example configs and pipeline scripts
```

The archive data itself is usually stored outside the repo or under a local `accounts/` tree. Do not commit third-party media by default.

---

## Archive format

X Media CI stores each post as an independent directory:

```text
x_media/CI/
  accounts/
    <handle>/
      profile.json
      tweets/
        YYYY/
          YYYY-MM/
            <YYYYMMDDThhmmssZ>_<tweet_id>/
              tweet.json
              exports/
              media/
                images/
                video/
                audio/
                raw/
              replies/
                author_replies.jsonl
  indices/
    tweets.jsonl
    by_handle/<handle>.jsonl
    by_date/YYYY/YYYY-MM.jsonl
```

### `tweet.json` core fields

```json
{
  "tweet_id": "...",
  "tweet_url": "https://x.com/<handle>/status/<id>",
  "author_handle": "<handle>",
  "datetime_utc": "2026-06-27T00:00:00Z",
  "datetime_beijing": "2026-06-27T08:00:00+08:00",
  "text": "...",
  "media": [
    {
      "type": "image",
      "file": "media/images/example.jpg",
      "sha256": "...",
      "source_url": "https://pbs.twimg.com/media/..."
    }
  ],
  "components": {},
  "exports": []
}
```

JSONL indices make the archive friendly to shell tools, Python scripts, local search, and AI-agent batch processing.

---

## Quick start

### 1. Install Python dependencies

```bash
cd tools
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Optional but recommended for video handling:

```bash
ffmpeg -version
```

### 2. Capture a single post

```bash
python tools/fetch_x.py url \
  --url "https://x.com/<handle>/status/<tweet_id>" \
  --ci-root ./x_media/CI \
  --user-data-dir tools/.pw-userdata \
  --headed
```

The first headed run can be used to log in with your own browser session. Later runs can reuse the same `--user-data-dir`.

### 3. Capture a timeline

```bash
python tools/fetch_x.py timeline \
  --handle "<handle>" \
  --limit 20 \
  --ci-root ./x_media/CI \
  --user-data-dir tools/.pw-userdata
```

### 4. Validate or export landed content

```bash
python tools/x_media_ci.py validate --root ./x_media/CI/accounts
python tools/x_media_ci.py batch --root ./x_media/CI/accounts --op all --force
```

### 5. Start the local API server

```bash
X_MEDIA_CI_ROOT="$PWD/x_media/CI/accounts" bash tools/server/run_server.sh
# Open http://localhost:8765/docs
```

From Android on USB:

```bash
adb reverse tcp:8765 tcp:8765
# phone uses http://127.0.0.1:8765
```

See [`tools/server/README.md`](tools/server/README.md), [`tools/app/README.md`](tools/app/README.md), and [`tools/android/README.md`](tools/android/README.md).

---

## CLI overview

| Command | Purpose |
|---|---|
| `tools/fetch_x.py url --url ...` | Capture one X post |
| `tools/fetch_x.py timeline --handle ...` | Discover and capture recent timeline posts |
| `tools/x_media_ci.py md --tweet-dir ...` | Generate Markdown from landed metadata/extracts |
| `tools/x_media_ci.py pdf --tweet-dir ...` | Generate PDF |
| `tools/x_media_ci.py ocr --tweet-dir ...` | OCR screenshots/images into text and exports |
| `tools/x_media_ci.py transcode --tweet-dir ...` | Normalize media for playback |
| `tools/x_media_ci.py validate --root ...` | Validate archive schema |
| `tools/x_media_ci.py batch --root ... --op ...` | Run an operation across many tweet dirs |

---

## Use cases

### AI-agent memory and research

Archive high-signal posts and media so agents can later summarize, classify, compare, and cite them without repeatedly browsing X.

### Content and media workflows

Preserve source material for review-first content pipelines: screenshots, videos, text, metadata, and export notes live together.

### Opportunity and product research

Store launches, demos, and founder/build-in-public threads as a structured local case library.

### Mobile review

Run capture/export on a PC, then browse and trigger jobs from Android or desktop through the local FastAPI server and Flutter client.

---

## Documentation

- [`docs/vision.md`](docs/vision.md) — project positioning and long-term direction
- [`docs/architecture.md`](docs/architecture.md) — capture/storage/server/mobile architecture
- [`docs/roadmap.md`](docs/roadmap.md) — practical milestones toward a strong v1
- [`docs/openai-oss-application.md`](docs/openai-oss-application.md) — maintainer grant/application notes
- [`SECURITY.md`](SECURITY.md) — security and responsible-use policy

---

## Development

Run Python syntax checks:

```bash
python -m py_compile tools/fetch_x.py tools/x_media_ci.py tools/server/app.py tools/scripts/*.py
```

Run the existing CI-style lint entry:

```bash
cd tools
python x_media_ci.py lint
```

Run validation when you have a local archive:

```bash
python tools/x_media_ci.py validate --root ./x_media/CI/accounts
```

---

## Roadmap snapshot

Near-term priorities:

- stable unified CLI aliases (`xmc fetch`, `xmc timeline`, `xmc serve`)
- fixture-based tests without committing third-party media
- README screenshots / short demo GIF
- safer default capture limits and clearer error messages
- Flutter browse/detail screens with image/video preview
- documented plugin points for AI-agent summarization and tagging

See [`docs/roadmap.md`](docs/roadmap.md).

---

## License

MIT. See [`LICENSE`](LICENSE).

---

## Project description for GitHub

Suggested GitHub description:

```text
Local-first X/Twitter media archiver for AI-agent content workflows: save posts, images, videos, metadata, OCR/PDF exports, and JSONL indices.
```

Suggested topics:

```text
x twitter archive media-archiver local-first ai-agents playwright fastapi flutter ocr content-workflow research-tools
```

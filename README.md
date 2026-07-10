# CiteSeal

**Local-first, auditable, agent-ready research archive infrastructure.**

CiteSeal captures fragile web content — posts, images, videos, metadata — and turns it into structured, verifiable, local artifacts that humans and AI agents can consume long after the original page changes or disappears.

It is designed for builders who use social media as a research, product, or market signal source and need a reproducible way to preserve useful content as a **durable local evidence layer** — not a one-off screenshot or a clipboard paste.

![CiteSeal architecture](docs/assets/architecture.svg)

> **Status:** early-stage but functional. Playwright-based capture, structured storage with schema validation, Markdown/PDF/OCR export helpers, a FastAPI local server, GitHub Actions CI, 218 passing tests, agent bundle + provenance manifest exports, and a Flutter client skeleton for mobile/desktop review.

---

## Why this exists

Web content is fragile. Posts get deleted, media links expire, threads fragment, and AI agents that try to read live pages get unstable, inconsistent context.

CiteSeal solves this by capturing content into a **stable local format** with:

- structured metadata (`tweet.json`) and JSONL indices
- media saved at original quality where possible
- OCR/PDF/Markdown derived exports
- schema validation and fix-up tooling
- a local HTTP API for cross-device and agent access

The archive is filesystem-native, easy to back up, and friendly to shell tools, Python scripts, and AI-agent batch processing.

---

## Three core capabilities

| Capability | What it does |
|---|---|
| **Capture** | Playwright-based acquisition of single posts or timeline samples using your own authorized browser session. Text, images, video, metadata, and source URLs are saved with SHA-256 hashes. |
| **Validate** | Schema-driven validation and fix-up of every archived item. `tweet.json` is the single source of truth; derived artifacts (OCR, PDF, Markdown) are traceable exports, not opaque blobs. |
| **Agent-ready export** | JSONL indices, structured item directories, and Markdown exports that AI agents can read, search, and cite without browsing the web. Agents consume the archive output as a stable context layer. |

---

## Who this is for

- **AI-agent / research workflow builders** who need a stable local corpus instead of fragile live-web scraping
- **Researchers** tracking public technical discussions who want reproducible, citable evidence
- **Developers** building content pipelines that need structured source material with provenance
- **Maintainers** who want reproducible evidence and exports for notes, docs, and reports

## Who this is not for

- People looking for a bulk scraping service or API bypass
- People who want to redistribute third-party media
- People who need commercial-scale ingestion or automated engagement

---

## Responsible use

This project is **local-first** and intended for personal research, documentation, and maintainer workflows.

CiteSeal does **not** provide an API bypass, credential bypass, paywall bypass, or public scraping service. Use it only for content you are authorized to access, with your own browser session, and respect platform terms, copyright, privacy, and deletion requests.

See [`SECURITY.md`](SECURITY.md) for the full security and responsible-use policy.

---

## Quick start

### 1. Install dependencies

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
  --ci-root ./citeseal \
  --user-data-dir tools/.pw-userdata \
  --headed
```

The first headed run can be used to log in with your own browser session. Later runs can reuse the same `--user-data-dir`.

### 3. Capture a timeline

```bash
python tools/fetch_x.py timeline \
  --handle "<handle>" \
  --limit 20 \
  --ci-root ./citeseal \
  --user-data-dir tools/.pw-userdata
```

### 4. Validate or export landed content

```bash
python tools/citeseal.py validate --root ./citeseal/accounts
python tools/citeseal.py batch --root ./citeseal/accounts --op all --force
```

### 5. Start the local API server

```bash
CITESEAL_ROOT="$PWD/citeseal/accounts" bash tools/server/run_server.sh
# Open http://localhost:8765/docs
```

From Android on USB:

```bash
adb reverse tcp:8765 tcp:8765
# phone uses http://127.0.0.1:8765
```

---

## Archive format

Each captured post is an independent, self-describing directory:

```text
accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<tweet_id>/
  tweet.json          # canonical source of truth
  media/
    images/
    video/
    audio/
    raw/
  exports/            # derived: Markdown, PDF, OCR
  replies/
    author_replies.jsonl
```

JSONL indices make the archive friendly to shell tools, Python scripts, local search, and AI-agent batch processing:

```text
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
  "datetime_local": "2026-06-27T00:00:00Z",
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

---

## CLI overview

| Command | Purpose |
|---|---|
| `tools/fetch_x.py url --url ...` | Capture one post |
| `tools/fetch_x.py timeline --handle ...` | Discover and capture recent timeline posts |
| `tools/citeseal.py md --tweet-dir ...` | Generate Markdown from landed metadata/extracts |
| `tools/citeseal.py pdf --tweet-dir ...` | Generate PDF |
| `tools/citeseal.py ocr --tweet-dir ...` | OCR screenshots/images into text and exports |
| `tools/citeseal.py transcode --tweet-dir ...` | Normalize media for playback |
| `tools/citeseal.py validate --root ...` | Validate archive schema |
| `tools/citeseal.py batch --root ... --op ...` | Run an operation across many tweet dirs |

---

## Repository layout

```text
.
├── README.md
├── SECURITY.md
├── CONTRIBUTING.md
├── docs/
│   ├── vision.md
│   ├── architecture.md
│   ├── roadmap.md
│   ├── agent-integration.md
│   ├── agent-bundle-spec.md
│   ├── provenance.md
│   ├── cookbook-claude.md
│   ├── cookbook-hermes.md
│   ├── adr/
│   │   ├── 0001-agent-bundle-as-agent-consumption-layer.md
│   │   └── 0002-local-first-boundary.md
│   └── use-cases.md
├── tests/               # 219 pytest tests, synthetic fixtures
├── .github/workflows/   # CI: lint + validate + pytest (Ubuntu + Windows)
└── tools/
    ├── fetch_x.py              # Playwright X capture: URL + timeline
    ├── citeseal.py           # Unified CLI for export/validate/batch operations
    ├── scripts/                # Markdown/PDF/OCR/transcode/schema helpers
    ├── server/                 # FastAPI local API for phone/desktop clients
    ├── app/                    # Flutter client skeleton
    ├── android/                # adb sync + local serve helpers
    └── examples/               # Example configs and pipeline scripts
```

The archive data itself is usually stored outside the repo or under a local `accounts/` tree. Do not commit third-party media by default.

---

## Documentation

| Document | Description |
|---|---|
| [`docs/vision.md`](docs/vision.md) | Project positioning and long-term direction |
| [`docs/architecture.md`](docs/architecture.md) | Capture / storage / export / provenance / access architecture |
| [`docs/agent-integration.md`](docs/agent-integration.md) | How AI agents consume the archive as a context layer |
| [`docs/agent-bundle-spec.md`](docs/agent-bundle-spec.md) | Agent bundle v1.0 specification |
| [`docs/provenance.md`](docs/provenance.md) | Manifest layer: provenance, integrity, and transform tracing |
| [`docs/cookbook-claude.md`](docs/cookbook-claude.md) | How Claude reads the archive for summarization/citation |
| [`docs/cookbook-hermes.md`](docs/cookbook-hermes.md) | How Hermes builds trend reports from the archive |
| [`docs/use-cases.md`](docs/use-cases.md) | Real-world scenarios and workflows |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records — why key design choices were made |
| [`docs/roadmap.md`](docs/roadmap.md) | Milestones toward a stable v1 |
| [`SECURITY.md`](SECURITY.md) | Security and responsible-use policy |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute |
| [`CHANGELOG.md`](CHANGELOG.md) | Versioned change history |

---

## Development

```bash
# Install dev dependencies
python -m pip install -r requirements-dev.txt

# Run the full test suite
python -m pytest tests/ -v

# Lint
cd tools && python citeseal.py lint && cd ..

# Validate test fixtures
python tools/scripts/tweet_validate.py \
  tests/fixtures/accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890
```

All three must pass before pushing. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for details.

---

## Roadmap snapshot

**Completed in v0.7.0:**

- Agent bundle spec (`agent_bundle.schema.json`) and `cs export-agent` command
- Provenance manifest layer (capture environment, hashes, transform trace)
- FastAPI agent-access endpoints
- Claude/Hermes consumption cookbook
- v0.7.0 first public release

**Long-term backlog:**

- Unified CLI aliases (`cs fetch`, `cs timeline`, `cs serve`, `cs doctor`)
- Thread/reply capture, bookmark import
- Local full-text search (SQLite FTS)
- Plugin hooks for AI-agent summarization and tagging

See [`docs/roadmap.md`](docs/roadmap.md) for the full plan.

---

## Maintainer

This project is maintained by **atomize-lab** ([GitHub](https://github.com/atomize-lab)).

It is an independent, personal research tool. AI assistants (Claude, Hermes)
are used as development tools during engineering, but all design decisions,
code review, and release authority rest with the human maintainer.

---

## License

MIT. See [`LICENSE`](LICENSE).

Fields: [docs/tweet-json-fields.md](docs/tweet-json-fields.md).

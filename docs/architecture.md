# Architecture

X Media CI is organized around five layers:

1. capture
2. storage
3. provenance & integrity
4. export/validation + agent bundles
5. local access clients

```text
X / Twitter page
      │
      ▼
Playwright capture (`tools/fetch_x.py`)
      │
      ├── text + metadata
      ├── image/video/audio/raw media
      └── source URLs + hashes
      │
      ▼
Local archive (`accounts/`, `indices/`)
      │
      ├── CLI export/validate (`tools/citeseal.py`)
      ├── Markdown/PDF/OCR/transcode helpers (`tools/scripts/`)
      ├── Provenance manifest (`tools/scripts/build_manifest.py`)
      ├── Agent bundle export (`tools/scripts/build_agent_bundle.py`)
      └── FastAPI server (`tools/server/app.py`)
              │
              ├── Swagger/local browser
              ├── Flutter desktop/mobile client
              └── Android browser via adb reverse / same WiFi
```

## Capture layer

Primary entry point:

```bash
python tools/fetch_x.py url --url <status-url>
python tools/fetch_x.py timeline --handle <handle> --limit 20
```

Responsibilities:

- open X with Playwright;
- reuse a user-owned browser profile when `--user-data-dir` is supplied;
- extract tweet text, timestamp, handle, status ID, and media URLs;
- download images at original quality where possible;
- download video through best-effort MP4/HLS handling;
- write the canonical `tweet.json`;
- update JSONL indices.

The capture layer should remain conservative by default: small limits, explicit user input, clear errors, and no background mass scraping.

## Storage layer

The storage layout is intentionally simple and filesystem-native:

```text
accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<tweet_id>/tweet.json
```

Advantages:

- easy to inspect manually;
- stable paths for media and exports;
- no database server required;
- easy to sync with rsync/Syncthing/adb/cloud backup;
- JSON/JSONL works well with shell tools and AI agents.

The archive can later support optional SQLite or full-text-search indices, but JSONL should remain the portable source of truth.

## Export and validation layer

Unified CLI:

```bash
python tools/citeseal.py <op> --tweet-dir <dir>
python tools/citeseal.py batch --root <accounts-root> --op all
```

Implemented helper categories:

- Markdown generation
- PDF generation
- OCR over screenshots/long images
- OCR extract generation
- export writing
- video transcode
- schema validation/fixing

Design rule: exports are derived artifacts. `tweet.json` and media files should remain the stable core.

## Provenance and integrity layer

Each archived item can carry a provenance manifest (`manifest.json`) that
records the complete processing chain and file inventory with SHA-256
hashes.

```bash
citeseal manifest --tweet-dir <dir>
```

The manifest provides:

- **File inventory** — every file classified (`metadata`, `media`,
  `export`, `ocr`, …) with SHA-256 hash and size.
- **Transform chain** — ordered processing steps from `capture` →
  `article_md` → `article_pdf` → `ocr` → `transcode` → `manifest`,
  with inputs/outputs for each step.
- **Trust flags** — quick booleans (`has_media`, `has_ocr`,
  `media_verified`, `all_files_hashed`, …) for data-quality assessment.
- **Summary** — aggregate file counts and total size.

This layer makes the archive **auditable**: any downstream consumer (AI
agent, researcher, compliance tool) can verify that files have not been
tampered with and trace every derived artifact back to its source.

See [Provenance & Manifest](provenance.md) for full specification.

### Agent bundle export

The agent bundle is a portable, self-describing package derived from an
item directory:

```bash
citeseal export-agent --tweet-dir <dir> --output <bundle_dir>
```

The bundle (`bundle.json` + copied media) lets an AI agent consume the
item without understanding the project's internal directory structure.
The bundle's `provenance` field references the source manifest,
maintaining traceability from portable bundle back to archived item.

See [Agent Bundle Spec](agent-bundle-spec.md) for full specification.

## Local API server

Server:

```bash
bash tools/server/run_server.sh
```

The server exposes two layers of endpoints:

**Management endpoints** (for the Flutter app / human browsing):

- `GET /api/health`
- `GET /api/accounts`
- `GET /api/accounts/{handle}`
- `GET /api/index/tweets`
- `GET /api/tweet/{tweet_id}`
- `PUT /api/tweet/{tweet_id}`
- `POST /api/run`
- `GET /api/jobs/{job_id}`
- `GET /media/...`

**Agent-access endpoints** (v0.5, for AI agent programmatic consumption):

- `GET /api/index/items` — structured item list with trust signals
  (has\_media, has\_ocr, has\_article, validated), always reflects
  current on-disk state
- `GET /api/item/{item_id}/context` — agent-readable context for a
  single item: metadata, media list, text excerpt, trust flags, and
  manifest preview
- `POST /api/export/agent_bundle` — batch export one or more items as
  agent bundles; returns inline `bundle.json` for each item
- `POST /api/validate/item/{item_id}` — on-demand schema validation;
  returns structured errors and warnings without modifying files

The agent-access layer reuses the same library functions (`build_bundle`,
`build_manifest`, `validate_tweet_dir`) as the CLI, so the server never
re-implements logic that already has tests. See the cookbooks
(`docs/cookbook-claude.md`, `docs/cookbook-hermes.md`) for end-to-end
HTTP consumption recipes.

The server is a local control plane. It should not be exposed to the public internet without authentication and hardening.

## Mobile/desktop client

The Flutter app is intended to provide:

- archive browsing;
- tweet detail view;
- image/video preview;
- remote job trigger and job status;
- metadata editing;
- eventually local-device export/import helpers.

The recommended first mobile path is PC capture + local server + phone browsing. Phone-side X login/capture is intentionally not a v1 requirement.

## Trust boundaries

| Boundary | Rule |
|---|---|
| X access | Use only user-authorized content and browser sessions |
| Local archive | Treat media as private user data by default |
| FastAPI server | Bind locally or trusted LAN only unless hardened |
| AI-agent consumers | Provide structured artifacts; do not grant arbitrary filesystem write access by default |
| Public repo | Do not commit third-party media or private captures |

## Future extension points

- tagging/classification sidecars
- local vector index or SQLite FTS
- plugin hook after capture
- AI summary generation
- duplicate media detection
- richer thread/reply capture
- import/export bundles for sharing metadata without redistributing media

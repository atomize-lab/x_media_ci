# Changelog

All notable changes to CiteSeal are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- nothing yet

## [v0.7.0] - 2026-07-09

First public release. All core features are functional and tested (218 tests).

### Changed
- Renamed project from `x_media_ci` to **CiteSeal** (package name, CLI, env vars, docs, file paths)
- `datetime_beijing` field renamed to `datetime_local` for privacy neutrality
- README maintainer section now references the org account instead of a personal handle
- Example URLs in docs replaced with generic placeholders
- Internal review materials removed from project and git history
- GitHub repo description/topics updated to brand positioning

### Added - Agent bundle spec and export (v0.3)
- `schemas/agent_bundle.schema.json`: agent bundle v1.0 JSON Schema (item_id, source_platform, source_url, captured_at, author_handle, text_excerpt, assets, provenance, trust_flags, related_items)
- `docs/agent-bundle-spec.md`: full specification for agent bundle v1.0
- `tools/scripts/build_agent_bundle.py`: bundle generation with copy-on-export, optional SHA-256 media hashing
- `cs export-agent` CLI command for single-item bundle export
- `tools/examples/agent/` directory with Claude, Hermes, and HTTP client examples
- 39 unit tests for bundle generation, schema validation, and edge cases

### Added - Provenance and manifest layer (v0.4)
- `schemas/manifest.schema.json`: manifest v1.0 JSON Schema (metadata, files, transforms, trust_flags, summary)
- `tools/scripts/build_manifest.py`: manifest generator with full-file SHA-256 hashing, automatic transform-chain inference
- `docs/provenance.md`: provenance rules, verification methods, and bundle-manifest relationship
- `cs manifest` CLI command for single-item manifest generation
- 59 unit tests for manifest generation, hash verification, and transform inference

### Added - Agent-access API endpoints (v0.5)
- `GET /api/index/items`: structured item list for agent consumption
- `GET /api/item/{id}/context`: agent-readable context for an item
- `POST /api/export/agent_bundle`: batch bundle export
- `POST /api/validate/item/{id}`: on-demand validation

### Added - Agent consumption cookbook (v0.6)
- `docs/cookbook-claude.md`: how Claude reads the archive for summarization/citation
- `docs/cookbook-hermes.md`: how Hermes builds trend reports from the archive
- `tools/examples/agent/claude_prompt_example.md`, `hermes_workflow.md`, `http_client_example.py`

### Added - Narrative and maintainability (v0.2)
- Issue templates: bug report and feature request (`.github/ISSUE_TEMPLATE/`)
- Pull request template (`.github/pull_request_template.md`)
- `Makefile` with `test`, `lint`, `validate-fixtures`, `serve`, `smoke-cli` targets
- `cs doctor` command for environment diagnostics
- `docs/agent-integration.md`: agent consumption guide with Claude/Hermes/Codex examples
- `docs/use-cases.md`: three high-value scenarios with ROI comparison
- Maintainer section in README

### Other changes
- Rewrote `README.md` with new positioning: "local-first, auditable, agent-ready research archive infrastructure"
- Restructured `docs/roadmap.md` into grant-relevant track and long-term backlog
- Updated `docs/architecture.md` from four-layer to five-layer architecture (added provenance & integrity layer)
- Replaced Unicode CLI output symbols with ASCII for Windows compatibility
- Test count increased from 88 to 218 (all passing on Ubuntu + Windows CI)

## [v0.1.0] - 2026-07-08

First tagged release. The project is a working local-first archive toolkit with capture, validation, export, and local API capabilities.

### Added — Core capture and storage
- Playwright-based capture for single tweet URL and user timeline (`tools/fetch_x.py`)
- Structured storage convention: `accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<tweet_id>/`
- `tweet.json` schema with validation (`tools/scripts/tweet_schema.py`, `tools/scripts/tweet_validate.py`)
- Image and video best-effort saving with SHA-256 media hashing
- JSONL indices: global, by-handle, by-date (`tools/scripts/ci_common.py`)
- Markdown export with article extraction (`tools/scripts/gen_article_md.py`)
- PDF export (`tools/scripts/gen_pdf.py`)
- OCR text extraction from images (`tools/scripts/gen_ocr.py`)
- Video transcoding (`tools/scripts/transcode.py`)
- Batch operations: `citeseal.py batch --op all|md|pdf|ocr|transcode|validate`

### Added — Local API server
- FastAPI server with 9 endpoints: health, accounts, index, tweet CRUD, job runner, media serving
- `tools/server/run_server.sh` launcher

### Added — Flutter client
- Browse, detail, remote-edit, and server-connection screens
- Android local capture mode with WebView cookie injection
- Android APK release workflow

### Added — Testing and CI
- 88 passing tests with fully synthetic fixtures (no third-party media)
- `pytest.ini`, `requirements-dev.txt`, `tests/conftest.py`
- GitHub Actions CI: pyflakes lint + fixture validation + pytest (Ubuntu + Windows)
- Test fixture: `tests/fixtures/accounts/example_user/` with 3 tweet directories

### Added — Documentation and governance
- `README.md` with quickstart and architecture overview
- `docs/vision.md`: project positioning
- `docs/architecture.md`: four-layer architecture and trust boundaries
- `docs/roadmap.md`: versioned roadmap
- `CONTRIBUTING.md`: contribution guide
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1
- `SECURITY.md`: responsible-use policy
- MIT `LICENSE`

### Added — CLI utilities
- `citeseal.py lint`: pyflakes over bundled scripts
- `citeseal.py validate`: validate archive directories
- `citeseal.py batch`: run export/OCR/transcode operations in batch
- `citeseal.py fix`: auto-fix common `tweet.json` issues (handle prefix, datetime format)

## Pre-release history

- 2026-06-07: Initial commit, Android local capture mode, Flutter client, GitHub Actions CI
- 2026-06-08: Video capture improvements, Android storage fixes, PDF image sizing
- 2026-06-27: Open-source positioning, LICENSE, SECURITY.md, architecture docs
- 2026-07-08: Test suite, synthetic fixtures, CONTRIBUTING.md, CODE_OF_CONDUCT.md
- 2026-07-09: README rewrite, agent-integration docs, use-cases docs, roadmap restructure

---

### Versioning policy

- **Patch** (x.y.Z): bug fixes, no new features, no breaking changes.
- **Minor** (x.Y.0): new features, backward compatible.
- **Major** (X.0.0): breaking changes to `tweet.json` schema, CLI interface, or API contract.

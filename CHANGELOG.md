# Changelog

All notable changes to X Media CI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Issue templates: bug report and feature request (`.github/ISSUE_TEMPLATE/`)
- Pull request template (`.github/pull_request_template.md`)
- `Makefile` with `test`, `lint`, `validate-fixtures`, `serve`, `smoke-cli` targets
- `xmc doctor` command for environment diagnostics
- `docs/agent-integration.md`: agent consumption guide with Claude/Hermes/Codex examples
- `docs/use-cases.md`: three high-value scenarios with ROI comparison
- `docs/anthropic-grant-plan.md`: feasibility plan (internal reference)

### Changed
- Rewrote `README.md` with new positioning: "local-first, auditable, agent-ready research archive infrastructure"
- Restructured `docs/roadmap.md` into grant-relevant track and long-term backlog

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
- Batch operations: `x_media_ci.py batch --op all|md|pdf|ocr|transcode|validate`

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
- `x_media_ci.py lint`: pyflakes over bundled scripts
- `x_media_ci.py validate`: validate archive directories
- `x_media_ci.py batch`: run export/OCR/transcode operations in batch
- `x_media_ci.py fix`: auto-fix common `tweet.json` issues (handle prefix, datetime format)

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

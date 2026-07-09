# Roadmap

This roadmap is split into two tracks:

- **Grant-relevant track** — work that directly strengthens the project's position as a local-first, auditable, agent-ready research archive infrastructure. These are the highest-priority items.
- **Long-term backlog** — valuable but not time-critical. These can be deferred until after the core agent-ready layer is stable.

## Current state (v0.7 first public release)

Already present and tested:

- Playwright capture for URL and timeline workflows (`tools/fetch_x.py`)
- Structured storage with `tweet.json` schema and validation
- Image/video saving with SHA-256 media hashes
- JSONL indices (global, by-handle, by-date)
- Markdown/PDF/OCR/transcode export helpers
- FastAPI local server with 13 endpoints (9 management + 4 agent-access)
- Flutter client skeleton (browse/remote/edit flows)
- GitHub Actions CI: lint + fixture validation + pytest (Ubuntu + Windows)
- 218 passing tests with fully synthetic fixtures (no third-party media)
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- Issue/PR templates, CHANGELOG.md, Makefile, `cs doctor`
- docs: vision.md, architecture.md, agent-integration.md, use-cases.md, roadmap.md, agent-bundle-spec.md, provenance.md

---

## Grant-relevant track

These milestones build the agent-ready evidence layer that defines the project's core value.

### v0.2 — Narrative and maintainability (Week 1-2)

Make the project instantly understandable and visibly maintained.

- [x] Rewrite README with new positioning (local-first, auditable, agent-ready)
- [x] Add `docs/agent-integration.md`
- [x] Add `docs/use-cases.md`
- [x] Add issue/PR templates (`.github/ISSUE_TEMPLATE/`, `pull_request_template.md`)
- [x] Add `CHANGELOG.md` and v0.1.0 release draft
- [x] Add `Makefile` or `justfile` (test, lint, validate-fixtures, serve, smoke-cli)
- [x] Add `cs doctor` command (check ffmpeg, playwright, adb, Python deps, directory structure)
- [x] Add Maintainer section to README

### v0.3 - Agent bundle spec and export (Week 3)

Define the stable product that agents consume.

- [x] Add `schemas/agent_bundle.schema.json` (version, item_id, source_platform, source_url, captured_at, author_handle, text_excerpt, media, ocr_text, article_md_path, citation_label, trust_flags, provenance, related_items)
- [x] Add `docs/agent-bundle-spec.md`
- [x] Implement `tools/scripts/build_agent_bundle.py`
- [x] Add `cs export-agent` CLI command
- [x] Add `tools/examples/agent/minimal_bundle/` example
- [x] Add tests for bundle generation and schema validation

### v0.4 - Provenance and manifest layer (Week 4)

Make every archived item traceable from capture to export.

- [x] Add `schemas/manifest.schema.json` (capture_tool_version, capture_mode, browser_context, downloaded_assets, sha256, transforms_applied, validation_status, created_at)
- [x] Implement `tools/scripts/build_manifest.py`
- [x] Add transform trace fields to capture/transcode/OCR scripts
- [x] Add `docs/provenance.md`

### v0.5 - Agent-access API (Week 5)

Strengthen FastAPI as a query and export interface for agents.

- [x] Add `GET /api/index/items` (structured item list for agent consumption)
- [x] Add `GET /api/item/{id}/context` (agent-readable context for an item)
- [x] Add `POST /api/export/agent_bundle` (batch bundle export)
- [x] Add `POST /api/validate/item/{id}` (on-demand validation)
- [x] Add API tests (`tests/server/test_app_api.py`)
- [x] Update `docs/architecture.md` with agent-access layer

### v0.6 - Agent consumption cookbook (Week 6)

Prove that Claude, Hermes, and Codex can consume the archive in real workflows.

- [x] Add `docs/cookbook-claude.md` (how Claude reads the archive for summarization/citation)
- [x] Add `docs/cookbook-hermes.md` (how Hermes builds trend reports from the archive)
- [x] Add `tools/examples/agent/claude_prompt_example.md`
- [x] Add `tools/examples/agent/hermes_workflow.md`
- [x] Add `tools/examples/agent/http_client_example.py`
- [x] Document what agents should NOT do (no bulk scraping, no redistribution)

### v0.7 - First public release (Week 7)

- [x] Tag v0.7.0 with release notes and known limitations
- [x] Add README Quickstart with minimal demo data flow
- [ ] Add "good first issue" labels and contribution areas
- [ ] Add Architecture Decision Records (`docs/adr/0001-agent-bundle.md`, `docs/adr/0002-local-first-boundary.md`)

### v1.0 — Stable agent-ready archive (Week 11-12)

- [ ] Freeze agent bundle v1 schema
- [ ] Freeze core API endpoints
- [ ] Add migration notes
- [ ] Full test suite green
- [ ] Complete documentation navigation
- [ ] Release candidate with honest known-limitations list

---

## Long-term backlog

Valuable but not on the critical path. Pursue after the agent-ready layer is stable or when community demand emerges.

### Unified CLI

- [ ] `cs fetch`, `cs timeline`, `cs validate`, `cs fix`, `cs manifest`, `cs serve`
- [ ] Dry-run and no-media modes
- [ ] Capture summary output in JSON
- [ ] Normalize exit codes and error messages

### Archive quality

- [ ] Duplicate URL/tweet detection before downloading media
- [ ] Repair command for missing indices
- [ ] Optional tags and notes sidecar files
- [ ] Deduplicated media store

### Mobile review loop

- [ ] Finish Flutter browse/detail screens
- [ ] Image preview and video playback
- [ ] Remote job trigger UX for md/pdf/ocr/transcode/validate
- [ ] Server URL persistence and connection health indicator
- [ ] Android USB `adb reverse` quickstart docs

### Search and discovery

- [ ] Local full-text search (SQLite FTS) while preserving JSONL as source of truth
- [ ] Local vector search / embedding index
- [ ] Tagging/classification sidecars

### Capture extensions

- [ ] Richer thread/reply capture
- [ ] Bookmark/import workflows
- [ ] Browser extension or share-sheet integration
- [ ] OCR language profiles
- [ ] Multi-platform support (beyond X/Twitter)

### Platform and packaging

- [ ] Desktop packaging (PyInstaller)
- [ ] Android packaging
- [ ] Plugin hooks for AI summarization and tagging

---

## Good first issues

- improve README screenshots / demo GIF
- add fixture tests for edge cases
- improve validation error messages
- add a schema reference page
- document Windows/WSL setup
- improve Flutter tweet detail UI
- add sample archive generator
- add OCR language profile examples

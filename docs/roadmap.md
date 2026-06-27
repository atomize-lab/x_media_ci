# Roadmap

This roadmap is intentionally practical. The goal is to make X Media CI credible as a small but real open-source project, not to overbuild a platform.

## v0.1 — Existing foundation

Already present:

- Playwright capture for URL and timeline workflows
- local archive directory convention
- `tweet.json` metadata records
- image/video best-effort saving
- JSONL indices
- Markdown/PDF/OCR/transcode helpers
- FastAPI local server
- Flutter app skeleton
- GitHub Actions lint/validation workflow

## v0.2 — Make the project usable by a new user

Priority: documentation, examples, and safe defaults.

- [ ] Add a clear repository license.
- [ ] Add a demo screenshot/GIF to the README.
- [ ] Add a tiny synthetic fixture that contains no third-party media.
- [ ] Add `tests/fixtures/` and CI validation against the fixture.
- [ ] Add a single command quickstart script for local validation.
- [ ] Add GitHub repository description and topics.
- [ ] Add clearer Playwright login/profile instructions.
- [ ] Add responsible-use checks and warnings in capture commands.

## v0.3 — Unified CLI

Priority: reduce the number of entry points users need to remember.

Target command shape:

```bash
xmc fetch <status-url>
xmc timeline <handle> --limit 20
xmc validate <archive-root>
xmc export <tweet-dir> --format md,pdf
xmc serve --root <archive-root>
```

Tasks:

- [ ] Add a package-level CLI wrapper.
- [ ] Preserve existing `tools/fetch_x.py` and `tools/x_media_ci.py` compatibility.
- [ ] Normalize exit codes and error messages.
- [ ] Add dry-run and no-media modes.
- [ ] Add capture summary output in JSON.

## v0.4 — Better archive quality

Priority: make archived records easier to trust and reuse.

- [ ] Add media SHA256 hashing consistently.
- [ ] Record capture environment and tool version.
- [ ] Add duplicate URL/tweet detection before downloading media.
- [ ] Add a repair command for missing indices.
- [ ] Add a manifest format for portable archive bundles.
- [ ] Add optional tags and notes sidecar files.

## v0.5 — Mobile review loop

Priority: make phone usage real without moving X login to the phone.

- [ ] Finish Flutter browse/detail screens.
- [ ] Add image preview and video open/play support.
- [ ] Add remote job trigger UX for `md`, `pdf`, `ocr`, `transcode`, and `validate`.
- [ ] Add server URL persistence and connection health indicator.
- [ ] Add Android USB `adb reverse` quickstart docs with screenshots.

## v0.6 — AI-agent integration

Priority: make the archive easy for AI agents to consume safely.

- [ ] Add a stable `selected_items.jsonl` export format.
- [ ] Add summary/tag sidecar schema.
- [ ] Add examples for agent workflows: summarize, classify, create case notes.
- [ ] Add local-only API endpoints for query/search.
- [ ] Add optional SQLite FTS index while preserving JSONL as the source of truth.

## v1.0 — Stable local-first archive toolkit

v1.0 should mean:

- clear install path;
- repeatable capture of single URL and small timelines;
- durable archive schema;
- validation and repair tools;
- local server and mobile browsing path;
- docs that a new user can follow;
- tests that run without real X credentials or third-party media.

## Backlog

- richer thread/reply capture
- bookmark/import workflows
- browser extension or share-sheet integration
- OCR language profiles
- deduplicated media store
- local vector search
- desktop packaging
- Android packaging
- plugin hooks for AI summarization

## Contribution guide draft

Good first issues:

- improve README screenshots
- add fixture tests
- improve validation error messages
- add a small schema reference page
- document Windows/WSL setup
- improve Flutter tweet detail UI
- add sample archive generator

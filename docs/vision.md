# Vision

X Media CI is a local-first archive layer for X/Twitter content that can be used by humans, scripts, and AI agents.

The long-term goal is not to build a public scraper. The goal is to help people preserve and reuse content they can already access in a structured, private, reproducible way.

## Problem

X is increasingly used as a real-time source for:

- AI and developer-tool announcements
- build-in-public product updates
- short technical demos
- research and market signals
- visual evidence such as screenshots, charts, and videos

However, posts are fragile:

- bookmarks are platform-dependent
- media links can expire or change
- threads and replies are difficult to preserve as context
- AI agents need structured local files, not browser-only state
- mobile review workflows need fast access without re-opening X repeatedly

## Product thesis

A useful X archive should be:

1. **Local-first** — the user controls the archive and can back it up.
2. **Media-complete** — text without images/videos often loses the core context.
3. **Agent-friendly** — metadata and indices should be JSON/JSONL, not a black-box database only.
4. **Review-first** — the archive should support human review before content is reused or published.
5. **Cross-device** — heavy capture/export can run on a PC while a phone browses or controls the workflow.
6. **Responsible** — no bypassing permissions, paywalls, or platform access controls.

## Target users

- AI-agent builders collecting workflow examples
- researchers tracking public technical discussions
- creators preserving source material for review-first content workflows
- product/opportunity scouts building a local case library
- maintainers who want reproducible evidence and exports for notes, docs, and reports

## What success looks like

A v1 user should be able to:

1. capture a single X status URL into a local archive;
2. capture a small timeline sample from a handle they can access;
3. preserve text, images, video, source URLs, timestamps, and hashes;
4. run validation and export jobs;
5. browse the archive from a phone through a local server;
6. hand selected JSON/Markdown/media to an AI agent for summarization, tagging, or content drafting.

## Non-goals

- Public scraping-as-a-service
- Circumventing X login, permissions, rate limits, or paywalls
- Redistributing third-party media
- Replacing X's API for commercial-scale ingestion
- Automated posting or engagement farming

## Relationship to AI-agent workflows

X Media CI is the information-asset layer. It does not decide what is important by itself. Instead, it produces clean local artifacts that other systems can consume:

- trend radar tools can pass selected URLs to the archive;
- content pipelines can read Markdown/PDF exports;
- opportunity-radar systems can store posts as case evidence;
- mobile review tools can inspect source material before approval.

This separation keeps capture, storage, review, and publishing independently testable.

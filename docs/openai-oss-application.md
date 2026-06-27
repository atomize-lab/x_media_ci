# OpenAI Codex for Open Source application notes

This document helps the maintainer apply to OpenAI's Codex for Open Source program.

Official pages:

- https://developers.openai.com/codex/community/codex-for-oss
- https://openai.com/form/codex-for-oss/

> Do not submit false usage metrics. If the project is early-stage, say so clearly and emphasize active maintenance, roadmap, and ecosystem relevance.

## Recommended repository

```text
https://github.com/atomize-lab/x_media_ci
```

## Suggested role

Choose:

```text
Primary maintainer
```

Suggested text:

```text
I am the primary maintainer responsible for the project direction, architecture, documentation, release workflow, and ongoing development.
```

## Why this repository qualifies

Form limit: 500 characters.

```text
X Media CI is an early-stage local-first X/Twitter media archiver for AI-agent workflows. It preserves accessible posts, images, videos, metadata, OCR/PDF exports, and JSONL indices so researchers, maintainers, and agent builders can review and reuse public technical signals responsibly. The repo is actively maintained with Python capture/export tools, FastAPI, Flutter, and CI.
```

Character count: about 390.

## Interested in

Recommended:

- API credits for my project

Optional, only if the repository later adds stronger security use cases:

- Codex Security

## How API credits would be used

Form limit: 500 characters.

```text
API credits would support maintainer automation: PR review, test failure analysis, schema validation, release notes, documentation updates, and AI-assisted refactoring across the Python capture/export tools, FastAPI server, and Flutter client. Codex would also help build safer defaults, fixture-based tests, and better responsible-use documentation.
```

Character count: about 340.

## Anything else we should know?

Form limit: 500 characters.

```text
The project is intentionally local-first and does not provide a public scraping service or access-control bypass. It focuses on responsible personal archiving of content the user can already access, with structured artifacts for AI-agent review, research, and content workflows. The current roadmap prioritizes tests, documentation, mobile review, and safer capture defaults.
```

Character count: about 370.

## Fields the maintainer must fill personally

- First name
- Last name
- Email associated with ChatGPT account
- GitHub username
- OpenAI Organization ID

Find Organization ID at:

```text
https://platform.openai.com/settings/organization/general
```

## Pre-application checklist

Before submitting, improve the public repo page:

- [ ] Add or confirm a clear open-source license.
- [ ] Set GitHub description:

```text
Local-first X/Twitter media archiver for AI-agent content workflows: save posts, images, videos, metadata, OCR/PDF exports, and JSONL indices.
```

- [ ] Add GitHub topics:

```text
x twitter archive media-archiver local-first ai-agents playwright fastapi flutter ocr content-workflow research-tools
```

- [ ] Add at least one screenshot or demo GIF.
- [ ] Add a synthetic fixture and CI validation.
- [ ] Make one release after the documentation refresh.
- [ ] Keep the repository public.
- [ ] Keep the GitHub profile visibility public during application review.

## Honest positioning

Recommended wording:

- "early-stage but actively maintained"
- "local-first archive toolkit"
- "AI-agent-friendly structured artifacts"
- "responsible personal research and maintainer workflows"

Avoid claiming:

- broad adoption that does not exist yet
- high star/download numbers if absent
- authorization to archive content the user cannot access
- compliance guarantees that have not been legally reviewed

## Possible follow-up reply if OpenAI asks for more detail

```text
X Media CI is built around a filesystem-native archive schema and JSONL indices so users and agents can inspect the captured data without a proprietary database. The maintainer workload includes Playwright capture stability, media download handling, schema validation, OCR/export tooling, FastAPI endpoints, and a Flutter client for mobile review. API credits would be used only for open-source maintainer automation and code-quality workflows.
```

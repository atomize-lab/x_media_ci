# ADR 0002: Local-first boundary — capture vs. consumption separation

- **Status**: Accepted
- **Date**: 2026-06-27 (v0.7.0, codified from original design)

## Context

CiteSeal operates at the intersection of two domains with conflicting incentives:

1. **Web capture** — acquiring content from external platforms (X/Twitter, web
   pages) that have rate limits, terms of service, and anti-scraping measures.
2. **AI agent consumption** — feeding archived content to LLM-based agents
   (Claude, Hermes, Codex) for summarization, citation, and analysis.

If these two domains are not separated by a hard boundary, the project risks
becoming a scraping tool that feeds agents — which is both legally precarious
and misaligned with responsible AI principles. The boundary also has a
practical engineering benefit: capture is a fragile, platform-dependent
operation, while consumption is a stable, format-dependent operation. Mixing
them couples fragile code to stable code.

### Alternatives considered

1. **Agents capture directly** — rejected. Agents making live web requests
   bypass the user's authorized browser session, have no rate-limit awareness,
   and blur the line between "agent reads" and "agent collects." This is the
   exact anti-pattern the project exists to prevent.

2. **A capture API that agents call on demand** — rejected. Even if the API
   enforces authorization, it creates an automated capture pipeline driven by
   agent demand. This shifts capture decisions from human intent to agent
   intent, which is harder to audit and control.

3. **Cloud-hosted archive with agent access** — rejected. Removes the
   local-first property; introduces a server that could be abused as a
   redistribution endpoint; adds operational complexity inconsistent with a
   personal research tool.

## Decision

We enforce a **hard boundary** between capture and consumption:

```
┌─────────────────────────────────────────────────────────────┐
│                     CAPTURE LAYER                            │
│  (human-initiated, authorized browser session, local only)   │
│                                                              │
│  User decides what to capture → Playwright fetch → validate  │
│  → write to local filesystem (tweet.json + media + exports)  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                    ════════════════
                      BOUNDARY
                    ════════════════
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   CONSUMPTION LAYER                          │
│  (agent reads local files, never makes web requests)         │
│                                                              │
│  Agent bundle export → bundle.json → Claude/Hermes/Codex     │
│  Local HTTP API (cs serve) → read-only endpoints             │
└─────────────────────────────────────────────────────────────┘
```

### Boundary rules

1. **Capture is always human-initiated.** The user explicitly runs a capture
   command (`cs fetch`, `fetch_x.py`) with their own authorized browser
   session. There is no programmatic capture trigger from the consumption
   layer.

2. **Agents never make web requests.** The agent bundle and the local HTTP
   API are strictly read-only. No endpoint, CLI command, or library function
   in the consumption layer initiates network capture.

3. **All media stays local.** No redistribution, no upload, no sharing
   endpoint. The local HTTP API binds to `127.0.0.1` by default.

4. **No API bypass, credential bypass, or paywall bypass.** Capture uses the
   user's own browser session via Playwright. If the user cannot see the
   content in their browser, CiteSeal cannot capture it.

5. **Agents are downstream consumers, never upstream collectors.** This is
   the one-line summary of the entire boundary, and it is enforced through
   design (no capture code path reachable from consumption code), not just
   policy.

### Enforcement mechanisms

- **Code separation**: Capture scripts (`fetch_x.py`, timeline capture) and
  consumption scripts (`build_agent_bundle.py`, `server.py`) share no import
  path. The CLI (`citeseal.py`) routes them to separate subcommand groups.
- **HTTP API is read-only**: `cs serve` exposes only `GET` endpoints. There
  is no `POST /capture` or similar.
- **Local binding**: The API server binds to `127.0.0.1` by default,
  preventing remote access without explicit configuration.
- **No scraping helpers**: The project provides no bulk-capture, no
  follower-list crawling, no timeline pagination beyond what the user
  explicitly requests.

## Consequences

### Positive

- **Responsible-use alignment**: The boundary directly implements
  responsible AI principles — agents consume verified, user-authorized
  content rather than autonomously collecting from the live web.
- **Auditability**: Every archived item traces back to a human capture
  decision. The manifest records the capture step, and no automated path
  can create items without it.
- **Engineering isolation**: Capture fragility (platform changes, rate
  limits, auth expiry) does not affect consumption stability. Agent
  consumers see a stable format regardless of how capture evolves.
- **Legal defensibility**: The project is a personal archiving tool using
  the user's own authorized session, not a scraping service. The boundary
  makes this distinction structural, not just documented.

### Negative

- **No real-time agent capture**: Agents cannot request fresh captures on
  demand. If an agent needs content that isn't archived, it must ask the
  human to capture it. This is by design, but limits automation.
- **Manual capture burden**: The user must proactively capture content they
  anticipate needing. There is no "capture on mention" or background
  capture. Mitigated by the timeline capture command, which can batch-capture
  a user's recent posts in one action.
- **Onboarding friction**: New users must set up Playwright and an authorized
  browser session before they can capture anything. The sample archive
  generator (see roadmap) reduces this for testing, but real use requires
  the capture setup.

### Neutral

- The boundary is a design constraint, not a feature. It makes the project
  less powerful than an unconstrained scraping tool, but more trustworthy as
  an agent context layer. This trade-off is the project's core positioning.

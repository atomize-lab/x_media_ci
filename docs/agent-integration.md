# Agent Integration

How AI agents (Claude, Hermes, Codex, or any LLM-based workflow) consume the CiteSeal archive as a stable context layer.

---

## Why agents should not depend on live web pages

AI agents that read social media directly from the browser face several problems:

| Problem | Impact on agents |
|---|---|
| **Content mutability** | Posts get edited, deleted, or hidden. An agent that reads a page today may get different content tomorrow. |
| **Media inaccessibility** | Images, videos, and charts are not directly readable as text. An agent sees a URL, not the content. |
| **Context fragmentation** | Threads, replies, and quote-posts are spread across pages. Agents lose the relationship between items. |
| **No provenance** | A screenshot pasted into a prompt has no source URL, timestamp, or hash. It cannot be verified or cited. |
| **Rate and access limits** | Repeated browsing triggers blocks, captchas, or login walls. Agents waste turns on access, not reasoning. |
| **Non-reproducible runs** | If the input changes between runs, the agent's output cannot be reproduced or audited. |

CiteSeal solves these by capturing content into **stable local files** with structured metadata, media hashes, and derived text exports. Agents read the local archive instead of the live web.

---

## What the archive gives an agent

Each captured item is a self-describing directory:

```text
accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<tweet_id>/
  tweet.json          # structured metadata: text, media, timestamps, hashes, source URLs
  media/images/       # original-quality images
  media/video/        # video files
  exports/
    article.md        # Markdown rendering of the post
    ocr/ocr.txt       # OCR text extracted from images/screenshots
```

JSONL indices provide batch access:

```text
indices/
  tweets.jsonl        # every item, one JSON object per line
  by_handle/<h>.jsonl # per-author partition
  by_date/YYYY-MM.jsonl
```

An agent can:

1. **Read `tweet.json`** for structured metadata (text, author, timestamp, media list with hashes and source URLs).
2. **Read `exports/article.md`** for a clean Markdown rendering.
3. **Read `exports/ocr/ocr.txt`** for text extracted from images — useful when the post's meaning depends on a screenshot or chart.
4. **Scan `indices/tweets.jsonl`** to discover items by handle, date, or keyword without walking the directory tree.
5. **Cite items** using the stable `tweet_url`, `tweet_id`, and SHA-256 hashes as provenance.

---

## Two consumption modes

### Mode 1: Local file consumption

The agent reads archive files directly from the filesystem. This is the simplest and most reproducible mode.

**When to use:** The agent runs on the same machine as the archive, or the archive is mounted/synced to the agent's environment.

**Example — Claude reading a single item:**

```
Read the file at /path/to/archive/accounts/alice/tweets/2026/2026-07/20260708_180000_1234567890/tweet.json
and the Markdown export at .../exports/article.md.
Summarize the key claim and list every media asset with its SHA-256 hash.
```

Claude receives stable, structured input — no browser, no network, no content drift.

**Example — scanning the index:**

```python
import json

with open("indices/tweets.jsonl") as f:
    items = [json.loads(line) for line in f]

# Filter by handle
alice_items = [i for i in items if i["author_handle"] == "alice"]
for item in alice_items[:10]:
    print(item["tweet_id"], item["datetime_utc"], item["text"][:80])
```

The agent can then load full item directories for the items it wants to analyze.

### Mode 2: HTTP API consumption

The FastAPI server exposes the archive over local HTTP. This is useful when the agent runs on a different device or needs a query interface.

**When to use:** Mobile review, remote agents, or when you want a clean query API instead of filesystem access.

**Start the server:**

```bash
CITESEAL_ROOT="$PWD/citeseal/accounts" bash tools/server/run_server.sh
# API docs at http://localhost:8765/docs
```

**Key endpoints:**

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Server health check |
| `GET /api/accounts` | List all archived handles |
| `GET /api/accounts/{handle}` | Get profile + tweet count for a handle |
| `GET /api/index/tweets` | Get the global tweet index (JSONL items) |
| `GET /api/tweet/{tweet_id}` | Get full `tweet.json` for a specific item |
| `PUT /api/tweet/{tweet_id}` | Update item metadata (e.g., add tags) |
| `POST /api/run` | Trigger an export/OCR/transcode job |
| `GET /api/jobs/{job_id}` | Check job status |
| `GET /media/...` | Serve media files |

**Example — an agent fetching items via HTTP:**

```python
import requests

BASE = "http://localhost:8765"

# List accounts
accounts = requests.get(f"{BASE}/api/accounts").json()

# Get the global index
items = requests.get(f"{BASE}/api/index/tweets").json()

# Fetch full metadata for a specific item
item = requests.get(f"{BASE}/api/tweet/1234567890").json()
print(item["text"])
print([m["sha256"] for m in item.get("media", [])])
```

---

## Agent workflow examples

### Example 1: Claude summarizes a research thread

**Setup:** You have archived 20 posts from a technical thread using `fetch_x.py timeline`.

**Prompt to Claude:**

```
I have a local archive of posts from @alice at:
/path/to/archive/accounts/alice/tweets/

Read the index at indices/by_handle/alice.jsonl to see all items.
Then read the Markdown exports (exports/article.md) for the 5 most recent items.
Produce a structured summary with:
- Key claims (one per item)
- Supporting media (file path + hash)
- A citation block with tweet_url and datetime_utc for each item
```

Claude reads stable local files, produces a summary grounded in verifiable artifacts, and every claim is traceable to a source URL and hash.

### Example 2: Hermes builds a trend report

**Setup:** You run a weekly trend scan and archive interesting posts. Hermes (or any agent framework) consumes the archive to produce a report.

**Workflow:**

1. **Capture phase:** Use `fetch_x.py` to archive posts from 5 handles (limit 20 each).
2. **Export phase:** Run `citeseal.py batch --op all` to generate Markdown + OCR for every item.
3. **Agent phase:** Hermes reads `indices/tweets.jsonl`, filters by date range, loads relevant `article.md` files, and generates a trend report.
4. **Review phase:** The Flutter client lets you review and tag items before the report is finalized.

The key property: **the agent never touches the live web.** Its input is the local archive, which is stable, reproducible, and auditable.

### Example 3: Codex generates test fixtures from archived content

**Setup:** You want to create synthetic test fixtures based on real archive structure.

**Prompt to Codex:**

```
Look at the archive structure under:
/path/to/archive/accounts/example_user/tweets/2026/2026-07/

Read tweet.json for one item to understand the schema.
Then create a synthetic test fixture at tests/fixtures/accounts/synthetic_user/
that follows the same structure but uses placeholder text and a 1x1 PNG.
Validate it with: python tools/scripts/tweet_validate.py <fixture-dir>
```

Codex learns the schema from a real example, produces a compliant fixture, and validates it — all from local files.

---

## What agents should NOT do

- **Do not bulk-scrape.** CiteSeal is designed for small, explicit, user-authorized captures. Agents should not automate mass collection.
- **Do not bypass access controls.** Use only content you are authorized to access with your own browser session.
- **Do not redistribute media.** The archive is for local use. Agents should reference file paths and hashes, not republish third-party media.
- **Do not treat derived exports as authoritative.** `tweet.json` is the source of truth. OCR text, Markdown, and PDF are derived artifacts that may have transcription errors.
- **Do not modify the archive without explicit user action.** Agents can read freely, but writes (tagging, editing metadata) should go through the API or CLI with user awareness.

---

## Design principle: agents are downstream consumers

CiteSeal is the **evidence layer**, not the agent itself. The separation is intentional:

```
User authorizes capture
      ↓
CiteSeal captures + validates + exports
      ↓
Local archive (stable, auditable, filesystem-native)
      ↓
Agent reads archive → reasons → produces output
      ↓
Human reviews output before publishing
```

This separation keeps capture, storage, review, and publishing independently testable. The agent's output is only as trustworthy as its input — and the input is a verified local archive, not a volatile web page.

---

## Agent bundle + manifest: joint consumption

The archive now exports two complementary artifacts that agents consume together:

### Agent bundle (for consumption)

An agent bundle is a self-describing directory containing:

```text
<bundle_dir>/
  bundle.json          # manifest with all metadata, text, provenance, asset list
  media/               # copied media files (images, video, audio)
  article.md           # article markdown (if available)
  ocr_text.txt         # full OCR text (if available)
  tweet.json           # original source metadata (for reference)
```

The agent reads `bundle.json` to get everything it needs: text, media references
with hashes, provenance, and trust flags. No directory walking required.

**Export a bundle:**

```bash
python tools/citeseal.py export-agent \
  --tweet-dir accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<id> \
  --output my_bundle \
  --hash-media
```

See [`docs/agent-bundle-spec.md`](agent-bundle-spec.md) for the full specification.

### Manifest (for integrity)

A manifest (`manifest.json`) lives in the item directory and records:

- **File inventory** with SHA-256 hashes for every file
- **Transform chain** (capture -> article_md -> ocr -> export_agent -> manifest)
- **Trust flags** for quick data-quality assessment

**Generate a manifest:**

```bash
python tools/citeseal.py manifest \
  --tweet-dir accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<id>
```

See [`docs/provenance.md`](provenance.md) for the full specification.

### Joint citation standard

When an agent cites an archived item, it should reference **both** artifacts:

```text
[1] @author_handle, captured_at.
    "{text_excerpt first 80 chars}..."
    Source: {source_url}
    Bundle: bundle.json v{bundle_version}, exported {provenance.exported_at}
    Manifest: manifest.json, {N} files hashed
    Primary media SHA-256: {sha256 of first media entry}
    Transform chain: {transform steps, comma-separated}
    Trust: validated={trust_flags.validated}, media_verified={trust_flags.media_verified}
```

**Why both:**

| | Bundle | Manifest |
|---|---|---|
| **Optimized for** | Agent consumption (embedded text, media copies) | Integrity audit (full file hashes, transform chain) |
| **Location** | Separate portable directory | Item directory (in-place) |
| **Includes media** | Yes (copied files) | No (references by path) |
| **Includes full text** | Yes (in bundle.json) | No (references by path) |

The bundle gives the agent convenience; the manifest gives the verifier
auditability. Citing both gives the reader maximum confidence.

### Field authority

When bundle.json and manifest.json disagree (which should not happen in normal
operation, but agents should handle defensively):

| Field | Authority | Reason |
|---|---|---|
| File SHA-256 hashes | Manifest | Manifest hashes all files; bundle only hashes media |
| Text content | Bundle | Bundle embeds text; manifest references by path |
| Transform chain | Manifest | Bundle does not record transforms |
| Trust flags | Both (should match) | If they differ, flag for human review |
| Provenance metadata | Bundle | Bundle records export metadata; manifest records item metadata |

---

## Cookbooks

For step-by-step recipes with real commands and prompts:

- [`docs/cookbook-claude.md`](cookbook-claude.md) - Claude / Claude Code consuming bundles
- [`docs/cookbook-hermes.md`](cookbook-hermes.md) - Hermes Agent consuming bundles
- [`tools/examples/agent/`](../tools/examples/agent/) - quick-reference examples

---

## See also

- [`docs/architecture.md`](architecture.md) - the five-layer architecture and trust boundaries
- [`docs/agent-bundle-spec.md`](agent-bundle-spec.md) - agent bundle v1.0 specification
- [`docs/provenance.md`](provenance.md) - manifest layer and integrity verification
- [`docs/cookbook-claude.md`](cookbook-claude.md) - step-by-step Claude consumption recipes
- [`docs/cookbook-hermes.md`](cookbook-hermes.md) - step-by-step Hermes consumption recipes
- [`docs/use-cases.md`](use-cases.md) - real-world scenarios
- [`docs/vision.md`](vision.md) - project positioning and the agent-ready thesis
- [`SECURITY.md`](../SECURITY.md) - responsible-use policy

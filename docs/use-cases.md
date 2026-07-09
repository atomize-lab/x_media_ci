# Use Cases

Three high-value scenarios that show why a local-first, auditable, agent-ready archive matters. Each scenario describes the problem, the workflow, and the concrete value delivered.

---

## Scenario 1: Researcher archives a high-signal technical thread

### The problem

A researcher is tracking a technical discussion on X — say, a multi-post thread about a new agent architecture. The thread includes code screenshots, architecture diagrams, and reply chains with corrections and caveats.

The researcher needs to:

- preserve the full thread before it gets edited or deleted
- keep the images at original resolution (the diagrams matter)
- cite specific posts in a paper or report with verifiable provenance
- revisit the content offline without re-browsing X

Bookmarks don't work: they depend on the platform, don't preserve media reliably, and can't be cited.

### The workflow

```bash
# 1. Capture the thread author's recent posts
python tools/fetch_x.py timeline \
  --handle "researcher_handle" \
  --limit 30 \
  --ci-root ./citeseal \
  --user-data-dir tools/.pw-userdata

# 2. Generate Markdown + OCR exports for every item
python tools/citeseal.py batch \
  --root ./citeseal/accounts \
  --op all --force

# 3. Validate the archive
python tools/citeseal.py validate --root ./citeseal/accounts
```

### What the researcher gets

Each post is now a self-describing directory:

```text
accounts/researcher_handle/tweets/2026/2026-07/20260708_140000_9876543210/
  tweet.json               # text, timestamps, source URL, media hashes
  media/images/diagram.png # original-resolution architecture diagram
  exports/
    article.md             # clean Markdown rendering
    ocr/ocr.txt            # text extracted from code screenshots
```

**Citation block** the researcher can paste into a paper:

```text
Source: https://x.com/researcher_handle/status/9876543210
Captured: 2026-07-08T14:00:00Z
Author: @researcher_handle
Media hash (SHA-256): a1b2c3d4...
```

Every claim is traceable. The archive is reproducible — a peer reviewer can verify the exact same content.

### Why this is better than alternatives

| Approach | Problem |
|---|---|
| Screenshot | No source URL, no timestamp, no hash, no structured metadata |
| Bookmark | Platform-dependent, media may expire, not citable |
| Copy-paste text | Loses images, loses context, no provenance |
| CiteSeal | Local, stable, structured, citable, media-complete |

---

## Scenario 2: Developer builds a local evidence corpus for content pipelines

### The problem

A developer runs a review-first content pipeline: they collect posts about AI tools, review them, and produce analysis threads or blog posts. They need a **local corpus** that:

- is structured and queryable (not a folder of screenshots)
- preserves media alongside text
- can be batch-processed by scripts
- feeds into their content production workflow without depending on live X access

### The workflow

```bash
# 1. Weekly capture from 5 source handles
for handle in alice bob carol dave eve; do
  python tools/fetch_x.py timeline \
    --handle "$handle" \
    --limit 20 \
    --ci-root ./citeseal \
    --user-data-dir tools/.pw-userdata
done

# 2. Export everything to Markdown
python tools/citeseal.py batch \
  --root ./citeseal/accounts \
  --op md --force

# 3. Start the local API server
CITESEAL_ROOT="$PWD/citeseal/accounts" bash tools/server/run_server.sh
```

### What the developer gets

**Queryable corpus via JSONL indices:**

```python
import json

# Load the global index
with open("indices/tweets.jsonl") as f:
    items = [json.loads(line) for line in f]

# Filter by date range
import datetime
week_items = [
    i for i in items
    if "2026-07-01" <= i["datetime_utc"][:10] <= "2026-07-07"
]

# Group by author
from collections import defaultdict
by_author = defaultdict(list)
for item in week_items:
    by_author[item["author_handle"]].append(item)

for author, posts in by_author.items():
    print(f"{author}: {len(posts)} posts")
```

**Content pipeline integration:**

```python
# For each item, load the Markdown export and feed it to the next stage
for item in week_items[:5]:
    md_path = f"accounts/{item['author_handle']}/tweets/.../{item['tweet_id']}/exports/article.md"
    with open(md_path) as f:
        markdown = f.read()
    # ... pass to content analysis, tagging, or draft generation
```

**Mobile review:** The developer opens the Flutter client on their phone, browses the week's captures via the local API, and tags items as "use" or "skip" before the content pipeline picks them up.

### Key value

The corpus is **independent of X availability.** If X is down, rate-limited, or the developer is offline, the pipeline still works — it reads local files. The JSONL format means standard tools (`jq`, `grep`, Python, shell) work without a database.

---

## Scenario 3: AI agent consumes structured archive for summarization and citation

### The problem

An AI agent (Claude, Hermes, or any LLM-based workflow) needs to:

- summarize a set of archived posts
- classify them by topic
- produce a research brief with citations
- do all of this **without browsing the live web**

Live web access is unreliable: pages change, media is inaccessible, rate limits trigger, and the agent's output becomes non-reproducible.

### The workflow

```bash
# 1. Archive is already captured and exported (Scenarios 1-2)

# 2. Agent reads the local archive — no browser needed
```

**Prompt to Claude:**

```
I have a local archive of AI-tool-related posts at:
/home/user/citeseal/

Read the global index at indices/tweets.jsonl to see all items.
Select items from 2026-07-01 to 2026-07-07.

For each selected item, read:
- tweet.json (structured metadata)
- exports/article.md (Markdown rendering)
- exports/ocr/ocr.txt (if it exists — text from screenshots)

Produce a research brief with:
1. Topic clusters (group related items)
2. Key findings (one sentence per cluster, with item citations)
3. Evidence appendix:
   - tweet_url
   - datetime_utc
   - author_handle
   - media SHA-256 hashes

Do NOT browse the web. Use only the local archive.
```

### What the agent produces

```markdown
## Research Brief: AI Tool Discussions (July 1-7, 2026)

### Cluster 1: Agent orchestration frameworks

**Finding:** Multiple authors discuss the limitations of single-agent systems
and the shift toward multi-agent orchestration.

- @alice (2026-07-03): "Single-agent systems hit a ceiling when tasks require
  specialized reasoning across domains..." [1]
- @carol (2026-07-05): "We replaced our monolithic agent with a 3-agent
  pipeline and saw a 40% reduction in error rates..." [2]

### Cluster 2: Local-first AI workflows

**Finding:** Growing interest in local-first architectures for AI agent
context management.

- @bob (2026-07-02): Shared a diagram showing a local archive feeding
  into an agent context layer. [3]

### Evidence Appendix

[1] https://x.com/alice/status/111... | 2026-07-03T10:00:00Z | sha256: a1b2...
[2] https://x.com/carol/status/222... | 2026-07-05T14:30:00Z | sha256: c3d4...
[3] https://x.com/bob/status/333... | 2026-07-02T09:15:00Z | sha256: e5f6...
```

### Why this matters

| Property | Live web access | CiteSeal archive |
|---|---|---|
| **Stability** | Content may change between runs | Fixed local files, immutable per capture |
| **Media access** | Agent sees URLs, not content | OCR text + file paths available |
| **Provenance** | No source URL or hash in prompt | Every item has URL, timestamp, SHA-256 |
| **Reproducibility** | Non-reproducible | Fully reproducible from local files |
| **Rate limits** | Subject to blocks/captchas | No network access needed |
| **Citation quality** | Agent may hallucinate sources | Sources are structured metadata |

The agent's output is only as trustworthy as its input. By grounding the agent in a verified local archive, every claim becomes traceable and every run becomes reproducible.

---

## Common patterns across all scenarios

1. **Capture is explicit and user-authorized.** No background scraping, no bulk automation. The user decides what to archive.
2. **`tweet.json` is the source of truth.** Derived artifacts (Markdown, OCR, PDF) are traceable exports, not authoritative.
3. **The archive is filesystem-native.** No database server, no opaque binary format. Standard tools work.
4. **Agents are downstream consumers.** CiteSeal captures and validates; agents read and reason. The separation is intentional.
5. **Everything is citable.** Source URL, timestamp, author, and media hashes are preserved for every item.

---

## See also

- [`docs/agent-integration.md`](agent-integration.md) — detailed guide on how agents consume the archive
- [`docs/architecture.md`](architecture.md) — the four-layer architecture and trust boundaries
- [`docs/vision.md`](vision.md) — project positioning and design principles
- [`SECURITY.md`](../SECURITY.md) — responsible-use policy

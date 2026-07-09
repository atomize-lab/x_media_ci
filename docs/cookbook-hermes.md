# Cookbook: Hermes Agent Consuming an Agent Bundle

> **Audience:** Developers who use Hermes Agent (or similar agent frameworks)
> to build research workflows on top of archived content.
> **Prerequisites:** CiteSeal installed, Hermes Agent running, at least one
> archived item on disk.

---

## Why Hermes + CiteSeal

Hermes Agent is an AI agent orchestration system with file-reading tools,
persistent memory, and multi-step workflow capabilities. CiteSeal produces
self-describing agent bundles that Hermes can consume as stable context.

The combination enables a workflow where:

1. **Human captures** content with CiteSeal (explicit, authorized)
2. **CiteSeal exports** an agent bundle (structured, hashed, provenance-traced)
3. **Hermes reads** the bundle via `read_file` tool (local, no network)
4. **Hermes reasons** across multiple bundles (cross-reference, summarize, audit)
5. **Human reviews** Hermes output before publishing

Hermes never touches the live web. Its input is the verified local archive.

---

## Quick start: end-to-end in a Hermes session

### Step 1: Export a bundle (terminal)

```bash
python tools/citeseal.py export-agent \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890 \
  --output /tmp/hermes_bundle \
  --hash-media
```

### Step 2: Generate a manifest for provenance (terminal)

```bash
python tools/citeseal.py manifest \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890 \
  --dry-run > /tmp/hermes_bundle/manifest_preview.json
```

### Step 3: Consume in Hermes (session)

In a Hermes session, simply ask:

```
Read the file /tmp/hermes_bundle/bundle.json.

Then:
1. Summarize the archived post in 2 sentences
2. List all media assets with their SHA-256 hashes
3. Check the provenance field - when was this captured and with what tool?
4. Check trust_flags - are there any data quality issues?
5. Produce a citation using the citation_label field
```

Hermes uses its `read_file` tool to load `bundle.json` directly. No browser,
no API calls, no content drift.

---

## Recipe 1: Multi-bundle trend report

**Goal:** Hermes reads multiple bundles and produces a trend report with citations.

**Setup:** Export several bundles from a timeline capture:

```bash
mkdir /tmp/trend_report

for dir in accounts/example_user/tweets/2026/2026-07/*/; do
  python tools/citeseal.py export-agent \
    --tweet-dir "$dir" \
    --output "/tmp/trend_report/$(basename "$dir")" \
    --hash-media
done
```

**Hermes prompt:**

```
I have agent bundles in /tmp/trend_report/. Each subdirectory has a bundle.json.

For each bundle:
1. Read bundle.json
2. Extract: item_id, author_handle, captured_at, text_excerpt (first 120 chars)
3. Check trust_flags.validated and trust_flags.has_media

Then produce a trend report:
- Date range covered
- Number of items, broken down by author
- Top 3 recurring topics (based on text_excerpt across all bundles)
- Items with media vs. text-only
- Any items with trust_flags issues (flag for human review)

Include a citations section with source_url and SHA-256 hash for each item.
```

**Why this is reliable:** Hermes reads self-describing JSON with a stable schema.
Every item it references has a real file path, a real hash, and a real source URL.
If Hermes mentions a claim, you can verify it against the bundle.

---

## Recipe 2: Provenance audit workflow

**Goal:** Hermes verifies that an archived item has not been tampered with since
manifest generation.

**Setup:**

```bash
# Generate manifest in the item directory
python tools/citeseal.py manifest \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890

# Export bundle
python tools/citeseal.py export-agent \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890 \
  --output /tmp/audit --hash-media
```

**Hermes prompt:**

```
Read the following files:
1. /tmp/audit/bundle.json (the agent bundle)
2. accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890/manifest.json (the provenance manifest)

Perform an audit:
1. For each media file in bundle.json, find the corresponding entry in manifest.json
   and verify the SHA-256 hashes match.
2. List the transform chain from manifest.json (capture -> article_md -> ocr -> export_agent -> manifest).
3. Check trust_flags in both files - are they consistent?
4. Report: PASS if all hashes match and flags are consistent, FLAG if any mismatch.

Output a structured audit report with:
- Item ID
- Source URL
- Transform chain (ordered)
- Hash verification results (per file)
- Trust flag comparison
- Final verdict
```

**What this proves:** Hermes can act as an automated audit agent. It cross-checks
two independent artifacts (bundle and manifest) and verifies cryptographic integrity
without trusting either one alone.

---

## Recipe 3: Automated research digest pipeline

**Goal:** Use Hermes as part of a recurring pipeline that produces a weekly
research digest from newly archived items.

**Pipeline:**

```
[Weekly cron]
    |
    v
1. Export bundles for new items (cs export-agent)
    |
    v
2. Generate manifests for new items (cs manifest)
    |
    v
3. Hermes reads all new bundles
    |
    v
4. Hermes produces a digest with citations
    |
    v
5. Hermes saves digest to /research/digests/YYYY-MM-DD.md
    |
    v
[Human reviews digest before publishing]
```

**Hermes session prompt (triggered by cron or manual):**

```
Read all bundle.json files under /tmp/weekly_bundles/.

For this week's digest:
1. Group items by theme (cluster by text_excerpt keywords)
2. For each theme, write:
   - Theme name
   - Items in this theme (with citation_label and captured_at)
   - 2-sentence summary of the theme
3. Flag any items where trust_flags.media_verified is false
4. Flag any items with no OCR text (trust_flags.has_ocr = false) but has_media = true
   (these may need manual OCR review)
5. Save the digest to /research/digests/$(date +%Y-%m-%d).md

Include a provenance footer:
- Total items processed
- Date range
- All source URLs and primary media hashes
```

**Key property:** The digest is reproducible. If you re-run the pipeline with the
same bundles, you get the same input. No live-web dependency means no drift.

---

## Recipe 4: Bundle + manifest joint citation

**Goal:** Hermes produces citations that reference both the bundle (for consumption)
and the manifest (for integrity verification), giving the reader maximum confidence.

**Hermes prompt:**

```
Read /tmp/audit/bundle.json and the corresponding manifest.json.

For each item, produce a joint citation in this format:

---
[1] @author_handle, captured_at.
    "{text_excerpt first 80 chars}..."
    Source: {source_url}
    Bundle: bundle.json v{bundle_version}, exported {provenance.exported_at}
    Manifest: manifest.json, {number of files} files hashed
    Primary media SHA-256: {sha256 of first media entry}
    Transform chain: {transform steps, comma-separated}
    Trust: validated={trust_flags.validated}, media_verified={trust_flags.media_verified}
---

This citation lets a reader:
1. Visit the original source (source_url)
2. Verify the archive hasn't been tampered (SHA-256 hash)
3. Understand what processing was applied (transform chain)
4. Assess data quality (trust flags)
```

**Why joint citation matters:** The bundle is optimized for agent consumption
(embedded text, media copies). The manifest is optimized for integrity (full file
hashes, transform chain). Citing both gives the consumer the convenience of the
bundle and the auditability of the manifest.

---

## What Hermes should NOT do with bundles

| Don't | Why |
|---|---|
| Auto-capture new content | Capture is a human decision; Hermes consumes, it does not collect |
| Republish media to external services | Bundles are for local research only |
| Modify bundle.json or manifest.json | These are immutable exports; modifications break provenance |
| Skip trust_flags checks | Flags exist to prevent acting on incomplete/corrupt data |
| Access source URLs live | The archive is the input; the live web is explicitly out of scope |

---

## Integration with Hermes skills

Hermes Agent supports custom skills. A natural integration pattern:

1. **Create a Hermes skill** that knows the CiteSeal bundle schema
2. **The skill** reads `bundle.json`, validates `bundle_version`, checks `trust_flags`
3. **The skill** produces structured output (summary, citation, audit verdict)
4. **The session** can chain multiple bundle reads into a workflow

This turns bundle consumption from ad-hoc prompting into a repeatable, skill-driven
workflow - which is exactly the agent-ready pattern CiteSeal is designed to support.

---

## See also

- [Agent Bundle Specification](agent-bundle-spec.md) - full schema reference
- [Provenance & Manifest](provenance.md) - manifest layer and integrity verification
- [Agent Integration](agent-integration.md) - conceptual guide for agent consumption
- [Claude Cookbook](cookbook-claude.md) - equivalent recipes for Claude
- [Hermes workflow example](../tools/examples/agent/hermes_workflow.md) - quick reference

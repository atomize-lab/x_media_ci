# Cookbook: Claude Consuming an Agent Bundle

> **Audience:** Developers and maintainers who want to feed archived content to
> Claude (or Claude Code CLI) as a stable, citable context layer.
> **Prerequisites:** CiteSeal installed, at least one archived item on disk.

---

## Why a cookbook

The [agent-integration guide](agent-integration.md) explains *why* agents should
consume local archives. This cookbook shows *how* - with real commands, real
prompts, and real expected output.

Claude is used here as a **downstream consumer**: it reads a verified local
artifact, reasons about it, and produces output that a human reviews before
publishing. Claude never touches the live web.

---

## Quick start: one-item end-to-end

### Step 1: Export a bundle from an archived item

```bash
# Assume you have an archived tweet at:
#   accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890/

python tools/citeseal.py export-agent \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890 \
  --output /tmp/my_bundle \
  --hash-media
```

This produces:

```
/tmp/my_bundle/
  bundle.json      # agent bundle manifest (the primary artifact)
  media/           # copied media files (images, video)
  article.md       # Markdown rendering (if available)
  ocr_text.txt     # OCR text (if available)
  tweet.json       # original source metadata
```

### Step 2: Verify the bundle with a manifest

```bash
python tools/citeseal.py manifest \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890 \
  --dry-run
```

The manifest confirms every file's SHA-256 hash and the transform chain
(capture -> article_md -> ocr -> export_agent -> manifest). You can cross-check
that the bundle's media hashes match the manifest's file hashes.

### Step 3: Point Claude Code at the bundle

```bash
claude --add-dir /tmp/my_bundle "Read /tmp/my_bundle/bundle.json and provide:
1. A 2-sentence summary of the archived post
2. A list of all media assets with their types and SHA-256 hashes
3. The provenance information (when captured, source URL, export tool)
4. Any trust_flags that indicate data quality issues
5. A suggested citation using the citation_label field"
```

Claude reads the local files - no browser, no network, no content drift. Every
claim it makes is traceable to a source URL and hash.

---

## Recipe 1: Summarize a single post with media verification

**Goal:** Claude reads one bundle, summarizes the content, and verifies media integrity.

**Prompt (Claude Code CLI):**

```bash
claude --add-dir /tmp/my_bundle "Read bundle.json in this directory.

Then:
1. Summarize the post text (use text_excerpt or text_full)
2. For each media[] entry, report: file path, type, alt_text (if any), and sha256 hash
3. Read ocr_text.txt if it exists - does the OCR text match the post's claims?
4. Check trust_flags.media_verified - if true, all declared media exists
5. Produce a citation block:

   Source: {source_url}
   Author: @{author_handle}
   Captured: {captured_at}
   Verified: SHA-256 {hash of primary media}"
```

**What Claude does:**

| Step | Claude action | Why it's reliable |
|---|---|---|
| Read bundle.json | Loads structured metadata | Schema-validated, not raw HTML |
| Check media hashes | Reads sha256 fields | Cryptographic verification |
| Read OCR text | Loads ocr_text.txt | Text extraction, not image guessing |
| Produce citation | Uses citation_label | Stable, reproducible reference |

---

## Recipe 2: Cross-reference multiple bundles

**Goal:** Claude reads several bundles and finds connections (threads, quotes, themes).

**Setup:** Export multiple bundles into a parent directory:

```bash
mkdir /tmp/research_bundles

python tools/citeseal.py export-agent \
  --tweet-dir path/to/tweet_a --output /tmp/research_bundles/a --hash-media

python tools/citeseal.py export-agent \
  --tweet-dir path/to/tweet_b --output /tmp/research_bundles/b --hash-media

python tools/citeseal.py export-agent \
  --tweet-dir path/to/tweet_c --output /tmp/research_bundles/c --hash-media
```

**Prompt:**

```bash
claude --add-dir /tmp/research_bundles "Read all bundle.json files under this directory.

For each bundle, extract:
- item_id, author_handle, captured_at, text_excerpt (first 100 chars)

Then:
1. Identify any bundles that reference each other via related_items[]
2. Find common themes across the posts
3. Flag any items where trust_flags.validated is false
4. Produce a summary table:

| Item ID | Author | Date | Theme | Valid | Related To |
"
```

**Why this works:** Claude reads self-describing JSON files with stable schemas.
It does not need to understand the project's directory layout - each bundle is
self-contained.

---

## Recipe 3: Provenance audit with manifest + bundle

**Goal:** Claude traces an item from capture to export, verifying no tampering.

**Setup:** Generate both a manifest and a bundle for the same item:

```bash
# Generate manifest (in the item directory)
python tools/citeseal.py manifest \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890

# Export bundle (to a separate directory)
python tools/citeseal.py export-agent \
  --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890 \
  --output /tmp/audit_bundle --hash-media
```

**Prompt:**

```bash
claude --add-dir /tmp/audit_bundle "You are auditing the provenance of an archived item.

Read bundle.json in this directory.

Then:
1. Report the provenance object: exported_at, export_tool, source_dir
2. List the transform chain that produced this item
   (the bundle's provenance references the source directory)
3. For each media[] entry, verify:
   - The sha256 hash exists
   - The file path is valid (check media/ directory)
4. Check trust_flags:
   - media_verified: were all declared media files present at export?
   - has_ocr: was OCR text extracted?
   - has_article: was article markdown generated?
5. Produce an audit verdict: PASS (all checks clear) or FLAG (list issues)"
```

**What this proves:** The bundle is not just "a JSON file" - it is a verifiable
artifact with cryptographic hashes, a documented transform chain, and trust flags
that a downstream agent can programmatically check.

---

## Recipe 4: Generate a research digest from a batch

**Goal:** Claude reads multiple bundles and produces a structured research digest
with citations.

**Setup:** Export 5-10 bundles from a timeline capture:

```bash
for dir in accounts/example_user/tweets/2026/2026-07/*/; do
  python tools/citeseal.py export-agent \
    --tweet-dir "$dir" \
    --output "/tmp/digest/$(basename "$dir")" \
    --hash-media
done
```

**Prompt:**

```bash
claude --add-dir /tmp/digest "Read all bundle.json files in this directory.

Produce a research digest with these sections:

## Executive Summary
(2-3 sentences summarizing the overall content)

## Key Items
For each item, provide:
- Citation: [citation_label]
- Date: captured_at
- Summary: 1-2 sentences
- Media: list of media types (image, video, none)
- Quality: trust_flags status

## Themes
Cross-reference the items - what topics appear repeatedly?

## Provenance
For each item, confirm: source_url, export_tool, media_verified

## Citations
List all items with their source URLs and SHA-256 hashes for verification."
```

**Output:** A research digest where every claim is grounded in a verified local
artifact with a traceable source URL and hash. No hallucinated URLs, no content
drift, no rate-limiting.

---

## What Claude should NOT do with bundles

| Don't | Why |
|---|---|
| Republish media files | Bundles are for local research, not redistribution |
| Bulk-export without user authorization | Export is a human decision, not an agent action |
| Trust OCR text blindly | OCR is a derived artifact; `tweet.json` is the source of truth |
| Modify bundle.json | The bundle is an immutable export; modifications break provenance |
| Access the source URL live | The whole point is to avoid the live web; the archive is the input |

---

## Citation format

When Claude cites an archived item, use this format:

```
[@author_handle, captured_at]. "{text_excerpt first 80 chars}...".
Source: {source_url}. Archive hash: {sha256 of primary media}.
Retrieved via CiteSeal agent bundle v{bundle_version}.
```

This gives the reader: the original source, the capture time, a content hash for
verification, and the archive tool version - all from a single bundle.json.

---

## See also

- [Agent Bundle Specification](agent-bundle-spec.md) - full schema reference
- [Provenance & Manifest](provenance.md) - manifest layer and integrity verification
- [Agent Integration](agent-integration.md) - conceptual guide for agent consumption
- [Hermes Cookbook](cookbook-hermes.md) - equivalent recipes for Hermes Agent
- [Claude prompt example](../tools/examples/agent/claude_prompt_example.md) - quick reference

# Claude / Claude Code: Consuming an Agent Bundle

## Prerequisites

Export a bundle first:

```bash
xmc export-agent \
  --tweet-dir path/to/tweet_dir \
  --output my_bundle \
  --hash-media
```

## Claude Code (CLI)

Point Claude Code at the bundle directory:

```bash
claude --add-dir my_bundle "Read my_bundle/bundle.json and provide:
1. A 2-sentence summary of the archived post
2. A list of all media assets with their types
3. The provenance information (when captured, source URL)
4. Any trust flags that indicate data quality issues"
```

## Claude (Web / API)

Copy the `bundle.json` content and paste it into your Claude conversation:

```
I'm sharing an agent bundle (JSON) from x_media_ci, a local-first media
archiver. Please:

1. Summarize the archived post in 2 sentences
2. List all media assets and their types
3. Check the trust_flags field — are there any quality concerns?
4. Suggest a citation for this item using the citation_label field

Here is the bundle.json:

---paste bundle.json content here---
```

## Advanced: Multi-Bundle Analysis

If you export multiple bundles into a parent directory:

```bash
mkdir bundles
xmc export-agent --tweet-dir tweet_a --output bundles/a
xmc export-agent --tweet-dir tweet_b --output bundles/b
xmc export-agent --tweet-dir tweet_c --output bundles/c
```

Then ask Claude Code to analyze them together:

```bash
claude --add-dir bundles "Read all bundle.json files under bundles/.
Identify common themes across the archived posts, and list any items
that reference each other via related_items."
```

## What Claude Can Do With Bundles

| Task | How |
|---|---|
| Summarize a post | Read `text_excerpt` / `text_full` |
| Describe media | Read `media[]` entries with `alt_text` |
| Verify provenance | Check `provenance.exported_at`, `source_url` |
| Assess data quality | Inspect `trust_flags` |
| Cross-reference items | Use `related_items[]` |
| Generate citations | Use `citation_label` |
| Read OCR text | Check `ocr_text` field |
| Read article | Follow `article_md_path` |

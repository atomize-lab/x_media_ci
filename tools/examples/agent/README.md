# Agent Bundle Examples

This directory contains runnable examples showing how AI agents can consume
agent bundles exported by `x_media_ci`.

## Quick Start

```bash
# 1. Export a bundle from a tweet directory
xmc export-agent \
  --tweet-dir path/to/tweet_dir \
  --output my_bundle \
  --hash-media

# 2. Consume it with your agent (see examples below)
```

## Files

| File | Description |
|---|---|
| [`claude_prompt_example.md`](claude_prompt_example.md) | Example prompt for Claude / Claude Code to read and summarize a bundle. |
| [`hermes_workflow.md`](hermes_workflow.md) | Example workflow for Hermes Agent to consume a bundle in a session. |
| [`http_client_example.py`](http_client_example.py) | Python script to fetch a bundle via the local HTTP server. |

## What is an Agent Bundle?

An agent bundle is a self-describing directory containing:

- `bundle.json` — the manifest with all metadata, text, provenance, and asset list
- `media/` — copied media files (images, video, audio)
- `article.md` — article markdown (if available)
- `ocr_text.txt` — full OCR text (if available)
- `tweet.json` — original source metadata (for reference)

See [`docs/agent-bundle-spec.md`](../../../docs/agent-bundle-spec.md) for the
full specification.

## Responsible Use

- Bundles are exported from **already-archived** items. This project does not
  provide scraping functionality.
- Always respect the original platform's Terms of Service.
- Bundles are for research, archiving, and review workflows on content you
  have legitimately captured.
- Do not use bundles to circumvent platform access restrictions.

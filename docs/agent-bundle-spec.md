# Agent Bundle Specification (v1.0)

> **Status:** Draft — stabilizing for v0.1.0 release.
> **Schema:** [`schemas/agent_bundle.schema.json`](../schemas/agent_bundle.schema.json)

## 1. What is an Agent Bundle?

An **agent bundle** is a self-describing JSON export of a single archived item (e.g., a tweet with its media, OCR text, and article). It is designed to be consumed directly by AI agents — Claude, Hermes, Codex, or any LLM-based workflow — without the agent needing to understand the project's internal directory layout.

The bundle solves a specific problem: **agents cannot reliably consume raw web pages**, and ad-hoc directory structures are fragile inputs. A bundle gives the agent:

- A single JSON file with all metadata, text, and provenance.
- Relative paths to media and export files, co-located in the same directory.
- A stable schema version so consumers can pin their parsing logic.

## 2. Bundle Structure

Each bundle is a **directory** containing:

```
<output_dir>/
  bundle.json          # The agent bundle manifest (required)
  media/               # Copied media files (if any)
    01.png
    02.png
  article.md           # Article markdown (if available)
  ocr_text.txt         # Full OCR text (if available)
  tweet.json           # Original source metadata (for reference)
```

The `bundle.json` file is the primary artifact. All other files are optional and depend on what the source item contains.

## 3. bundle.json Fields

### Required Fields

| Field | Type | Description |
|---|---|---|
| `bundle_version` | `"1.0"` | Schema version this bundle conforms to. |
| `item_id` | string | Unique identifier for the archived item (e.g., tweet_id). |
| `source_platform` | enum | `"x"`, `"twitter"`, or `"web"`. |
| `source_url` | string (uri) | Original URL of the item. |
| `captured_at` | string | ISO 8601 timestamp when the item was captured. |
| `author_handle` | string | Author handle without leading `@`. |
| `text_excerpt` | string | Full or truncated text of the item. |
| `assets` | array | List of all files included in the bundle. |
| `provenance` | object | Export metadata: `exported_at`, `export_tool`, `source_dir`. |

### Optional Fields

| Field | Type | Description |
|---|---|---|
| `text_full` | string | Full untruncated text (omitted if same as `text_excerpt`). |
| `media` | array | Media asset list with `file`, `type`, `path`, `alt_text`, `sha256`. |
| `ocr_text` | string | Full OCR text extracted from media. |
| `article_md_path` | string | Relative path to article markdown within the bundle. |
| `citation_label` | string | Suggested citation label (e.g., `@example_user, 2026-07-08`). |
| `trust_flags` | object | Quality indicators: `validated`, `has_media`, `has_ocr`, `has_article`, `media_verified`. |
| `related_items` | array | Related item IDs with relation type (`reply`, `quote`, `retweet`, `thread`). |

### assets[] Entry

Each entry in `assets[]` describes one file in the bundle directory:

```json
{
  "path": "media/01.png",
  "kind": "media",
  "size_bytes": 45678
}
```

| Field | Type | Description |
|---|---|---|
| `path` | string | Relative path within the bundle directory. |
| `kind` | enum | `metadata`, `media`, `ocr`, `article`, `export`, `context`, `manifest`. |
| `size_bytes` | integer | File size in bytes (optional). |

### provenance Object

```json
{
  "exported_at": "2026-07-09T10:00:00Z",
  "export_tool": "x_media_ci build_agent_bundle v0.1.0",
  "source_dir": "tests/fixtures/.../20260708_180000_1234567890",
  "schema_version": "tweet.json v1"
}
```

## 4. Design Principles

1. **Local-first**: Bundles are files on disk. No network calls required to consume them.
2. **Self-describing**: A consumer only needs `bundle.json` to understand the item. No external schema lookups at runtime.
3. **Copy-on-export**: Media and export files are **copied** into the bundle directory, not symlinked. This makes bundles portable.
4. **Provenance is mandatory**: Every bundle records where it came from, when it was exported, and which tool produced it. This enables audit trails.
5. **Forward-compatible**: Unknown fields are allowed. Consumers must ignore fields they don't understand.

## 5. Consuming a Bundle

### For Claude / Claude Code

```bash
# Export a bundle from a tweet directory
xmc export-agent --tweet-dir path/to/tweet_dir --output my_bundle

# Point Claude at the bundle
claude --add-dir my_bundle "Summarize the archived tweet in my_bundle/bundle.json"
```

### For Hermes Agent

```bash
# Export, then reference in a Hermes session
xmc export-agent --tweet-dir path/to/tweet_dir --output my_bundle
# In Hermes: "Read my_bundle/bundle.json and summarize the key claims"
```

### For any HTTP client

If the local server is running (`xmc serve`), bundles can be fetched via HTTP:

```python
import requests
r = requests.get("http://localhost:8000/agent-bundle/example_user/1234567890")
bundle = r.json()
print(bundle["text_excerpt"])
```

## 6. Text Truncation Rules

When `text_excerpt` is truncated:

- Maximum 280 characters (configurable via `--max-excerpt`).
- Truncated text ends with `...`.
- Full text is available in `text_full` if it differs from `text_excerpt`.

If the original text is ≤280 characters, `text_excerpt` contains the full text and `text_full` is omitted.

## 7. SHA-256 Hashing

Media files are optionally hashed. To enable hashing:

```bash
xmc export-agent --tweet-dir path/to/tweet_dir --output my_bundle --hash-media
```

This adds a `sha256` field to each `media[]` entry. Hashing is opt-in because it adds I/O cost for large media collections.

## 8. Validation

Bundles can be validated against the JSON Schema:

```bash
# Using python-jsonschema (if installed)
python -m jsonschema -i my_bundle/bundle.json schemas/agent_bundle.schema.json
```

The `build_agent_bundle.py` script also performs a structural self-check before writing the bundle, ensuring all referenced files exist in the output directory.

## 9. Versioning

- `bundle_version: "1.0"` is the initial stable version.
- Breaking changes increment the major version (2.0, 3.0, ...).
- Additive changes (new optional fields) do not increment the version.
- Consumers should check `bundle_version` and refuse to parse versions they don't support.

## 10. What Bundles Are Not

- **Not a bulk export format**: Bundles are per-item. Bulk export is a future concern.
- **Not a replacement for tweet.json**: The original `tweet.json` remains the source of truth. Bundles are a derived, agent-optimized view.
- **Not a scraping tool**: Bundles are exported from already-archived items. The project does not provide scraping functionality.
- **Not encrypted**: Bundles are plain files. Security is handled at the filesystem level.

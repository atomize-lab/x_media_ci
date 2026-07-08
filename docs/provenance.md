# Provenance & Manifest

> **Status:** Stable (v1.0) — July 2026
> **Schema:** [`schemas/manifest.schema.json`](../schemas/manifest.schema.json)
> **Generator:** `x_media_ci manifest --tweet-dir <path>`

## 1. Why provenance matters

Every archived item in `x_media_ci` originates from an external platform
(X/Twitter), then passes through a chain of local transforms: article
extraction, PDF rendering, OCR, transcoding, and agent bundle export.
Without a provenance record, a downstream consumer (AI agent, researcher,
audit workflow) cannot answer:

- Where did this file come from?
- What was the original source URL?
- Which files are derived from which?
- Has any file been tampered with after generation?
- What processing steps were applied?

The **manifest** (`manifest.json`) answers all of these in a single
machine-readable file that travels with the item directory.

## 2. Manifest structure

Each item directory contains a `manifest.json` with four layers:

```
manifest.json
├── metadata          # item_id, source_url, captured_at, author_handle
├── files[]           # complete file inventory with SHA-256 hashes
├── transforms[]      # ordered processing chain (capture → export → manifest)
├── trust_flags       # quick booleans for data-quality assessment
└── summary           # aggregate counts and sizes
```

### 2.1 File inventory

Every file in the item directory is listed with:

| Field | Description |
|---|---|
| `path` | Relative path from the item directory root |
| `kind` | Classification: `metadata`, `media`, `media_raw`, `export`, `ocr`, `article`, `manifest`, `other` |
| `size_bytes` | File size in bytes |
| `sha256` | SHA-256 hash (64 hex chars) |
| `derived_from` | (optional) Source file paths this file was derived from |
| `transform_id` | (optional) ID of the transform that produced this file |

### 2.2 Transform chain

Transforms are ordered chronologically and represent the processing
pipeline:

```
capture → article_md → article_pdf → ocr → transcode → export_agent → manifest
```

Not all steps are present for every item — only steps whose outputs
exist on disk are included. The `manifest` step is always last (it
records itself).

Each transform records:

| Field | Description |
|---|---|
| `id` | Unique identifier within the manifest (e.g., `t1_capture`) |
| `step` | Step type: `capture`, `transcode`, `ocr`, `article_md`, `article_pdf`, `fix`, `validate`, `export_agent`, `manifest` |
| `tool` | Script/tool that performed the transform |
| `started_at` / `completed_at` | ISO 8601 timestamps |
| `status` | `success`, `warning`, `error`, `skipped` |
| `inputs[]` | Paths of input files consumed |
| `outputs[]` | Paths of output files produced |
| `notes` | Human-readable notes |

### 2.3 Trust flags

Quick booleans for automated data-quality assessment:

| Flag | True when |
|---|---|
| `has_metadata` | `tweet.json` exists |
| `has_media` | At least one media file (image/video/audio) exists |
| `has_exports` | At least one export file (PDF, article extract) exists |
| `has_ocr` | OCR text files exist |
| `has_article` | Article markdown exists |
| `media_verified` | All media files declared in `tweet.json` exist on disk |
| `all_files_hashed` | Every file has a valid SHA-256 hash |

## 3. Generation

### CLI

```bash
# Generate manifest for a single item
x_media_ci manifest --tweet-dir accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890

# Dry-run (print to stdout, don't write)
x_media_ci manifest --tweet-dir <path> --dry-run
```

### Library

```python
from build_manifest import build_manifest

manifest = build_manifest(
    Path("accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890"),
    pretty=True,
    write=True,
)
```

## 4. Verification

### 4.1 Integrity check

To verify that no files have been modified after manifest generation:

```python
import hashlib, json
from pathlib import Path

manifest = json.loads(Path("manifest.json").read_text())
for entry in manifest["files"]:
    actual = hashlib.sha256(
        Path(entry["path"]).read_bytes()
    ).hexdigest()
    if actual != entry["sha256"]:
        print(f"TAMPERED: {entry['path']}")
```

### 4.2 Schema validation

```bash
python -c "
import json, jsonschema
schema = json.load(open('schemas/manifest.schema.json'))
data = json.load(open('manifest.json'))
jsonschema.validate(data, schema)
print('Valid')
"
```

## 5. Relationship to agent bundles

The manifest and the agent bundle serve complementary purposes:

| | Manifest | Agent Bundle |
|---|---|---|
| **Scope** | Single item directory | Single item, portable |
| **Purpose** | Provenance & integrity | AI agent consumption |
| **Location** | `manifest.json` in item dir | Separate `bundle/` directory |
| **Includes media** | No (references by path) | Yes (copies media files) |
| **Includes full text** | No (references by path) | Yes (embedded in bundle.json) |
| **Hashed** | Yes (all files SHA-256) | Yes (media files SHA-256) |

An agent bundle's `bundle.json` includes a `provenance` field that
references the source manifest, allowing an agent to trace back from
a portable bundle to the original archived item.

## 6. Design decisions

### 6.1 Why infer transforms instead of logging them?

The manifest generator infers the transform chain from the file
structure rather than reading runtime logs. This decision was made
because:

1. **Retroactive compatibility** — existing items created before the
   manifest system have no logs, but their file structure is intact.
2. **Simplicity** — no need to maintain a separate log file or
   database.
3. **Verifiability** — the inferred chain can be verified against
   the actual files on disk.

The trade-off is that the inferred timestamps for past transforms
default to `captured_at` (the original capture time), which is
approximate. The `manifest` step itself always uses the actual
generation timestamp.

### 6.2 Why SHA-256?

SHA-256 is chosen over MD5 or SHA-1 for:

- **Collision resistance** — no known practical collisions.
- **Industry standard** — universally supported across tools and
  languages.
- **Audit compliance** — meets NIST and compliance requirements.

### 6.3 Why exclude `manifest.json` from its own file inventory?

The manifest describes the state of the directory *before* it was
generated. Including itself would create a self-referential hash
problem (the hash of the manifest would change when the manifest is
written, because the manifest would then contain its own hash).

The `manifest` transform step records `manifest.json` as its output,
providing provenance for the manifest file itself without the
self-reference problem.

## 7. Future enhancements

- **Incremental updates** — re-generate only changed file hashes
  instead of re-hashing everything.
- **Runtime log integration** — optionally read transform logs from
  a `.transforms/` directory for more accurate timestamps.
- **Cross-item manifests** — a collection-level manifest that
  references individual item manifests.
- **Signed manifests** — GPG or PGP signatures for non-repudiation.

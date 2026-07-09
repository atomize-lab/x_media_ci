# ADR 0001: Agent bundle as the agent consumption layer

- **Status**: Accepted
- **Date**: 2026-06-15 (v0.3)

## Context

CiteSeal's internal directory layout is optimized for **archival integrity**, not
for **agent consumption**. A single archived item spreads across multiple files
and directories:

```
accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<id>/
├── tweet.json          # metadata
├── media/
│   ├── images/
│   │   ├── 01.png
│   │   └── 02.png
│   └── video/
│       └── clip.mp4
├── exports/
│   ├── article.md
│   ├── article.pdf
│   └── ocr_text.txt
└── manifest.json       # provenance
```

An AI agent (Claude, Hermes, Codex) that wants to summarize or cite this item
would need to:

1. Discover which files exist
2. Read `tweet.json` to understand metadata
3. Read `article.md` or `ocr_text.txt` for text content
4. Cross-reference `manifest.json` for provenance
5. Map media files to their descriptions

This is fragile: agents trip over missing files, inconsistent paths, and
platform-specific metadata. The problem compounds when multiple agents or
multiple workflows consume the same archive -- each re-implements the same
discovery logic.

### Alternatives considered

1. **Let agents read the raw directory** — rejected. Every agent re-implements
   discovery; no schema guarantee; breaks when layout changes.

2. **A database export (SQLite)** — rejected. Adds a runtime dependency;
   binary format is not human-readable; not diff-friendly; ties consumers to
   a query language.

3. **A single consolidated JSON with embedded media (base64)** — rejected.
   Bloats file size for video/audio; base64-encoding binary media is wasteful;
   hard to inspect manually.

4. **A symlink-based bundle** — rejected. Symlinks are not portable across
   operating systems (especially Windows); bundles would break when copied.

## Decision

We introduce the **agent bundle** as a separate, portable export format that
sits between the archive and the agent consumer.

```
Archive (source of truth)  --export-->  Agent Bundle (consumption layer)  <--read--  Agent
```

A bundle is a **directory** containing:

- `bundle.json` — a single self-describing JSON file with all metadata, text,
  and provenance
- Copied (not symlinked) media files
- Copied article/OCR exports

### Key design rules

1. **Copy-on-export**: Media and exports are copied into the bundle directory,
   not symlinked. Bundles are portable — they can be zipped, emailed, or
   attached to an agent session without path dependencies.

2. **Self-describing**: A consumer only needs `bundle.json` to understand the
   item. No external schema lookups at runtime. Unknown fields are allowed
   (forward-compatible).

3. **Provenance is mandatory**: Every bundle records `exported_at`,
   `export_tool`, `source_dir`, and `schema_version`. This enables audit
   trails and traceability back to the original archive.

4. **Per-item, not bulk**: Bundles are exported one item at a time. Bulk
   export is a future concern, deferred until consumption patterns stabilize.

5. **Schema-versioned**: `bundle_version: "1.0"` is the initial stable
   version. Breaking changes increment the major version; additive changes
   (new optional fields) do not. Consumers check the version and refuse to
   parse versions they don't support.

## Consequences

### Positive

- **Stable agent interface**: Agents consume a versioned, self-describing
  format. Archive layout changes do not break consumers as long as the bundle
  schema is respected.
- **Portability**: Bundles can be shared, archived, or attached to agent
  sessions independently of the source archive.
- **Provenance chain**: Every bundle traces back to its source via the
  `provenance` field, supporting citation and audit use cases.
- **Forward compatibility**: The "ignore unknown fields" rule allows the
  schema to grow additively without breaking existing consumers.

### Negative

- **Storage duplication**: Media is copied, not referenced. A large archive
  with many exported bundles uses more disk space. Mitigated by the fact that
  bundles are opt-in exports, not automatic.
- **Freshness**: A bundle is a snapshot at export time. If the source item is
  later updated (e.g., re-OCR'd), the bundle is stale until re-exported.
  The `exported_at` timestamp makes staleness detectable.
- **Schema maintenance burden**: The bundle schema must be versioned and
  maintained. Breaking changes require a major version bump and consumer
  migration.

### Neutral

- The manifest (`manifest.json`) remains the source of truth for provenance
  within the archive. The bundle's `provenance` field references the manifest,
  creating a two-layer provenance chain: bundle → manifest → archive.

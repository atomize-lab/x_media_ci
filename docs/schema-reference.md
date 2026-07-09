# Schema reference

Consolidated field reference for CiteSeal v1 artifacts.

## tweet.json

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tweet_id` | string | yes | Platform post id (string of digits). |
| `tweet_url` | string | yes | Canonical post URL. |
| `author_handle` | string | yes | Author handle without leading @ (recommended). |
| `datetime_utc` | string | yes | Capture/post time in UTC (ISO-8601 preferred). |
| `text` | varies | no | Post body text. |
| `media` | varies | no | List of media descriptors (file, type, optional alt_text). |
| `exports` | varies | no | List of derived export artifacts under exports/. |
| `datetime_local` | varies | no | Local timestamp with offset. |
| `components` | varies | no | Declared content components (text, images, ...). |
| `replies` | varies | no | Optional reply thread metadata. |

## agent_bundle.schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bundle_version` | string | yes | Version of the agent bundle spec this file conforms to. |
| `item_id` | string | yes | Unique identifier for the archived item (e.g. tweet_id). |
| `source_platform` | string | yes | Platform the item was captured from. |
| `source_url` | string | yes | Original URL of the item. |
| `captured_at` | string | yes | ISO 8601 timestamp when the item was captured (datetime_utc from tweet.json). |
| `author_handle` | string | yes | Author handle without leading @. |
| `text_excerpt` | string | yes | Full or truncated text of the item. Truncated excerpts end with '...'. |
| `text_full` | string | no | Full untruncated text. Omitted if same as text_excerpt. |
| `media` | array | no | List of media assets attached to the item. |
| `ocr_text` | string | no | Full OCR text extracted from media, if available. |
| `article_md_path` | string | no | Relative path to the article markdown file within the bundle, if available. |
| `assets` | array | yes | List of all files included in the bundle output directory. |
| `citation_label` | string | no | Suggested citation label for the item (e.g. '@example_user, 2026-07-08'). |
| `trust_flags` | object | no | Flags indicating data quality and completeness. |
| `provenance` | object | yes | Provenance metadata about the capture and export process. |
| `related_items` | array | no | List of related item IDs (e.g. reply threads, quote tweets). |

## manifest.schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `manifest_version` | string | yes | Manifest schema version. |
| `item_id` | string | yes | Unique identifier for the archived item (e.g., tweet_id). |
| `source_platform` | string | yes | Platform the item was captured from. |
| `source_url` | string | yes | Original URL of the item. |
| `captured_at` | string | yes | ISO 8601 timestamp when the item was originally captured/archived (from tweet.json datetime_utc). |
| `generated_at` | string | yes | ISO 8601 timestamp when this manifest was generated. |
| `generator` | string | yes | Tool that generated this manifest. |
| `author_handle` | string | no | Author handle without @ prefix. |
| `citation_label` | string | no | Human-readable citation label. |
| `files` | array | yes | Complete inventory of all files in the item directory, with relative paths and SHA-256 hashes. |
| `transforms` | array | yes | Ordered list of transforms that have been applied to produce the files in this item directory. |
| `components` | array | no | Content components present in this item (e.g., text, images, video, audio, article, ocr). |
| `trust_flags` | object | no |  |
| `summary` | object | no |  |

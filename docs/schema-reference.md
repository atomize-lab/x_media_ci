# Schema Reference

This page provides a consolidated reference for all field schemas used in Citeseal.

---

## 1. tweet.json (v1)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tweet_id` | string | Yes | Unique identifier for the tweet |
| `tweet_url` | string | Yes | Full URL to the tweet |
| `author_handle` | string | Yes | Twitter/X handle of the author |
| `datetime_utc` | string | Yes | ISO 8601 timestamp in UTC |
| `datetime_local` | string | No | ISO 8601 timestamp in local timezone |
| `text` | string | No | Full text content of the tweet |
| `media` | array | No | List of media files attached to the tweet |
| `exports` | array | No | List of exported files (PDF, etc.) |
| `components` | array | No | Components used to render the tweet |
| `replies` | array | No | Replies to the tweet |

---

## 2. Agent Bundle (v1.0)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | Yes | Unique identifier for the agent |
| `agent_name` | string | Yes | Name of the agent |
| `version` | string | Yes | Version of the agent bundle |
| `created_at` | string | No | ISO 8601 timestamp of creation |
| `exports` | array | No | List of exported files |

---

## 3. Manifest (v1.0)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provenance` | object | Yes | Provenance information |
| `source` | string | Yes | Source of the data |
| `timestamp` | string | No | ISO 8601 timestamp |
| `signature` | string | No | Digital signature of the manifest |

---

## Quick Links

- [Agent Bundle Specification](./agent-bundle-spec.md)
- [Provenance Documentation](./provenance.md)
- [Validation Logic](../tools/scripts/tweet_schema.py)
# tweet.json field cheat sheet

| Field | Notes |
| --- | --- |
| `tweet_id` | string id |
| `tweet_url` | canonical status URL |
| `author_handle` | without leading @ preferred |
| `datetime` | ISO-8601 UTC |
| `text` | tweet body |
| `media` | **list** of objects with `file` paths |

Validation should emit a clear error (not crash) if `media` is not a list.

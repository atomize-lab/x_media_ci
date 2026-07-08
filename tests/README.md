# x_media_ci tests

Pytest test suite for the x_media CI tools.

## Running locally

```bash
# from project root
python3 -m pytest tests/ -v
```

No network access required. All fixtures are synthetic (1×1 pixel PNGs,
fake PDF headers) and contain no third-party media.

## What's covered

| File | Scope |
|---|---|
| `test_ci_common.py` | Path helpers, `TweetPaths`, `is_tweet_dir`, `find_tweet_dirs`, `safe_filename`, `env_flag` |
| `test_tweet_schema.py` | Schema validation: good/dirty/invalid fixtures, `write_tweet_json` round-trip |
| `test_tweet_fix.py` | `plan_fix` / `apply_fix`: handle stripping, media path resolution, dry-run vs apply |
| `test_cli_smoke.py` | CLI entry points (`tweet_validate.py`, `tweet_fix.py`, `x_media_ci.py --help`) exit cleanly |
| `test_indices.py` | JSONL index format: valid JSON, dedup key, handle/date partitioning |

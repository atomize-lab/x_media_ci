# Contributing to x_media_ci

Thanks for your interest in contributing! This document covers the basics.

## Quick Start

```bash
# 1. Fork & clone
git clone https://github.com/<your-fork>/x_media_ci.git
cd x_media_ci

# 2. Create a virtualenv and install deps
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r tools/requirements.txt
pip install -r requirements-dev.txt

# 3. Run the full test suite
python -m pytest tests/ -v

# 4. Lint
cd tools && python x_media_ci.py lint && cd ..
```

## Project Structure

```
x_media_ci/
├── tools/
│   ├── x_media_ci.py          # Unified CLI entry point
│   ├── scripts/                # Core Python modules
│   │   ├── ci_common.py        # Shared path/IO helpers
│   │   ├── tweet_schema.py     # tweet.json validation + write_tweet_json()
│   │   ├── tweet_validate.py   # CLI: validate tweet dirs
│   │   ├── tweet_fix.py        # CLI: fuzzy fix-up of tweet.json
│   │   └── ...
│   └── requirements.txt
├── tests/
│   ├── conftest.py             # Shared pytest fixtures
│   ├── fixtures/               # Synthetic test data (no real tweets)
│   ├── test_ci_common.py
│   ├── test_tweet_schema.py
│   ├── test_tweet_fix.py
│   ├── test_indices.py
│   └── test_cli_smoke.py
├── .github/workflows/ci.yml
└── pytest.ini
```

## Making Changes

### 1. Create a branch

```bash
git checkout -b fix/my-bugfix
```

### 2. Write tests first

We follow a test-first approach for bug fixes and new features:

- **Bug fix**: Write a failing test that reproduces the bug, then fix the code.
- **New feature**: Write tests for the expected behavior, then implement.

All test fixtures live under `tests/fixtures/` and are **fully synthetic** --
no real Twitter/X content, no third-party media. When adding a new fixture,
follow the existing directory structure:

```
tests/fixtures/accounts/<handle>/tweets/YYYY/YYYY-MM/<timestamp>_<tweet_id>/
    tweet.json
    media/images/...
    exports/...
```

### 3. Run tests + lint locally

```bash
# Lint
cd tools && python x_media_ci.py lint && cd ..

# Validate fixtures
python tools/scripts/tweet_validate.py --root tests/fixtures/accounts

# Full test suite
python -m pytest tests/ -v --tb=short
```

All three must pass before you push.

### 4. Commit and push

Use clear, conventional commit messages:

```
fix: strip @ prefix from author_handle in tweet_fix
test: add fixture round-trip tests for tweet_schema
docs: add CONTRIBUTING.md
feat: add --strict flag to tweet_validate
```

### 5. Open a Pull Request

- Reference any related issues in the PR description.
- CI will run automatically: pyflakes lint + fixture validation + pytest.
- All checks must be green before merge.

## Code Style

- Python 3.10+ (CI runs 3.12).
- Follow the existing style -- we use `pyflakes` for lint, not a heavy formatter.
- Keep functions focused; prefer small, testable units.
- Docstrings on public functions (triple-quote, first line is a summary).
- Type hints are welcome but not enforced everywhere.

## Testing Guidelines

| Test type | What it covers | Example file |
|-----------|---------------|--------------|
| Unit | Individual functions/classes | `test_ci_common.py`, `test_tweet_schema.py` |
| Fix-up logic | `tweet_fix.py` plan + apply | `test_tweet_fix.py` |
| Index integrity | JSONL format + partitioning | `test_indices.py` |
| CLI smoke | `--help`, exit codes, basic invocations | `test_cli_smoke.py` |

### Fixtures

- **Never commit real Twitter/X content.** All fixtures are synthetic.
- The `good` fixture (`20260708_180000_1234567890`) should always pass validation.
- The `dirty` fixture (`20260701_120000_9876543210`) has intentional issues for testing.
- The `invalid` fixture (`20260705_090000_5555555555`) is missing required fields.
- Tests that mutate fixtures must copy them to `tmp_path` first -- never mutate committed fixtures.

## Reporting Bugs

Open a [GitHub Issue](https://github.com/atomize-lab/x_media_ci/issues) with:

1. **What happened** (expected vs actual behavior)
2. **Steps to reproduce** (commands, input, or tweet URL)
3. **Environment** (OS, Python version, x_media_ci version)
4. **Logs** (run with `--verbose` or include stack traces)

## Suggesting Features

Open a GitHub Issue with the `enhancement` label. Describe the use case --
especially how it fits into an AI-agent content workflow.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).

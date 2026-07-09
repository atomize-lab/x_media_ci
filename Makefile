# X Media CI - Makefile
#
# Common development tasks. Run `make help` for a list of targets.
#
# Prerequisites:
#   - Python 3.10+ (uses .venv if present, falls back to python3)
#   - pyflakes installed in .venv or PATH (for `make lint`)
#   - Playwright browsers installed (for capture, not needed for tests)
#   - ffmpeg (for video transcoding, not needed for tests)

PYTHON := $(CURDIR)/.venv/bin/python
PYTHON_FALLBACK := python3
PYTEST := $(CURDIR)/.venv/bin/python -m pytest
FIXTURE_DIR := tests/fixtures/accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890
SERVER_SCRIPT := tools/server/run_server.sh
ARCHIVE_ROOT := $(CURDIR)/citeseal/accounts

# Use venv python if it exists, otherwise system python3
ifeq ($(wildcard .venv/bin/python),)
PYTHON := $(PYTHON_FALLBACK)
PYTEST := $(PYTHON_FALLBACK) -m pytest
endif

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: ## Create virtual environment and install dev dependencies
	$(PYTHON_FALLBACK) -m venv .venv
	$(PYTHON) -m pip install -r requirements-dev.txt
	@echo "Virtual environment created at .venv/"

.PHONY: test
test: ## Run the full test suite
	$(PYTEST) tests/ -v --tb=short

.PHONY: test-quiet
test-quiet: ## Run tests quietly (summary only)
	$(PYTEST) tests/ -q

.PHONY: lint
lint: ## Run pyflakes lint over bundled scripts
	cd tools && $(PYTHON) citeseal.py lint

.PHONY: validate-fixtures
validate-fixtures: ## Validate test fixtures
	$(PYTHON) tools/scripts/tweet_validate.py $(FIXTURE_DIR)

.PHONY: validate-archive
validate-archive: ## Validate the real archive (set ARCHIVE_ROOT)
	$(PYTHON) tools/scripts/tweet_validate.py $(ARCHIVE_ROOT)

.PHONY: ci
ci: lint validate-fixtures test-quiet ## Run the full CI pipeline locally (lint + validate + test)
	@echo ""
	@echo "=== CI PASSED ==="

.PHONY: serve
serve: ## Start the local API server
	@echo "Starting server on http://localhost:8765"
	@echo "Archive root: $(ARCHIVE_ROOT)"
	CITESEAL_ROOT="$(ARCHIVE_ROOT)" bash $(SERVER_SCRIPT)

.PHONY: smoke-cli
smoke-cli: ## Run a CLI smoke test (validate + lint, no network)
	@echo "=== Smoke test ==="
	@echo "--- lint ---"
	cd tools && $(PYTHON) citeseal.py lint
	@echo "--- validate fixture ---"
	$(PYTHON) tools/scripts/tweet_validate.py $(FIXTURE_DIR)
	@echo "--- pytest (subset) ---"
	$(PYTEST) tests/test_cli_smoke.py tests/test_tweet_schema.py -q
	@echo ""
	@echo "=== Smoke test PASSED ==="

.PHONY: doctor
doctor: ## Check environment and dependencies
	$(PYTHON) tools/citeseal.py doctor

.PHONY: clean
clean: ## Remove generated files (keeps .venv and source)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned __pycache__ and .pyc files"

.PHONY: clean-all
clean-all: clean ## Remove .venv as well
	rm -rf .venv
	@echo "Removed .venv/"

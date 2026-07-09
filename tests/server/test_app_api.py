"""Tests for the FastAPI server (tools/server/app.py).

Covers both the legacy endpoints and the v0.5 agent-access layer:
  - GET  /api/health
  - GET  /api/accounts
  - GET  /api/index/items            (v0.5)
  - GET  /api/item/{id}/context      (v0.5)
  - POST /api/export/agent_bundle    (v0.5)
  - POST /api/validate/item/{id}     (v0.5)
  - GET  /api/tweet/{id}             (legacy)
  - 404 handling for unknown items

The server reads from ``CITESEAL_ROOT``; tests point it at the
synthetic fixture tree under ``tests/fixtures/accounts``.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Make tools/scripts and tools/server importable.
ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / "tools" / "scripts"
SERVER_DIR = ROOT / "tools" / "server"
for _p in (str(SCRIPTS_DIR), str(SERVER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Point the server at the fixture accounts directory.
FIXTURES_ACCOUNTS = ROOT / "tests" / "fixtures" / "accounts"
os.environ["CITESEAL_ROOT"] = str(FIXTURES_ACCOUNTS)

from fastapi.testclient import TestClient  # noqa: E402

import app as server_app  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> TestClient:
    """A TestClient bound to the server app."""
    return TestClient(server_app.app)


GOOD_TWEET_ID = "1234567890"
DIRTY_TWEET_ID = "9876543210"
INVALID_TWEET_ID = "5555555555"


# ── Health & legacy endpoints ──────────────────────────────────────────────

class TestHealthAndLegacy:
    def test_health(self, client: TestClient):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "ci_root" in data

    def test_accounts(self, client: TestClient):
        r = client.get("/api/accounts")
        assert r.status_code == 200
        data = r.json()
        handles = [a["handle"] for a in data["accounts"]]
        assert "example_user" in handles

    def test_get_tweet_legacy(self, client: TestClient):
        r = client.get(f"/api/tweet/{GOOD_TWEET_ID}")
        assert r.status_code == 200
        data = r.json()
        assert data["tweet_id"] == GOOD_TWEET_ID

    def test_get_tweet_404(self, client: TestClient):
        r = client.get("/api/tweet/nonexistent999")
        assert r.status_code == 404


# ── v0.5: GET /api/index/items ──────────────────────────────────────────────

class TestIndexItems:
    def test_returns_all_fixture_items(self, client: TestClient):
        r = client.get("/api/index/items")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 3
        ids = {it["item_id"] for it in data["items"]}
        assert ids == {GOOD_TWEET_ID, DIRTY_TWEET_ID, INVALID_TWEET_ID}

    def test_items_have_trust_signals(self, client: TestClient):
        r = client.get("/api/index/items")
        data = r.json()
        for item in data["items"]:
            assert "has_media" in item
            assert "media_count" in item
            assert "has_ocr" in item
            assert "has_article" in item
            assert "validated" in item

    def test_filter_by_handle(self, client: TestClient):
        r = client.get("/api/index/items?handle=example_user")
        assert r.status_code == 200
        assert r.json()["count"] == 3

    def test_filter_by_nonexistent_handle(self, client: TestClient):
        r = client.get("/api/index/items?handle=nobody")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_limit_param(self, client: TestClient):
        r = client.get("/api/index/items?limit=1")
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_good_item_has_media(self, client: TestClient):
        r = client.get("/api/index/items")
        items = {it["item_id"]: it for it in r.json()["items"]}
        good = items[GOOD_TWEET_ID]
        assert good["has_media"] is True
        assert good["media_count"] == 2
        assert good["validated"] is True


# ── v0.5: GET /api/item/{item_id}/context ───────────────────────────────────

class TestItemContext:
    def test_good_item_context(self, client: TestClient):
        r = client.get(f"/api/item/{GOOD_TWEET_ID}/context")
        assert r.status_code == 200
        data = r.json()
        assert data["item_id"] == GOOD_TWEET_ID
        assert data["handle"] == "example_user"
        assert data["source_platform"] == "x"
        assert "text_excerpt" in data
        assert "trust_flags" in data
        assert data["trust_flags"]["has_media"] is True
        assert data["trust_flags"]["validated"] is True
        assert len(data["media"]) == 2
        # Each media entry should have a URL
        for m in data["media"]:
            assert "url" in m
            assert m["url"].startswith("/media/")

    def test_context_404(self, client: TestClient):
        r = client.get("/api/item/nonexistent999/context")
        assert r.status_code == 404

    def test_context_manifest_null_when_absent(self, client: TestClient):
        r = client.get(f"/api/item/{GOOD_TWEET_ID}/context")
        data = r.json()
        # The good fixture has no manifest.json
        assert data["manifest"] is None

    def test_context_text_full_for_short_tweets(self, client: TestClient):
        r = client.get(f"/api/item/{GOOD_TWEET_ID}/context")
        data = r.json()
        # The fixture text is short enough to not be truncated
        assert data["text_full"] is not None
        assert len(data["text_full"]) <= 280 or "..." not in data["text_excerpt"]

    def test_context_media_has_size(self, client: TestClient):
        r = client.get(f"/api/item/{GOOD_TWEET_ID}/context")
        data = r.json()
        for m in data["media"]:
            assert m["size"] > 0


# ── v0.5: POST /api/export/agent_bundle ─────────────────────────────────────

class TestExportAgentBundle:
    def test_export_single_item(self, client: TestClient):
        r = client.post(
            "/api/export/agent_bundle",
            json={"item_ids": [GOOD_TWEET_ID]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["exported"] == 1
        assert data["errors"] == 0
        result = data["results"][0]
        assert result["item_id"] == GOOD_TWEET_ID
        assert "bundle_json" in result
        assert result["file_count"] > 0
        # bundle_json should have required fields
        bj = result["bundle_json"]
        assert "bundle_version" in bj
        assert "assets" in bj
        assert "provenance" in bj

    def test_export_multiple_items(self, client: TestClient):
        r = client.post(
            "/api/export/agent_bundle",
            json={"item_ids": [GOOD_TWEET_ID, DIRTY_TWEET_ID]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["exported"] == 2
        assert data["errors"] == 0

    def test_export_with_hash_media(self, client: TestClient):
        r = client.post(
            "/api/export/agent_bundle",
            json={"item_ids": [GOOD_TWEET_ID], "hash_media": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["exported"] == 1
        bj = data["results"][0]["bundle_json"]
        # When hash_media=True, media entries should have sha256
        for m in bj.get("media", []):
            assert "sha256" in m

    def test_export_nonexistent_item(self, client: TestClient):
        r = client.post(
            "/api/export/agent_bundle",
            json={"item_ids": ["nonexistent999"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["exported"] == 0
        assert data["errors"] == 1
        assert "not found" in data["error_details"][0]["error"]

    def test_export_mixed_items(self, client: TestClient):
        """One valid + one invalid should export 1, error 1."""
        r = client.post(
            "/api/export/agent_bundle",
            json={"item_ids": [GOOD_TWEET_ID, "nonexistent999"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["exported"] == 1
        assert data["errors"] == 1

    def test_export_empty_list_rejected(self, client: TestClient):
        r = client.post(
            "/api/export/agent_bundle",
            json={"item_ids": []},
        )
        assert r.status_code == 400

    def test_export_too_many_items_rejected(self, client: TestClient):
        r = client.post(
            "/api/export/agent_bundle",
            json={"item_ids": [str(i) for i in range(51)]},
        )
        assert r.status_code == 400


# ── v0.5: POST /api/validate/item/{item_id} ─────────────────────────────────

class TestValidateItem:
    def test_validate_good_item(self, client: TestClient):
        r = client.post(f"/api/validate/item/{GOOD_TWEET_ID}")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["error_count"] == 0

    def test_validate_dirty_item(self, client: TestClient):
        r = client.post(f"/api/validate/item/{DIRTY_TWEET_ID}")
        assert r.status_code == 200
        data = r.json()
        # dirty fixture has at least one issue
        assert data["error_count"] + data["warning_count"] > 0

    def test_validate_404(self, client: TestClient):
        r = client.post("/api/validate/item/nonexistent999")
        assert r.status_code == 404

    def test_validate_returns_structured_errors(self, client: TestClient):
        """Error entries should have code, message, path fields."""
        r = client.post(f"/api/validate/item/{DIRTY_TWEET_ID}")
        data = r.json()
        for err_list_key in ("errors", "warnings"):
            for entry in data[err_list_key]:
                assert "code" in entry
                assert "message" in entry

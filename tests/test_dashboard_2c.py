"""Tests for dashboard.py 2C additions: saved searches, pinned topics, recent entity activity."""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import dashboard
from dashboard import (
    _load_saved_searches,
    _read_pinned_state,
    _recent_entity_activity,
    _save_saved_searches,
    _write_pinned_state,
    app,
)

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Saved Searches — helper tests
# ---------------------------------------------------------------------------

class SavedSearchHelpersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _path(self) -> Path:
        return self.root / "outputs" / "saved_searches.json"

    def test_load_returns_empty_list_when_no_file(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self._path()):
            result = _load_saved_searches()
        self.assertEqual(result, [])

    def test_save_and_load_roundtrip(self) -> None:
        entries = [{"id": "SS-001", "name": "Test", "query": "What is X?", "topic_scope": None, "created_at": "2026-01-01", "last_run_at": None}]
        with patch("dashboard.SAVED_SEARCHES_PATH", self._path()):
            _save_saved_searches(entries)
            loaded = _load_saved_searches()
        self.assertEqual(loaded, entries)

    def test_load_returns_empty_on_corrupt_json(self) -> None:
        self._path().parent.mkdir(parents=True, exist_ok=True)
        self._path().write_text("not-json", encoding="utf-8")
        with patch("dashboard.SAVED_SEARCHES_PATH", self._path()):
            result = _load_saved_searches()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Saved Searches — API endpoints
# ---------------------------------------------------------------------------

class SavedSearchEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ss_path = Path(self.tmp.name) / "outputs" / "saved_searches.json"
        self.ss_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_list_returns_empty(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self.ss_path):
            res = client.get("/api/saved-searches")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["searches"], [])

    def test_create_and_list(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self.ss_path):
            res = client.post(
                "/api/saved-searches",
                json={"name": "My search", "query": "What is LLM?", "topic_scope": None},
            )
            self.assertEqual(res.status_code, 201)
            entry = res.json()["search"]
            self.assertEqual(entry["name"], "My search")
            self.assertTrue(entry["id"].startswith("SS-"))

            res2 = client.get("/api/saved-searches")
            self.assertEqual(len(res2.json()["searches"]), 1)

    def test_create_requires_name(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self.ss_path):
            res = client.post("/api/saved-searches", json={"name": "", "query": "Q"})
        self.assertEqual(res.status_code, 400)

    def test_create_requires_query(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self.ss_path):
            res = client.post("/api/saved-searches", json={"name": "N", "query": ""})
        self.assertEqual(res.status_code, 400)

    def test_delete_removes_entry(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self.ss_path):
            res = client.post(
                "/api/saved-searches",
                json={"name": "To delete", "query": "Q"},
            )
            search_id = res.json()["search"]["id"]
            del_res = client.delete(f"/api/saved-searches/{search_id}")
            self.assertEqual(del_res.status_code, 200)
            list_res = client.get("/api/saved-searches")
            self.assertEqual(list_res.json()["searches"], [])

    def test_delete_nonexistent_returns_404(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self.ss_path):
            res = client.delete("/api/saved-searches/SS-NONEXISTENT")
        self.assertEqual(res.status_code, 404)

    def test_run_updates_last_run_at(self) -> None:
        with patch("dashboard.SAVED_SEARCHES_PATH", self.ss_path):
            create_res = client.post(
                "/api/saved-searches",
                json={"name": "Run me", "query": "Q"},
            )
            search_id = create_res.json()["search"]["id"]
            self.assertIsNone(create_res.json()["search"]["last_run_at"])

            run_res = client.post(f"/api/saved-searches/{search_id}/run")
            self.assertEqual(run_res.status_code, 200)
            self.assertIsNotNone(run_res.json()["search"]["last_run_at"])


# ---------------------------------------------------------------------------
# Pinned Topics — helper tests
# ---------------------------------------------------------------------------

class PinnedTopicHelpersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        topics_dir = self.root / "compiled" / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        self.topic_path = topics_dir / "my-topic.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_read_pinned_false_when_no_file(self) -> None:
        self.assertFalse(_read_pinned_state("nonexistent", self.root))

    def test_read_pinned_false_when_field_absent(self) -> None:
        self.topic_path.write_text('---\ntitle: "T"\n---\n\nBody.\n', encoding="utf-8")
        self.assertFalse(_read_pinned_state("my-topic", self.root))

    def test_write_and_read_pinned_true(self) -> None:
        self.topic_path.write_text('---\ntitle: "T"\n---\n\nBody.\n', encoding="utf-8")
        success = _write_pinned_state("my-topic", pinned=True, root=self.root)
        self.assertTrue(success)
        self.assertTrue(_read_pinned_state("my-topic", self.root))

    def test_write_and_read_pinned_false(self) -> None:
        self.topic_path.write_text('---\ntitle: "T"\npinned: true\n---\n\nBody.\n', encoding="utf-8")
        _write_pinned_state("my-topic", pinned=False, root=self.root)
        self.assertFalse(_read_pinned_state("my-topic", self.root))

    def test_write_updates_existing_pinned_field(self) -> None:
        self.topic_path.write_text('---\ntitle: "T"\npinned: false\n---\n\nBody.\n', encoding="utf-8")
        _write_pinned_state("my-topic", pinned=True, root=self.root)
        text = self.topic_path.read_text(encoding="utf-8")
        self.assertIn("pinned: true", text)
        # Ensure only one pinned field
        self.assertEqual(text.count("pinned:"), 1)

    def test_write_returns_false_for_missing_file(self) -> None:
        success = _write_pinned_state("ghost", pinned=True, root=self.root)
        self.assertFalse(success)


# ---------------------------------------------------------------------------
# Pinned Topics — API endpoints
# ---------------------------------------------------------------------------

class PinTopicEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        topics_dir = self.root / "compiled" / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "test-topic.md").write_text(
            '---\ntitle: "Test Topic"\n---\n\nBody.\n', encoding="utf-8"
        )
        registry = {"topics": [{"slug": "test-topic", "title": "Test Topic"}]}
        meta = self.root / "metadata"
        meta.mkdir(parents=True, exist_ok=True)
        (meta / "topic-registry.json").write_text(json.dumps(registry), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pin_topic(self) -> None:
        with patch("dashboard.ROOT", self.root):
            with patch("dashboard.TOPIC_REGISTRY_PATH", self.root / "metadata" / "topic-registry.json"):
                res = client.post("/api/topics/test-topic/pin")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "pinned")
        self.assertTrue(_read_pinned_state("test-topic", self.root))

    def test_unpin_topic(self) -> None:
        (self.root / "compiled" / "topics" / "test-topic.md").write_text(
            '---\ntitle: "Test Topic"\npinned: true\n---\n\nBody.\n', encoding="utf-8"
        )
        with patch("dashboard.ROOT", self.root):
            with patch("dashboard.TOPIC_REGISTRY_PATH", self.root / "metadata" / "topic-registry.json"):
                res = client.post("/api/topics/test-topic/unpin")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "unpinned")
        self.assertFalse(_read_pinned_state("test-topic", self.root))

    def test_pin_nonexistent_topic_returns_404(self) -> None:
        with patch("dashboard.ROOT", self.root):
            with patch("dashboard.TOPIC_REGISTRY_PATH", self.root / "metadata" / "topic-registry.json"):
                res = client.post("/api/topics/ghost-topic/pin")
        self.assertEqual(res.status_code, 404)


# ---------------------------------------------------------------------------
# Recent Entity Activity
# ---------------------------------------------------------------------------

class RecentEntityActivityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        ent_dir = self.root / "compiled" / "entities"
        ent_dir.mkdir(parents=True, exist_ok=True)
        arts_dir = self.root / "raw" / "articles"
        arts_dir.mkdir(parents=True, exist_ok=True)

        # Create two entity notes with dates
        (ent_dir / "anthropic.md").write_text(
            '---\ntitle: "Anthropic"\ndate_updated: "2026-04-22"\nsources:\n  - some-article-synthesis\napproved: true\n---\n\n# Anthropic\n',
            encoding="utf-8",
        )
        (ent_dir / "openai.md").write_text(
            '---\ntitle: "Openai"\ndate_updated: "2026-04-20"\nsources:\n  - another-article-synthesis\napproved: true\n---\n\n# OpenAI\n',
            encoding="utf-8",
        )

        # Create source articles with dates
        (arts_dir / "some-article.md").write_text(
            '---\ntitle: "Some"\ndate_ingested: "2026-04-22"\napproved: true\n---\n\nBody.\n',
            encoding="utf-8",
        )
        (arts_dir / "another-article.md").write_text(
            '---\ntitle: "Another"\ndate_ingested: "2026-04-20"\napproved: true\n---\n\nBody.\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_returns_entities_sorted_by_date_desc(self) -> None:
        results = _recent_entity_activity(self.root, limit=10)
        self.assertTrue(len(results) >= 1)
        dates = [r["last_seen_date"] for r in results]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_returns_at_most_limit(self) -> None:
        results = _recent_entity_activity(self.root, limit=1)
        self.assertLessEqual(len(results), 1)

    def test_result_has_required_fields(self) -> None:
        results = _recent_entity_activity(self.root, limit=10)
        for r in results:
            self.assertIn("slug", r)
            self.assertIn("name", r)
            self.assertIn("last_seen_date", r)
            self.assertIn("last_seen_in", r)

    def test_most_recent_entity_is_first(self) -> None:
        results = _recent_entity_activity(self.root, limit=10)
        slugs = [r["slug"] for r in results]
        if len(slugs) >= 2:
            self.assertEqual(slugs[0], "anthropic")

    def test_returns_empty_when_no_entities_dir(self) -> None:
        import shutil
        shutil.rmtree(self.root / "compiled" / "entities")
        results = _recent_entity_activity(self.root)
        self.assertEqual(results, [])

    def test_api_endpoint_returns_200(self) -> None:
        with patch("dashboard.ROOT", self.root):
            res = client.get("/api/entities/recent")
        self.assertEqual(res.status_code, 200)
        self.assertIn("entities", res.json())


if __name__ == "__main__":
    unittest.main()

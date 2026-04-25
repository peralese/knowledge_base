"""Tests for POST /api/share — 2C-1 mobile share endpoint."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dashboard
from dashboard import _url_is_duplicate, app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# _url_is_duplicate helper tests
# ---------------------------------------------------------------------------

class UrlIsDuplicateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_not_duplicate_when_empty(self) -> None:
        is_dup, existing = _url_is_duplicate("https://example.com/article", self.root)
        self.assertFalse(is_dup)
        self.assertEqual(existing, "")

    def test_detected_in_source_manifest(self) -> None:
        manifest = {
            "sources": [
                {
                    "source_id": "SRC-001",
                    "canonical_url": "https://example.com/article",
                }
            ]
        }
        meta = self.root / "metadata"
        meta.mkdir(parents=True)
        (meta / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        is_dup, existing = _url_is_duplicate("https://example.com/article", self.root)
        self.assertTrue(is_dup)
        self.assertEqual(existing, "SRC-001")

    def test_trailing_slash_normalized(self) -> None:
        manifest = {
            "sources": [
                {"source_id": "SRC-002", "canonical_url": "https://example.com/article/"}
            ]
        }
        meta = self.root / "metadata"
        meta.mkdir(parents=True)
        (meta / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        is_dup, _ = _url_is_duplicate("https://example.com/article", self.root)
        self.assertTrue(is_dup)

    def test_detected_in_inbox_feeds(self) -> None:
        feeds = self.root / "raw" / "inbox" / "feeds"
        feeds.mkdir(parents=True)
        (feeds / "my-article.json").write_text(
            json.dumps({"title": "T", "canonical_url": "https://example.com/feed-item", "content": ""}),
            encoding="utf-8",
        )
        is_dup, existing = _url_is_duplicate("https://example.com/feed-item", self.root)
        self.assertTrue(is_dup)
        self.assertEqual(existing, "my-article")

    def test_detected_in_inbox_browser(self) -> None:
        browser = self.root / "raw" / "inbox" / "browser"
        browser.mkdir(parents=True)
        (browser / "some-article.md").write_text(
            '---\ntitle: "T"\ncanonical_url: "https://example.com/browser-item"\n---\n\nBody.\n',
            encoding="utf-8",
        )
        is_dup, existing = _url_is_duplicate("https://example.com/browser-item", self.root)
        self.assertTrue(is_dup)

    def test_different_url_not_duplicate(self) -> None:
        manifest = {
            "sources": [{"source_id": "SRC-003", "canonical_url": "https://other.com/thing"}]
        }
        meta = self.root / "metadata"
        meta.mkdir(parents=True)
        (meta / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        is_dup, _ = _url_is_duplicate("https://example.com/different", self.root)
        self.assertFalse(is_dup)


# ---------------------------------------------------------------------------
# /api/share endpoint tests
# ---------------------------------------------------------------------------

class ShareEndpointTests(unittest.TestCase):
    def test_missing_url_returns_400(self) -> None:
        res = client.post("/api/share", json={"url": ""})
        self.assertEqual(res.status_code, 400)

    def test_non_http_url_returns_400(self) -> None:
        res = client.post("/api/share", json={"url": "ftp://example.com/file"})
        self.assertEqual(res.status_code, 400)

    def test_duplicate_returns_409(self) -> None:
        with patch("dashboard._url_is_duplicate", return_value=(True, "SRC-EXISTING")):
            res = client.post("/api/share", json={"url": "https://example.com/article"})
        self.assertEqual(res.status_code, 409)
        body = res.json()
        self.assertEqual(body["status"], "duplicate")
        self.assertEqual(body["existing_id"], "SRC-EXISTING")

    def test_unreachable_url_returns_502(self) -> None:
        import httpx
        with patch("dashboard._url_is_duplicate", return_value=(False, "")):
            with patch("httpx.get", side_effect=httpx.ConnectError("no route")):
                res = client.post("/api/share", json={"url": "https://unreachable.example.com/"})
        self.assertEqual(res.status_code, 502)

    def test_successful_share_queues_and_returns_inbox_id(self) -> None:
        """Test the full share flow by writing to a real temp inbox directory."""
        import tempfile
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = '<html><title>Test Article</title></html>'

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feeds_dir = root / "raw" / "inbox" / "feeds"
            feeds_dir.mkdir(parents=True)

            with patch("dashboard._url_is_duplicate", return_value=(False, "")):
                with patch("httpx.get", return_value=mock_response):
                    with patch("dashboard.ROOT", root):
                        import stage_to_inbox as sti
                        with patch.object(sti, "stage_feed", return_value=feeds_dir / "test-article.json") as mock_sf:
                            res = client.post(
                                "/api/share",
                                json={"url": "https://example.com/new-article", "note": "interesting read"},
                            )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "queued")
        self.assertTrue(body["inbox_id"].startswith("INX-"))

    def test_share_with_note_queues_successfully(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = '<html><head><title>My Article</title></head><body>Content</body></html>'

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feeds_dir = root / "raw" / "inbox" / "feeds"
            feeds_dir.mkdir(parents=True)

            with patch("dashboard._url_is_duplicate", return_value=(False, "")):
                with patch("httpx.get", return_value=mock_response):
                    with patch("dashboard.ROOT", root):
                        import stage_to_inbox as sti
                        with patch.object(sti, "stage_feed", return_value=feeds_dir / "my-article.json"):
                            res = client.post(
                                "/api/share",
                                json={"url": "https://example.com/test", "note": "my annotation"},
                            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "queued")

    def test_share_writes_json_file_with_correct_content(self) -> None:
        """stage_feed actually writes a .json file; verify path and content."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = '<html><head><title>CLI Tools Hidden Gems</title></head><body>Body.</body></html>'
        url = "https://simonwillison.net/2024/Jun/17/cli-tools-hidden-gems/"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feeds_dir = root / "raw" / "inbox" / "feeds"
            feeds_dir.mkdir(parents=True)

            with patch("dashboard._url_is_duplicate", return_value=(False, "")):
                with patch("httpx.get", return_value=mock_response):
                    with patch("dashboard.ROOT", root):
                        res = client.post("/api/share", json={"url": url, "note": "test note"})

            self.assertEqual(res.status_code, 200)
            body = res.json()
            self.assertEqual(body["status"], "queued")
            self.assertIn("inbox_id", body)
            self.assertIn("file", body)

            written = Path(body["file"])
            self.assertTrue(written.exists(), f"Expected file at {written}")

            payload = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "CLI Tools Hidden Gems")
            self.assertEqual(payload["canonical_url"], url)
            self.assertIn("test note", payload["content"])


if __name__ == "__main__":
    unittest.main()

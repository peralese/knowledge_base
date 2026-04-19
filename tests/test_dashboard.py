"""Tests for dashboard.py — ingestion metadata expansion (Phase 11)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# dashboard.py lives at the project root, not inside scripts/
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard import _inject_optional_frontmatter, _parse_tags


# ---------------------------------------------------------------------------
# _parse_tags
# ---------------------------------------------------------------------------

class ParseTagsTests(unittest.TestCase):
    def test_splits_comma_separated(self) -> None:
        self.assertEqual(_parse_tags("security, hardening, 2026"), ["security", "hardening", "2026"])

    def test_strips_whitespace(self) -> None:
        self.assertEqual(_parse_tags("  a ,  b  "), ["a", "b"])

    def test_blank_returns_empty(self) -> None:
        self.assertEqual(_parse_tags(""), [])
        self.assertEqual(_parse_tags("   "), [])

    def test_filters_empty_segments(self) -> None:
        self.assertEqual(_parse_tags("a,,b"), ["a", "b"])


# ---------------------------------------------------------------------------
# _inject_optional_frontmatter
# ---------------------------------------------------------------------------

class InjectOptionalFrontmatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_file(self, content: str) -> Path:
        p = self.root / "note.md"
        p.write_text(content, encoding="utf-8")
        return p

    def test_injects_source_type(self) -> None:
        path = self._make_file('---\ntitle: "T"\n---\n\nBody.\n')
        _inject_optional_frontmatter(path, {"source_type": "blog"})
        self.assertIn('source_type: "blog"', path.read_text(encoding="utf-8"))

    def test_injects_author(self) -> None:
        path = self._make_file('---\ntitle: "T"\n---\n\nBody.\n')
        _inject_optional_frontmatter(path, {"author": "Jane Smith"})
        self.assertIn('author: "Jane Smith"', path.read_text(encoding="utf-8"))

    def test_injects_tags_as_inline_list(self) -> None:
        path = self._make_file('---\ntitle: "T"\n---\n\nBody.\n')
        _inject_optional_frontmatter(path, {"tags": ["security", "hardening"]})
        text = path.read_text(encoding="utf-8")
        self.assertIn('tags: ["security", "hardening"]', text)

    def test_skips_none_values(self) -> None:
        path = self._make_file('---\ntitle: "T"\n---\n\nBody.\n')
        _inject_optional_frontmatter(path, {"author": None, "language": None})
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("author:", text)
        self.assertNotIn("language:", text)

    def test_skips_empty_string(self) -> None:
        path = self._make_file('---\ntitle: "T"\n---\n\nBody.\n')
        _inject_optional_frontmatter(path, {"author": "", "language": "  "})
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("author:", text)
        self.assertNotIn("language:", text)

    def test_skips_empty_list(self) -> None:
        path = self._make_file('---\ntitle: "T"\n---\n\nBody.\n')
        _inject_optional_frontmatter(path, {"tags": []})
        self.assertNotIn("tags:", path.read_text(encoding="utf-8"))

    def test_body_preserved_after_injection(self) -> None:
        path = self._make_file('---\ntitle: "T"\n---\n\nKeep this body.\n')
        _inject_optional_frontmatter(path, {"source_type": "article"})
        self.assertIn("Keep this body.", path.read_text(encoding="utf-8"))

    def test_no_fields_leaves_file_unchanged(self) -> None:
        original = '---\ntitle: "T"\n---\n\nBody.\n'
        path = self._make_file(original)
        _inject_optional_frontmatter(path, {"author": None, "tags": []})
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_missing_file_handled_gracefully(self) -> None:
        missing = self.root / "nonexistent.md"
        _inject_optional_frontmatter(missing, {"source_type": "blog"})  # no raise

    def test_file_without_frontmatter_left_unchanged(self) -> None:
        original = "No frontmatter here.\n"
        path = self._make_file(original)
        _inject_optional_frontmatter(path, {"source_type": "blog"})
        self.assertEqual(path.read_text(encoding="utf-8"), original)


# ---------------------------------------------------------------------------
# POST /api/ingest/url — optional fields written to frontmatter
# ---------------------------------------------------------------------------

class IngestURLMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "raw" / "inbox" / "browser").mkdir(parents=True)
        (self.root / "tmp").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _staged_file(self) -> Path:
        """Return the first .md file in the browser inbox."""
        files = list((self.root / "raw" / "inbox" / "browser").glob("*.md"))
        self.assertTrue(files, "No staged file found")
        return files[0]

    def _run_ingest_url(self, payload: dict) -> dict:
        """Call the ingest_url logic directly, bypassing HTTP."""
        from dashboard import IngestURLRequest, ingest_url, ROOT as DASH_ROOT
        import dashboard

        original_root = dashboard.ROOT
        original_tmp = dashboard.TMP_DIR
        dashboard.ROOT = self.root
        dashboard.TMP_DIR = self.root / "tmp"

        try:
            with patch("dashboard.httpx.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.text = "<html><body>Article content here.</body></html>"
                mock_resp.headers = {"content-type": "text/html"}
                mock_resp.raise_for_status = MagicMock()
                mock_get.return_value = mock_resp

                body = IngestURLRequest(**payload)
                result = ingest_url(body)
        finally:
            dashboard.ROOT = original_root
            dashboard.TMP_DIR = original_tmp

        return result

    def test_all_optional_fields_written_to_frontmatter(self) -> None:
        self._run_ingest_url({
            "url": "https://example.com/article",
            "topic_slug": "test-topic",
            "source_type": "blog",
            "author": "Jane Smith",
            "date_published": "2026-03-15",
            "tags": ["security", "hardening"],
            "language": "en",
            "license": "CC BY 4.0",
        })
        text = self._staged_file().read_text(encoding="utf-8")
        self.assertIn('source_type: "blog"', text)
        self.assertIn('author: "Jane Smith"', text)
        self.assertIn('date_published: "2026-03-15"', text)
        self.assertIn('"security"', text)
        self.assertIn('"hardening"', text)
        self.assertIn('language: "en"', text)
        self.assertIn('license: "CC BY 4.0"', text)

    def test_no_optional_fields_writes_only_source_type(self) -> None:
        self._run_ingest_url({
            "url": "https://example.com/article",
            "topic_slug": "test-topic",
        })
        text = self._staged_file().read_text(encoding="utf-8")
        # source_type always written
        self.assertIn("source_type:", text)
        # optional fields absent
        self.assertNotIn("author:", text)
        self.assertNotIn("date_published:", text)
        self.assertNotIn("language:", text)
        self.assertNotIn("license:", text)

    def test_tags_written_as_yaml_list(self) -> None:
        self._run_ingest_url({
            "url": "https://example.com/article",
            "topic_slug": "test-topic",
            "tags": ["a", "b", "c"],
        })
        text = self._staged_file().read_text(encoding="utf-8")
        self.assertIn('tags: ["a", "b", "c"]', text)

    def test_blank_language_not_written(self) -> None:
        self._run_ingest_url({
            "url": "https://example.com/article",
            "topic_slug": "test-topic",
            "language": "",
        })
        text = self._staged_file().read_text(encoding="utf-8")
        self.assertNotIn("language:", text)


if __name__ == "__main__":
    unittest.main()

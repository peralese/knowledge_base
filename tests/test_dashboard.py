"""Tests for dashboard.py — ingestion metadata expansion (Phase 11)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# dashboard.py lives at the project root, not inside scripts/
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dashboard
from dashboard import (
    _extract_page_title,
    _extract_frontmatter_tags,
    _inject_optional_frontmatter,
    _parse_tags,
    app,
    slugify,
)


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


class ExtractFrontmatterTagsTests(unittest.TestCase):
    def test_multiline_tags(self) -> None:
        text = '---\ntitle: "T"\ntags:\n  - "ai"\n  - research\n---\n\nBody.'
        self.assertEqual(_extract_frontmatter_tags(text), ["ai", "research"])

    def test_inline_tags(self) -> None:
        text = '---\ntitle: "T"\ntags: ["ai", "research"]\n---\n\nBody.'
        self.assertEqual(_extract_frontmatter_tags(text), ["ai", "research"])

    def test_empty_tags_ignored(self) -> None:
        text = '---\ntitle: "T"\ntags: []\n---\n\nBody.'
        self.assertEqual(_extract_frontmatter_tags(text), [])


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
        (self.root / "raw" / "articles").mkdir(parents=True)
        (self.root / "tmp").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _staged_file(self) -> Path:
        """Return the first raw article markdown file."""
        files = list((self.root / "raw" / "articles").glob("*.md"))
        self.assertTrue(files, "No raw article found")
        return files[0]

    def _run_ingest_url(self, payload: dict) -> dict:
        """Call the ingest_url logic directly, bypassing HTTP."""
        from dashboard import IngestURLRequest, ingest_url, ROOT as DASH_ROOT
        import dashboard

        original_root = dashboard.ROOT
        original_tmp = dashboard.TMP_DIR
        original_articles = dashboard.ARTICLES_DIR
        dashboard.ROOT = self.root
        dashboard.TMP_DIR = self.root / "tmp"
        dashboard.ARTICLES_DIR = self.root / "raw" / "articles"

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
            dashboard.ARTICLES_DIR = original_articles

        return result

    def test_all_optional_fields_written_to_frontmatter(self) -> None:
        self._run_ingest_url({
            "url": "https://example.com/article",
            "title": "Test Article",
            "topic_slug": "test-topic",
            "source_type": "blog",
            "author": "Jane Smith",
            "date_published": "2026-03-15",
            "tags": ["security", "hardening"],
            "language": "en",
            "license": "CC BY 4.0",
        })
        text = self._staged_file().read_text(encoding="utf-8")
        self.assertIn("source_type: blog", text)
        self.assertIn("author: Jane Smith", text)
        self.assertIn("date_published: 2026-03-15", text)
        self.assertIn("- security", text)
        self.assertIn("- hardening", text)
        self.assertIn("language: en", text)
        self.assertIn("license: CC BY 4.0", text)

    def test_no_optional_fields_writes_only_source_type(self) -> None:
        self._run_ingest_url({
            "url": "https://example.com/article",
            "title": "Test Article",
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
            "title": "Test Article",
            "topic_slug": "test-topic",
            "tags": ["a", "b", "c"],
        })
        text = self._staged_file().read_text(encoding="utf-8")
        self.assertIn("tags:\n  - a\n  - b\n  - c", text)

    def test_blank_language_not_written(self) -> None:
        self._run_ingest_url({
            "url": "https://example.com/article",
            "title": "Test Article",
            "topic_slug": "test-topic",
            "language": "",
        })
        text = self._staged_file().read_text(encoding="utf-8")
        self.assertNotIn("language:", text)


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

class SlugifyTests(unittest.TestCase):
    def test_basic_lowercase(self) -> None:
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_colon_becomes_hyphen(self) -> None:
        self.assertEqual(slugify("Title: Subtitle"), "title-subtitle")

    def test_apostrophe(self) -> None:
        self.assertEqual(slugify("Don't Stop"), "don-t-stop")

    def test_mixed_case(self) -> None:
        self.assertEqual(slugify("UPPER lower"), "upper-lower")

    def test_consecutive_spaces_collapse(self) -> None:
        self.assertEqual(slugify("a  b"), "a-b")

    def test_leading_trailing_stripped(self) -> None:
        self.assertEqual(slugify("  hello  "), "hello")

    def test_special_chars(self) -> None:
        self.assertEqual(slugify("OpenClaw: Best Practices for 2026!"), "openclaw-best-practices-for-2026")

    def test_stable_idempotent(self) -> None:
        title = "How to Harden OpenClaw: Security Best Practices"
        self.assertEqual(slugify(title), slugify(title))


# ---------------------------------------------------------------------------
# _extract_page_title
# ---------------------------------------------------------------------------

class ExtractPageTitleTests(unittest.TestCase):
    def test_og_title_preferred(self) -> None:
        html = '<html><head><meta property="og:title" content="OG Title"/><title>Page</title></head></html>'
        self.assertEqual(_extract_page_title(html), "OG Title")

    def test_twitter_title_fallback(self) -> None:
        html = '<html><head><meta name="twitter:title" content="TW Title"/><title>Page</title></head></html>'
        self.assertEqual(_extract_page_title(html), "TW Title")

    def test_title_tag_fallback(self) -> None:
        html = "<html><head><title>Plain Title</title></head></html>"
        self.assertEqual(_extract_page_title(html), "Plain Title")

    def test_strips_pipe_suffix(self) -> None:
        html = "<html><head><title>My Article | Example Site</title></head></html>"
        self.assertEqual(_extract_page_title(html), "My Article")

    def test_strips_dash_suffix(self) -> None:
        html = "<html><head><title>My Article - Example Site</title></head></html>"
        self.assertEqual(_extract_page_title(html), "My Article")

    def test_strips_em_dash_suffix(self) -> None:
        html = "<html><head><title>My Article \u2014 Example Site</title></head></html>"
        self.assertEqual(_extract_page_title(html), "My Article")

    def test_strips_middle_dot_suffix(self) -> None:
        html = "<html><head><title>My Article \u00b7 Example Site</title></head></html>"
        self.assertEqual(_extract_page_title(html), "My Article")

    def test_no_title_returns_none(self) -> None:
        html = "<html><head></head><body>No title here</body></html>"
        self.assertIsNone(_extract_page_title(html))

    def test_does_not_strip_mid_title_separator(self) -> None:
        # Only the LAST occurrence of a separator pattern is stripped
        html = "<html><head><title>A - B - Site Name</title></head></html>"
        self.assertEqual(_extract_page_title(html), "A - B")


# ---------------------------------------------------------------------------
# GET /api/fetch-title
# ---------------------------------------------------------------------------

class FetchTitleEndpointTests(unittest.TestCase):
    def _call(self, html: str, *, raise_exc: Exception | None = None) -> dict:
        from dashboard import fetch_title
        with patch("dashboard.httpx.get") as mock_get:
            if raise_exc is not None:
                mock_get.side_effect = raise_exc
            else:
                mock_resp = MagicMock()
                mock_resp.text = html
                mock_resp.raise_for_status = MagicMock()
                mock_get.return_value = mock_resp
            return fetch_title(url="https://example.com/article")

    def test_returns_og_title(self) -> None:
        html = '<html><head><meta property="og:title" content="OG Title"/></head></html>'
        result = self._call(html)
        self.assertEqual(result["title"], "OG Title")

    def test_returns_title_tag_content(self) -> None:
        html = "<html><head><title>Plain Title</title></head></html>"
        result = self._call(html)
        self.assertEqual(result["title"], "Plain Title")

    def test_strips_site_suffix(self) -> None:
        html = "<html><head><title>Article Title | Site Name</title></head></html>"
        result = self._call(html)
        self.assertEqual(result["title"], "Article Title")

    def test_unreachable_url_returns_null(self) -> None:
        result = self._call("", raise_exc=Exception("timeout"))
        self.assertIsNone(result["title"])

    def test_http_error_returns_null(self) -> None:
        result = self._call("", raise_exc=Exception("404"))
        self.assertIsNone(result["title"])


# ---------------------------------------------------------------------------
# POST /api/ingest/url — title field
# ---------------------------------------------------------------------------

class IngestURLTitleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "raw" / "articles").mkdir(parents=True)
        (self.root / "tmp").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, payload: dict) -> dict:
        from dashboard import IngestURLRequest, ingest_url
        import dashboard
        orig_root, orig_tmp = dashboard.ROOT, dashboard.TMP_DIR
        orig_articles = dashboard.ARTICLES_DIR
        dashboard.ROOT = self.root
        dashboard.TMP_DIR = self.root / "tmp"
        dashboard.ARTICLES_DIR = self.root / "raw" / "articles"
        try:
            with patch("dashboard.httpx.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.text = "<html><body>Content.</body></html>"
                mock_resp.headers = {"content-type": "text/html"}
                mock_resp.raise_for_status = MagicMock()
                mock_get.return_value = mock_resp
                body = IngestURLRequest(**payload)
                return ingest_url(body)
        finally:
            dashboard.ROOT = orig_root
            dashboard.TMP_DIR = orig_tmp
            dashboard.ARTICLES_DIR = orig_articles

    def _staged(self) -> Path:
        files = list((self.root / "raw" / "articles").glob("*.md"))
        self.assertTrue(files, "No raw article found")
        return files[0]

    def test_title_in_frontmatter(self) -> None:
        self._run({"url": "https://example.com/article", "title": "My Custom Title"})
        text = self._staged().read_text(encoding="utf-8")
        self.assertIn("My Custom Title", text)

    def test_slug_from_title_drives_filename(self) -> None:
        self._run({"url": "https://example.com/article", "title": "How to Harden OpenClaw"})
        name = self._staged().name
        self.assertIn("how-to-harden-openclaw", name)

    def test_missing_title_raises_400(self) -> None:
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._run({"url": "https://example.com/article", "title": ""})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_blank_title_raises_400(self) -> None:
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._run({"url": "https://example.com/article", "title": "   "})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_conflicting_title_returns_409(self) -> None:
        from fastapi import HTTPException
        # Pre-create an article with the same slug
        articles = self.root / "raw" / "articles"
        articles.mkdir(parents=True, exist_ok=True)
        (articles / "what-is-ollama.md").write_text("existing", encoding="utf-8")

        with self.assertRaises(HTTPException) as ctx:
            self._run({"url": "https://example.com/article", "title": "What is Ollama"})
        self.assertEqual(ctx.exception.status_code, 409)
        article_files = list((self.root / "raw" / "articles").glob("*.md"))
        self.assertEqual(len(article_files), 1)

    def test_url_slug_from_title_not_url_path(self) -> None:
        """Staged filename must come from the title, not the URL slug."""
        self._run({"url": "https://example.com/technology", "title": "How to Harden OpenClaw"})
        name = self._staged().name
        self.assertIn("how-to-harden-openclaw", name)
        self.assertNotIn("technology", name)


# ---------------------------------------------------------------------------
# POST /api/ingest/file — title drives filename + conflict detection
# ---------------------------------------------------------------------------

class IngestFileTitleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "raw" / "articles").mkdir(parents=True)
        (self.root / "tmp").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, title: str, filename: str = "upload.md", content: str = "body") -> dict:
        from dashboard import ingest_file
        import dashboard
        orig_root, orig_tmp = dashboard.ROOT, dashboard.TMP_DIR
        orig_articles = dashboard.ARTICLES_DIR
        dashboard.ROOT = self.root
        dashboard.TMP_DIR = self.root / "tmp"
        dashboard.ARTICLES_DIR = self.root / "raw" / "articles"
        try:
            upload = MagicMock()
            upload.filename = filename
            upload.file = MagicMock()
            upload.file.read = MagicMock(return_value=content.encode("utf-8"))
            return ingest_file(
                file=upload,
                title=title,
                topic_slug="test-topic",
                notes="",
                source_type="article",
                author="",
                canonical_url="",
                date_published="",
                tags="",
                language="",
                license="",
            )
        finally:
            dashboard.ROOT = orig_root
            dashboard.TMP_DIR = orig_tmp
            dashboard.ARTICLES_DIR = orig_articles

    def _staged(self) -> Path:
        files = list((self.root / "raw" / "articles").glob("*"))
        self.assertTrue(files, "No raw article found")
        return files[0]

    def test_slug_from_title_not_original_filename(self) -> None:
        self._run(title="What is Ollama", filename="something-unrelated.md")
        name = self._staged().name
        # Filename must be derived from the title slug, not the uploaded filename
        self.assertIn("what-is-ollama", name)
        self.assertNotIn("something-unrelated", name)

    def test_conflicting_title_returns_409(self) -> None:
        from fastapi import HTTPException
        articles = self.root / "raw" / "articles"
        articles.mkdir(parents=True, exist_ok=True)
        (articles / "what-is-ollama.md").write_text("existing", encoding="utf-8")

        with self.assertRaises(HTTPException) as ctx:
            self._run(title="What is Ollama", filename="any.md")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_no_suffix_appended_on_conflict(self) -> None:
        from fastapi import HTTPException
        articles = self.root / "raw" / "articles"
        articles.mkdir(parents=True, exist_ok=True)
        (articles / "what-is-ollama.md").write_text("existing", encoding="utf-8")

        with self.assertRaises(HTTPException) as ctx:
            self._run(title="What is Ollama", filename="any.md")
        # No sitemap-2 style files should appear
        article_files = list((self.root / "raw" / "articles").glob("*"))
        self.assertEqual(len(article_files), 1)


# ---------------------------------------------------------------------------
# POST /api/ingest/* — HTTP endpoints write directly to raw/articles
# ---------------------------------------------------------------------------

class IngestEndpointRawArticleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.articles_dir = self.root / "raw" / "articles"
        self.articles_dir.mkdir(parents=True)
        self.original_root = dashboard.ROOT
        self.original_articles = dashboard.ARTICLES_DIR
        dashboard.ROOT = self.root
        dashboard.ARTICLES_DIR = self.articles_dir
        self.client = TestClient(app)

    def tearDown(self) -> None:
        dashboard.ROOT = self.original_root
        dashboard.ARTICLES_DIR = self.original_articles
        self.tmp.cleanup()

    def test_file_ingest_uses_title_for_filename(self) -> None:
        response = self.client.post("/api/ingest/file", data={
            "title": "My Test Article About Ollama",
            "topic_slug": "test-topic",
        }, files={
            "file": ("some_random_filename.html", b"<html><body>content</body></html>", "text/html")
        })
        self.assertEqual(response.status_code, 200)

        expected_path = self.articles_dir / "my-test-article-about-ollama.md"
        self.assertTrue(expected_path.exists())

        wrong_path = self.articles_dir / "some_random_filename.md"
        self.assertFalse(wrong_path.exists())

    def test_url_ingest_uses_title_for_filename(self) -> None:
        with patch("dashboard.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = "<html><body>content</body></html>"
            mock_resp.headers = {"content-type": "text/html"}
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            response = self.client.post("/api/ingest/url", json={
                "url": "https://example.com/some/path/that/should/be/ignored",
                "title": "My Test Article About Local AI",
                "topic_slug": "test-topic",
            })

        self.assertEqual(response.status_code, 200)
        expected_path = self.articles_dir / "my-test-article-about-local-ai.md"
        self.assertTrue(expected_path.exists())

    def test_file_ingest_writes_optional_metadata(self) -> None:
        response = self.client.post("/api/ingest/file", data={
            "title": "Metadata Test Article",
            "topic_slug": "test-topic",
            "author": "Jane Smith",
            "canonical_url": "https://example.com/original",
            "date_published": "2026-01-15",
            "tags": "ai, research",
            "language": "en",
        }, files={
            "file": ("test.html", b"<html><body>content</body></html>", "text/html")
        })
        self.assertEqual(response.status_code, 200)

        article_path = self.articles_dir / "metadata-test-article.md"
        content = article_path.read_text(encoding="utf-8")
        self.assertIn("author: Jane Smith", content)
        self.assertIn('canonical_url: "https://example.com/original"', content)
        self.assertIn("date_published: 2026-01-15", content)
        self.assertIn("- ai", content)
        self.assertIn("language: en", content)

        manifest = json.loads((self.root / "metadata" / "source-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["sources"][0]["canonical_url"], "https://example.com/original")

    def test_file_ingest_omits_empty_optional_fields(self) -> None:
        response = self.client.post("/api/ingest/file", data={
            "title": "No Metadata Article",
            "topic_slug": "test-topic",
        }, files={
            "file": ("test.html", b"<html><body>content</body></html>", "text/html")
        })
        self.assertEqual(response.status_code, 200)

        article_path = self.articles_dir / "no-metadata-article.md"
        content = article_path.read_text(encoding="utf-8")
        self.assertNotIn("author", content)
        self.assertNotIn("date_published", content)
        self.assertNotIn("tags", content)


class TagsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for relative in [
            "raw/articles",
            "compiled/source_summaries",
            "compiled/topics",
            "metadata/prompts",
        ]:
            (self.root / relative).mkdir(parents=True)
        self.original_root = dashboard.ROOT
        dashboard.ROOT = self.root
        self.client = TestClient(app)

    def tearDown(self) -> None:
        dashboard.ROOT = self.original_root
        self.tmp.cleanup()

    def test_returns_sorted_unique_used_tags(self) -> None:
        (self.root / "raw" / "articles" / "one.md").write_text(
            '---\ntags:\n  - "ollama"\n  - local-ai\n---\n\nBody.',
            encoding="utf-8",
        )
        (self.root / "compiled" / "topics" / "two.md").write_text(
            '---\ntags: ["topic", "ollama"]\n---\n\nBody.',
            encoding="utf-8",
        )
        (self.root / "metadata" / "prompts" / "ignored.md").write_text(
            '---\ntags: ["prompt-only"]\n---\n\nBody.',
            encoding="utf-8",
        )

        response = self.client.get("/api/tags")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tags"], ["local-ai", "ollama", "topic"])


# ---------------------------------------------------------------------------
# Phase 12 query and re-synthesis endpoints
# ---------------------------------------------------------------------------

class QueryEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.client = TestClient(app)
        (self.root / "outputs" / "answers").mkdir(parents=True)
        (self.root / "compiled" / "topics").mkdir(parents=True)
        (self.root / "compiled" / "source_summaries").mkdir(parents=True)
        (self.root / "compiled" / "topics" / "openclaw-security.md").write_text(
            "---\ntitle: OpenClaw Security\ncompiled_from:\n  - hardening-openclaw-synthesis\n---\n\nTopic body [[hardening-openclaw-synthesis]].",
            encoding="utf-8",
        )
        (self.root / "compiled" / "source_summaries" / "hardening-openclaw-synthesis.md").write_text(
            "---\ntitle: Hardening\napproved: true\n---\n\nSummary body.",
            encoding="utf-8",
        )
        (self.root / "compiled" / "index.md").write_text("- [[openclaw-security]] — OpenClaw\n", encoding="utf-8")
        self.original_root = dashboard.ROOT
        dashboard.ROOT = self.root

    def tearDown(self) -> None:
        dashboard.ROOT = self.original_root
        self.tmp.cleanup()

    def test_post_query_with_topic_saves_answer(self) -> None:
        with patch("dashboard.call_query_ollama", return_value="Use [[hardening-openclaw-synthesis]]."):
            res = self.client.post(
                "/api/query",
                json={"question": "What are risks?", "topic_slug": "openclaw-security"},
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("hardening-openclaw-synthesis", data["sources"])
        self.assertTrue((self.root / data["saved_path"]).exists())

    def test_post_query_without_topic_uses_full_wiki(self) -> None:
        captured: list[str] = []

        def fake_call(prompt: str, model: str, timeout: int) -> str:
            captured.append(prompt)
            return "OpenClaw Security"

        with patch("dashboard.call_query_ollama", side_effect=fake_call):
            res = self.client.post("/api/query", json={"question": "What is known?"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any("Topic body" in p for p in captured))
        self.assertFalse(any("Summary body" in p for p in captured))

    def test_post_query_ollama_unavailable_returns_specific_error(self) -> None:
        with patch("dashboard.call_query_ollama", side_effect=OSError("down")):
            res = self.client.post("/api/query", json={"question": "Q?"})
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["error"], "ollama_unavailable")

    def test_recent_and_answer_detail(self) -> None:
        with patch("dashboard.call_query_ollama", return_value="Answer."):
            first = self.client.post("/api/query", json={"question": "Q1?"})
        filename = Path(first.json()["saved_path"]).name

        recent = self.client.get("/api/answers/recent")
        self.assertEqual(recent.status_code, 200)
        self.assertLessEqual(len(recent.json()["answers"]), 5)

        detail = self.client.get(f"/api/answers/{filename}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["question"], "Q1?")

    def test_feedback_endpoint_marks_answer(self) -> None:
        with patch("dashboard.call_query_ollama", return_value="Answer."):
            first = self.client.post("/api/query", json={"question": "Q1?"})
        filename = Path(first.json()["saved_path"]).name

        res = self.client.post(
            "/api/feedback",
            json={"answer_id": filename, "rating": "bad", "note": "too generic"},
        )
        self.assertEqual(res.status_code, 200)
        detail = self.client.get(f"/api/answers/{filename}")
        self.assertEqual(detail.json()["feedback"], "bad")
        self.assertEqual(detail.json()["feedback_note"], "too generic")


class ResynthesizeEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_post_resynthesize_success(self) -> None:
        fake_result = MagicMock()
        fake_result.topic_slug = "openclaw-security"
        fake_result.synthesis_version = 2
        fake_result.sources_used = 3
        fake_result.committed = True
        with patch("dashboard.resynthesize_topic", return_value=fake_result):
            res = self.client.post("/api/resynthesize", json={"topic_slug": "openclaw-security"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["synthesis_version"], 2)

    def test_post_resynthesize_insufficient_sources(self) -> None:
        with patch(
            "dashboard.resynthesize_topic",
            side_effect=dashboard.InsufficientSourcesError("Only 1 approved source summary found."),
        ):
            res = self.client.post("/api/resynthesize", json={"topic_slug": "openclaw-security"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "insufficient_sources")


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts/inbox_watcher.py (Phase 6)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.inbox_watcher import (
    detect_adapter,
    derive_origin,
    derive_source_type,
    derive_title,
    load_state,
    load_review_queue,
    save_state,
    scan_inbox,
    validate_ingested_note,
)


# ---------------------------------------------------------------------------
# Title derivation
# ---------------------------------------------------------------------------

class DeriveTitleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, name: str, content: str) -> Path:
        p = self.root / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_frontmatter_title_wins(self) -> None:
        p = self._write("note.md", '---\ntitle: "My Frontmatter Title"\n---\n\n# Other Heading\n')
        self.assertEqual(derive_title(p), "My Frontmatter Title")

    def test_first_heading_used_when_no_frontmatter(self) -> None:
        p = self._write("note.md", "# The Real Title\n\nSome body text.\n")
        self.assertEqual(derive_title(p), "The Real Title")

    def test_first_plain_line_used_when_no_heading(self) -> None:
        p = self._write("note.txt", "Plain title line\n\nBody text here.\n")
        self.assertEqual(derive_title(p), "Plain title line")

    def test_filename_stem_used_as_fallback(self) -> None:
        p = self._write("my-interesting-note.md", "")
        self.assertEqual(derive_title(p), "My Interesting Note")

    def test_pdf_uses_filename_stem(self) -> None:
        p = self._write("security-overview.pdf", "")
        self.assertEqual(derive_title(p), "Security Overview")

    def test_heading_markers_stripped(self) -> None:
        p = self._write("note.md", "## Section Heading\n\nBody.\n")
        self.assertEqual(derive_title(p), "Section Heading")

    def test_frontmatter_skipped_when_deriving_first_line(self) -> None:
        p = self._write("note.md", "---\ndate: 2026-04-10\n---\n\nActual Content Title\n")
        self.assertEqual(derive_title(p), "Actual Content Title")

    def test_long_first_line_is_capped(self) -> None:
        p = self._write("note.txt", "A" * 200 + "\n")
        self.assertLessEqual(len(derive_title(p)), 120)

    def test_html_title_tag_used(self) -> None:
        html = "<!DOCTYPE html><html><head><title>Real Page Title</title></head><body><p>Content</p></body></html>"
        p = self._write("page.html", html)
        self.assertEqual(derive_title(p), "Real Page Title")

    def test_html_entities_decoded_in_title(self) -> None:
        html = "<!DOCTYPE html><html><head><title>Features &amp; Updates</title></head><body></body></html>"
        p = self._write("page.html", html)
        self.assertEqual(derive_title(p), "Features & Updates")

    def test_html_doctype_not_used_as_title(self) -> None:
        html = "<!DOCTYPE html><html><head><title>Actual Title</title></head><body></body></html>"
        p = self._write("page.html", html)
        self.assertNotEqual(derive_title(p), "doctype-html")
        self.assertNotIn("doctype", derive_title(p).lower())

    def test_html_without_title_tag_falls_back_to_body_text(self) -> None:
        html = "<!DOCTYPE html><html><body><h1>Body Heading</h1><p>Some text.</p></body></html>"
        p = self._write("page.html", html)
        result = derive_title(p)
        self.assertIn("Body Heading", result)

    def test_html_without_any_text_falls_back_to_filename(self) -> None:
        p = self._write("my-article.html", "<!DOCTYPE html><html><body></body></html>")
        self.assertEqual(derive_title(p), "My Article")


# ---------------------------------------------------------------------------
# Source type and origin derivation
# ---------------------------------------------------------------------------

class DeriveSourceTypeTests(unittest.TestCase):
    def _path(self, name: str) -> Path:
        return Path(name)

    def test_pdf_always_pdf(self) -> None:
        self.assertEqual(derive_source_type(self._path("doc.pdf"), "article"), "pdf")

    def test_md_uses_default(self) -> None:
        self.assertEqual(derive_source_type(self._path("note.md"), "note"), "note")

    def test_txt_uses_default(self) -> None:
        self.assertEqual(derive_source_type(self._path("note.txt"), "article"), "article")


class DeriveOriginTests(unittest.TestCase):
    def _path(self, name: str) -> Path:
        return Path(name)

    def test_pdf_is_local_file(self) -> None:
        self.assertEqual(derive_origin(self._path("doc.pdf")), "local-file")

    def test_md_is_local_markdown(self) -> None:
        self.assertEqual(derive_origin(self._path("note.md")), "local-markdown")

    def test_txt_is_local_file(self) -> None:
        self.assertEqual(derive_origin(self._path("note.txt")), "local-file")


class DetectAdapterTests(unittest.TestCase):
    def test_detects_browser_subdir(self) -> None:
        self.assertEqual(detect_adapter(Path("/tmp/repo/raw/inbox/browser/item.md")), "browser")

    def test_defaults_to_inbox(self) -> None:
        self.assertEqual(detect_adapter(Path("/tmp/repo/raw/inbox/item.md")), "inbox")


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "metadata" / ".watcher-state.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_and_load_roundtrip(self) -> None:
        import scripts.inbox_watcher as mod
        original_path = mod.STATE_PATH
        mod.STATE_PATH = self.state_path
        try:
            state = {"/some/path/file.md": "2026-04-10T10:00:00"}
            save_state(state)
            loaded = load_state()
            self.assertEqual(loaded, state)
        finally:
            mod.STATE_PATH = original_path

    def test_load_returns_empty_when_file_missing(self) -> None:
        import scripts.inbox_watcher as mod
        original_path = mod.STATE_PATH
        mod.STATE_PATH = self.state_path  # doesn't exist yet
        try:
            self.assertEqual(load_state(), {})
        finally:
            mod.STATE_PATH = original_path

    def test_load_returns_empty_on_corrupt_json(self) -> None:
        import scripts.inbox_watcher as mod
        original_path = mod.STATE_PATH
        mod.STATE_PATH = self.state_path
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text("not json", encoding="utf-8")
            self.assertEqual(load_state(), {})
        finally:
            mod.STATE_PATH = original_path


# ---------------------------------------------------------------------------
# scan_inbox
# ---------------------------------------------------------------------------

class ScanInboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        # Minimal repo structure for ingest to work
        for d in [
            "raw/inbox", "raw/articles", "raw/notes", "raw/pdfs",
            "raw/archive", "metadata", "raw/inbox/browser", "raw/inbox/clipboard",
            "raw/inbox/feeds", "raw/inbox/pdf-drop",
        ]:
            (self.root / d).mkdir(parents=True, exist_ok=True)

        (self.root / "metadata" / "source-manifest.json").write_text(
            json.dumps({"manifest_version": "0.2.0", "last_updated": "", "description": "", "sources": []}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _drop(self, name: str, content: str) -> Path:
        p = self.root / "raw" / "inbox" / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_new_file_is_ingested_and_added_to_state(self) -> None:
        import scripts.inbox_watcher as mod
        original_root = mod.ROOT
        original_review_queue = mod.REVIEW_QUEUE_PATH
        original_review_md = mod.REVIEW_QUEUE_REPORT_PATH
        mod.ROOT = self.root
        mod.REVIEW_QUEUE_PATH = self.root / "metadata" / "review-queue.json"
        mod.REVIEW_QUEUE_REPORT_PATH = self.root / "metadata" / "review-queue.md"
        try:
            self._drop("my-article.md", "# My Article\n\nSome content.\n")
            state = scan_inbox(self.root / "raw" / "inbox", {}, "article")
            self.assertEqual(len(state), 1)
            output = self.root / "raw" / "articles" / "my-article.md"
            self.assertTrue(output.exists(), f"Expected {output}")
            queue = load_review_queue()
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["review_status"], "pending_review")
            self.assertEqual(queue[0]["validation_status"], "validated")
        finally:
            mod.ROOT = original_root
            mod.REVIEW_QUEUE_PATH = original_review_queue
            mod.REVIEW_QUEUE_REPORT_PATH = original_review_md

    def test_already_processed_file_is_skipped(self) -> None:
        import scripts.inbox_watcher as mod
        original_root = mod.ROOT
        mod.ROOT = self.root
        try:
            p = self._drop("already-done.md", "# Already Done\n\nContent.\n")
            existing_state = {str(p.resolve()): "2026-04-10T09:00:00"}
            state = scan_inbox(self.root / "raw" / "inbox", existing_state, "article")
            # State unchanged — file was skipped
            self.assertEqual(state, existing_state)
        finally:
            mod.ROOT = original_root

    def test_unsupported_extension_is_ignored(self) -> None:
        import scripts.inbox_watcher as mod
        original_root = mod.ROOT
        mod.ROOT = self.root
        try:
            (self.root / "raw" / "inbox" / "data.csv").write_text("a,b,c", encoding="utf-8")
            state = scan_inbox(self.root / "raw" / "inbox", {}, "article")
            self.assertEqual(state, {})
        finally:
            mod.ROOT = original_root

    def test_nonexistent_inbox_returns_state_unchanged(self) -> None:
        state = {"existing": "value"}
        result = scan_inbox(Path("/tmp/nonexistent-inbox-xyz"), state, "article")
        self.assertEqual(result, state)

    def test_multiple_files_all_ingested(self) -> None:
        import scripts.inbox_watcher as mod
        original_root = mod.ROOT
        original_review_queue = mod.REVIEW_QUEUE_PATH
        original_review_md = mod.REVIEW_QUEUE_REPORT_PATH
        mod.ROOT = self.root
        mod.REVIEW_QUEUE_PATH = self.root / "metadata" / "review-queue.json"
        mod.REVIEW_QUEUE_REPORT_PATH = self.root / "metadata" / "review-queue.md"
        try:
            self._drop("article-one.md", "# Article One\n\nContent one.\n")
            self._drop("article-two.txt", "Article Two\n\nContent two.\n")
            state = scan_inbox(self.root / "raw" / "inbox", {}, "article")
            self.assertEqual(len(state), 2)
            queue = load_review_queue()
            self.assertEqual(len(queue), 2)
        finally:
            mod.ROOT = original_root
            mod.REVIEW_QUEUE_PATH = original_review_queue
            mod.REVIEW_QUEUE_REPORT_PATH = original_review_md

    def test_adapter_subdirectories_are_scanned(self) -> None:
        import scripts.inbox_watcher as mod
        original_root = mod.ROOT
        original_review_queue = mod.REVIEW_QUEUE_PATH
        original_review_md = mod.REVIEW_QUEUE_REPORT_PATH
        mod.ROOT = self.root
        mod.REVIEW_QUEUE_PATH = self.root / "metadata" / "review-queue.json"
        mod.REVIEW_QUEUE_REPORT_PATH = self.root / "metadata" / "review-queue.md"
        try:
            browser_path = self.root / "raw" / "inbox" / "browser" / "web-clip.md"
            browser_path.write_text(
                '---\ntitle: "Web Clip"\ncanonical_url: "https://example.com"\n---\n\nBody.\n',
                encoding="utf-8",
            )
            state = scan_inbox(self.root / "raw" / "inbox", {}, "article")
            self.assertEqual(len(state), 1)
            queue = load_review_queue()
            self.assertEqual(queue[0]["adapter"], "browser")
            self.assertEqual(queue[0]["origin"], "web")
        finally:
            mod.ROOT = original_root
            mod.REVIEW_QUEUE_PATH = original_review_queue
            mod.REVIEW_QUEUE_REPORT_PATH = original_review_md


class ValidateIngestedNoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_note_has_no_issues(self) -> None:
        path = self.root / "note.md"
        path.write_text(
            (
                "---\n"
                'title: "Valid"\n'
                'source_type: "article"\n'
                'origin: "web"\n'
                'date_ingested: "2026-04-11"\n'
                'status: "raw"\n'
                "topics:\n"
                "tags:\n"
                'source_id: "SRC-20260411-0001"\n'
                'canonical_url: "https://example.com"\n'
                "---\n\n"
                "# Overview\n\nX\n\n# Source Content\n\nY\n\n# Key Points\n\n- Z\n\n# Notes\n\nN\n\n# Lineage\n\nL\n"
            ),
            encoding="utf-8",
        )
        self.assertEqual(validate_ingested_note(path), [])

    def test_missing_required_fields_are_reported(self) -> None:
        path = self.root / "bad.md"
        path.write_text("# Overview\n", encoding="utf-8")
        issues = validate_ingested_note(path)
        self.assertTrue(any("missing frontmatter field: title" == issue for issue in issues))
        self.assertTrue(any("missing section heading: # Source Content" == issue for issue in issues))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts.ingest import IngestRequest
from scripts.ingest import build_archive_filename
from scripts.ingest import destination_dir_for_source_type
from scripts.ingest import html_to_text
from scripts.ingest import ingest_source
from scripts.ingest import slugify_title


class IngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        for relative in [
            "raw/inbox",
            "raw/archive",
            "raw/articles",
            "raw/notes",
            "raw/pdfs",
            "metadata",
            "external",
        ]:
            (self.root / relative).mkdir(parents=True, exist_ok=True)

        (self.root / "metadata" / "source-manifest.json").write_text(
            json.dumps(
                {
                    "manifest_version": "0.2.0",
                    "last_updated": "",
                    "description": "Test manifest",
                    "sources": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_slug_generation(self) -> None:
        self.assertEqual(slugify_title("AWS Patch Manager Basics"), "aws-patch-manager-basics")
        self.assertEqual(slugify_title("  Mixed CASE / spacing  "), "mixed-case-spacing")

    def test_destination_path_selection(self) -> None:
        self.assertEqual(destination_dir_for_source_type("article"), Path("raw/articles"))
        self.assertEqual(destination_dir_for_source_type("note"), Path("raw/notes"))
        self.assertEqual(destination_dir_for_source_type("pdf"), Path("raw/pdfs"))
        self.assertEqual(destination_dir_for_source_type("unknown"), Path("raw/inbox"))

    def test_note_creation_and_manifest_update(self) -> None:
        request = IngestRequest(
            title="Example Note",
            source_type="note",
            origin="manual-entry",
            text="First paragraph.\n\nSecond paragraph.",
            root=self.root,
        )

        output_path = ingest_source(request)

        self.assertTrue(output_path.exists())
        note_text = output_path.read_text(encoding="utf-8")
        self.assertIn('title: "Example Note"', note_text)
        self.assertIn("# Source Content", note_text)
        self.assertIn("First paragraph.\n\nSecond paragraph.", note_text)

        manifest = json.loads((self.root / "metadata" / "source-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["sources"]), 1)
        self.assertEqual(manifest["sources"][0]["path"], "raw/notes/example-note.md")
        self.assertEqual(manifest["sources"][0]["source_type"], "note")

    def test_ingestion_from_inbox_auto_archives_original_file(self) -> None:
        inbox_file = self.root / "raw" / "inbox" / "sample-article.txt"
        inbox_file.write_text("Original inbox content.", encoding="utf-8")

        archived_at = datetime(2026, 4, 5, 21, 30, 45)
        with patch("scripts.ingest.datetime") as mock_datetime:
            mock_datetime.now.return_value = archived_at
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            output_path = ingest_source(
                IngestRequest(
                    title="Sample Article",
                    source_type="article",
                    origin="local-file",
                    input_path=str(inbox_file),
                    root=self.root,
                )
            )

        self.assertTrue(output_path.exists())
        self.assertFalse(inbox_file.exists())

        archived_files = list((self.root / "raw" / "archive").glob("sample-article--archived-*.txt"))
        self.assertEqual(len(archived_files), 1)
        self.assertEqual(
            archived_files[0].name,
            "sample-article--archived-20260405-213045.txt",
        )
        self.assertEqual(archived_files[0].read_text(encoding="utf-8"), "Original inbox content.")

    def test_archived_filename_gets_timestamp_suffix_while_active_note_stays_clean(self) -> None:
        inbox_file = self.root / "raw" / "inbox" / "openclaw-security-best-practices.md"
        inbox_file.write_text("Inbox markdown content.", encoding="utf-8")

        archived_at = datetime(2026, 4, 5, 21, 30, 45)
        with patch("scripts.ingest.datetime") as mock_datetime:
            mock_datetime.now.return_value = archived_at
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            output_path = ingest_source(
                IngestRequest(
                    title="OpenClaw Security Best Practices",
                    source_type="article",
                    origin="local-markdown",
                    input_path=str(inbox_file),
                    root=self.root,
                )
            )

        self.assertEqual(output_path.name, "openclaw-security-best-practices.md")
        archived_files = list((self.root / "raw" / "archive").glob("openclaw-security-best-practices--archived-*.md"))
        self.assertEqual(len(archived_files), 1)
        self.assertEqual(
            archived_files[0].name,
            "openclaw-security-best-practices--archived-20260405-213045.md",
        )

    def test_ingestion_from_outside_inbox_does_not_auto_archive(self) -> None:
        external_file = self.root / "external" / "outside-source.txt"
        external_file.write_text("Outside source content.", encoding="utf-8")

        output_path = ingest_source(
            IngestRequest(
                title="Outside Source",
                source_type="article",
                origin="local-file",
                input_path=str(external_file),
                root=self.root,
            )
        )

        self.assertTrue(output_path.exists())
        self.assertTrue(external_file.exists())
        self.assertEqual(list((self.root / "raw" / "archive").iterdir()), [])

    def test_archive_does_not_overwrite_existing_files(self) -> None:
        inbox_file = self.root / "raw" / "inbox" / "sample-article.txt"
        inbox_file.write_text("Original inbox content.", encoding="utf-8")

        archived_at = datetime(2026, 4, 5, 21, 30, 45)
        existing_archive = self.root / "raw" / "archive" / build_archive_filename(inbox_file, archived_at)
        existing_archive.write_text("Older archived copy.", encoding="utf-8")

        with patch("scripts.ingest.datetime") as mock_datetime:
            mock_datetime.now.return_value = archived_at
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            ingest_source(
                IngestRequest(
                    title="Sample Article",
                    source_type="article",
                    origin="local-file",
                    input_path=str(inbox_file),
                    root=self.root,
                )
            )

        self.assertTrue(existing_archive.exists())
        self.assertEqual(existing_archive.read_text(encoding="utf-8"), "Older archived copy.")

        archived_files = sorted((self.root / "raw" / "archive").glob("sample-article--archived-20260405-213045*.txt"))
        self.assertEqual(len(archived_files), 2)
        self.assertIn("sample-article--archived-20260405-213045-2.txt", [path.name for path in archived_files])

    def test_failed_ingestion_does_not_move_original_file(self) -> None:
        inbox_file = self.root / "raw" / "inbox" / "existing-note.txt"
        inbox_file.write_text("Original inbox content.", encoding="utf-8")

        first_request = IngestRequest(
            title="Existing Note",
            source_type="article",
            origin="local-file",
            text="Original content.",
            root=self.root,
        )
        ingest_source(first_request)

        failing_request = IngestRequest(
            title="Existing Note",
            source_type="article",
            origin="local-file",
            input_path=str(inbox_file),
            root=self.root,
        )

        with self.assertRaises(FileExistsError):
            ingest_source(failing_request)

        self.assertTrue(inbox_file.exists())
        self.assertEqual(list((self.root / "raw" / "archive").iterdir()), [])

    def test_no_overwrite_by_default(self) -> None:
        request = IngestRequest(
            title="Existing Note",
            source_type="article",
            origin="manual-entry",
            text="Original content.",
            root=self.root,
        )

        first_output = ingest_source(request)
        self.assertTrue(first_output.exists())

        with self.assertRaises(FileExistsError):
            ingest_source(request)


class HtmlToTextTests(unittest.TestCase):
    def test_strips_tags_and_returns_text(self) -> None:
        result = html_to_text("<p>Hello <b>world</b></p>")
        self.assertIn("Hello world", result)
        self.assertNotIn("<", result)

    def test_script_and_style_content_removed(self) -> None:
        html = "<style>.foo { width: 300px; height: 250px; }</style><p>Visible text</p><script>var x = [728, 90];</script>"
        result = html_to_text(html)
        self.assertIn("Visible text", result)
        self.assertNotIn("300px", result)
        self.assertNotIn("728", result)

    def test_html_entities_unescaped(self) -> None:
        result = html_to_text("<p>AT&amp;T &mdash; &lt;example&gt;</p>")
        self.assertIn("AT&T", result)
        self.assertIn("—", result)
        self.assertNotIn("&amp;", result)

    def test_block_tags_become_newlines(self) -> None:
        result = html_to_text("<h1>Title</h1><p>Para one</p><p>Para two</p>")
        lines = [l for l in result.splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 2)
        self.assertIn("Title", result)
        self.assertIn("Para one", result)
        self.assertIn("Para two", result)

    def test_head_content_excluded(self) -> None:
        html = "<html><head><title>Page Title</title><meta charset='utf-8'></head><body><p>Body text</p></body></html>"
        result = html_to_text(html)
        self.assertIn("Body text", result)
        self.assertNotIn("Page Title", result)

    def test_consecutive_blank_lines_collapsed(self) -> None:
        html = "<p>First</p><p></p><p></p><p>Second</p>"
        result = html_to_text(html)
        self.assertNotIn("\n\n\n", result)

    def test_html_file_ingested_as_plain_text(self) -> None:
        """End-to-end: HTML file from inbox/browser/ is stripped before note body."""
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for d in ["raw/inbox/browser", "raw/archive", "raw/articles", "raw/notes", "raw/pdfs", "metadata"]:
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "metadata" / "source-manifest.json").write_text(
            '{"manifest_version":"0.2.0","last_updated":"","description":"","sources":[]}',
            encoding="utf-8",
        )
        html_file = root / "raw" / "inbox" / "browser" / "article.html"
        html_file.write_text(
            "<html><head><style>.ad { width: 728px; height: 90px; }</style></head>"
            "<body><h1>Real Article Title</h1><p>Actual readable content here.</p></body></html>",
            encoding="utf-8",
        )
        from scripts.ingest import IngestRequest, ingest_source
        output = ingest_source(IngestRequest(
            title="Real Article Title",
            source_type="article",
            origin="web",
            input_path=str(html_file),
            root=root,
        ))
        note = output.read_text(encoding="utf-8")
        self.assertIn("Actual readable content here.", note)
        self.assertNotIn("728px", note)
        self.assertNotIn("<style>", note)
        temp.cleanup()


if __name__ == "__main__":
    unittest.main()

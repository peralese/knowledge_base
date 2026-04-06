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


if __name__ == "__main__":
    unittest.main()

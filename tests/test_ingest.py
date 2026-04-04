from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ingest import IngestRequest
from scripts.ingest import destination_dir_for_source_type
from scripts.ingest import ingest_source
from scripts.ingest import slugify_title


class IngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        for relative in [
            "raw/inbox",
            "raw/articles",
            "raw/notes",
            "raw/pdfs",
            "metadata",
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

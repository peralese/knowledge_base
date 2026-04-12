from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.stage_to_inbox import StageRequest, stage


class StageToInboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "raw" / "inbox").mkdir(parents=True, exist_ok=True)
        (self.root / "external").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_clipboard_stage_writes_markdown_wrapper(self) -> None:
        destination = stage(
            StageRequest(
                adapter="clipboard",
                title="Clipboard Note",
                text="Clipboard body",
                canonical_url="https://example.com",
                root=self.root,
            )
        )
        self.assertTrue(destination.exists())
        content = destination.read_text(encoding="utf-8")
        self.assertIn('title: "Clipboard Note"', content)
        self.assertIn('canonical_url: "https://example.com"', content)
        self.assertIn("Clipboard body", content)

    def test_browser_stage_copies_file(self) -> None:
        source = self.root / "external" / "clip.html"
        source.write_text("<html>hello</html>", encoding="utf-8")
        destination = stage(
            StageRequest(
                adapter="browser",
                input_file=source,
                root=self.root,
            )
        )
        self.assertTrue(destination.exists())
        self.assertEqual(destination.read_text(encoding="utf-8"), "<html>hello</html>")

    def test_feed_stage_writes_json_payload(self) -> None:
        destination = stage(
            StageRequest(
                adapter="feeds",
                text=json.dumps(
                    {
                        "title": "Feed Item",
                        "url": "https://example.com/feed-item",
                        "content": "Body from feed",
                    }
                ),
                root=self.root,
            )
        )
        payload = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(payload["title"], "Feed Item")
        self.assertEqual(payload["canonical_url"], "https://example.com/feed-item")
        self.assertEqual(payload["content"], "Body from feed")

    def test_pdf_stage_copies_file_to_pdf_drop(self) -> None:
        source = self.root / "external" / "whitepaper.pdf"
        source.write_bytes(b"%PDF-1.7")
        destination = stage(
            StageRequest(
                adapter="pdf-drop",
                input_file=source,
                root=self.root,
            )
        )
        self.assertTrue(destination.exists())
        self.assertEqual(destination.read_bytes(), b"%PDF-1.7")


if __name__ == "__main__":
    unittest.main()

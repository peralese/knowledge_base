from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.resynthesize_topic import (
    InsufficientSourcesError,
    resynthesize_topic,
    topic_status,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class ResynthesizeTopicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write(
            self.root / "metadata" / "topic-registry.json",
            '{"topics": [{"slug": "openclaw-security", "title": "OpenClaw Security"}]}\n',
        )
        _write(
            self.root / "compiled" / "topics" / "openclaw-security.md",
            """---
title: OpenClaw Security
note_type: topic
compiled_from:
  - source-a-synthesis
  - source-b-synthesis
date_compiled: 2026-04-18
date_updated: 2026-04-19
synthesis_version: 1
approved: true
---

Old body.

# Source Notes

- [[source-a-synthesis]]
- [[source-b-synthesis]]
""",
        )
        _write(
            self.root / "compiled" / "source_summaries" / "source-a-synthesis.md",
            "---\ntitle: A\napproved: true\n---\n\nAlpha.",
        )
        _write(
            self.root / "compiled" / "source_summaries" / "source-b-synthesis.md",
            "---\ntitle: B\napproved: true\n---\n\nBeta.",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_status_counts_sources(self) -> None:
        status = topic_status("openclaw-security", self.root)
        self.assertEqual(status["source_count"], 2)
        self.assertEqual(status["approved_source_count"], 2)
        self.assertEqual(status["synthesis_version"], 1)

    def test_resynthesize_updates_topic_note_and_version(self) -> None:
        with (
            patch("scripts.resynthesize_topic._check_model_available"),
            patch("scripts.resynthesize_topic.call_ollama", return_value="## Overview\n\nNew synthesis."),
            patch("scripts.resynthesize_topic.commit_pipeline_stage", return_value=True) as mock_commit,
        ):
            result = resynthesize_topic("openclaw-security", root=self.root)

        self.assertEqual(result.synthesis_version, 2)
        self.assertEqual(result.sources_used, 2)
        self.assertTrue(result.committed)
        text = (self.root / "compiled" / "topics" / "openclaw-security.md").read_text(encoding="utf-8")
        self.assertIn("synthesis_version: 2", text)
        self.assertIn("sources:\n  - compiled/source_summaries/source-a-synthesis.md", text)
        self.assertIn("## Overview\n\nNew synthesis.", text)
        mock_commit.assert_called_once()

    def test_insufficient_sources_raises_without_writing(self) -> None:
        (self.root / "compiled" / "source_summaries" / "source-b-synthesis.md").write_text(
            "---\ntitle: B\napproved: false\n---\n\nBeta.",
            encoding="utf-8",
        )
        path = self.root / "compiled" / "topics" / "openclaw-security.md"
        before = path.read_text(encoding="utf-8")
        with self.assertRaises(InsufficientSourcesError):
            resynthesize_topic("openclaw-security", root=self.root)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_dry_run_returns_preview_without_writing_or_committing(self) -> None:
        path = self.root / "compiled" / "topics" / "openclaw-security.md"
        before = path.read_text(encoding="utf-8")
        with patch("scripts.resynthesize_topic.commit_pipeline_stage") as mock_commit:
            result = resynthesize_topic("openclaw-security", root=self.root, dry_run=True)
        self.assertTrue(result.dry_run)
        self.assertIn("Source summaries:", result.preview)
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        mock_commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Tests for review.py 2C additions: show, list --full, session mode."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review import (
    _find_compiled_note,
    _read_canonical_url,
    _read_compiled_content,
    cmd_list,
    cmd_session,
    cmd_show,
    load_queue,
    save_queue,
)


def _slug_for(source_id: str) -> str:
    """Mirror the filename stem convention used by the actual ingestion pipeline."""
    return source_id.lower().replace("-", "")


def _make_queue_entry(
    source_id: str = "SRC-20260412-0001",
    title: str = "Test Article",
    review_status: str = "synthesized",
    confidence_score: float = 0.75,
    confidence_band: str = "medium",
    review_action: str | None = None,
    topic_slug: str = "test-topic",
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "source_note_path": f"raw/articles/{_slug_for(source_id)}.md",
        "adapter": "browser",
        "source_type": "article",
        "origin": "web",
        "topic_slug": topic_slug,
        "queued_at": "2026-04-15T10:00:00",
        "review_status": review_status,
        "validation_status": "validated",
        "validation_issues": [],
        "confidence_score": confidence_score,
        "confidence_band": confidence_band,
        "review_action": review_action,
        "review_method": None,
        "reviewed_at": None,
    }


class ReadCompiledContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_synthesis(self, slug: str, content: str) -> Path:
        path = self.root / "compiled" / "source_summaries" / f"{slug}-synthesis.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_returns_content_when_synthesis_exists(self) -> None:
        article_stem = "my-article"
        self._write_synthesis(article_stem, "# Synthesis\n\nThis is the synthesis content.\n")
        entry = {
            "source_note_path": f"raw/articles/{article_stem}.md",
        }
        content = _read_compiled_content(entry, self.root)
        self.assertIn("synthesis content", content)

    def test_returns_message_when_no_path(self) -> None:
        entry = {"source_note_path": ""}
        content = _read_compiled_content(entry, self.root)
        self.assertIn("No compiled synthesis path", content)

    def test_returns_message_when_synthesis_missing(self) -> None:
        # nonexistent.md → looks for compiled/source_summaries/nonexistent-synthesis.md
        entry = {"source_note_path": "raw/articles/nonexistent.md"}
        content = _read_compiled_content(entry, self.root)
        # Synthesis file doesn't exist → _find_compiled_note returns None
        self.assertIn("No compiled synthesis path", content)


class ReadCanonicalUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_reads_canonical_url_from_frontmatter(self) -> None:
        article = self.root / "raw" / "articles" / "my-article.md"
        article.parent.mkdir(parents=True, exist_ok=True)
        article.write_text(
            '---\ntitle: "My Article"\ncanonical_url: "https://example.com/article"\n---\n\nBody.\n',
            encoding="utf-8",
        )
        entry = {"source_note_path": "raw/articles/my-article.md"}
        url = _read_canonical_url(entry, self.root)
        self.assertEqual(url, "https://example.com/article")

    def test_returns_empty_when_no_canonical_url(self) -> None:
        article = self.root / "raw" / "articles" / "no-url.md"
        article.parent.mkdir(parents=True, exist_ok=True)
        article.write_text('---\ntitle: "T"\n---\n\nBody.\n', encoding="utf-8")
        entry = {"source_note_path": "raw/articles/no-url.md"}
        url = _read_canonical_url(entry, self.root)
        self.assertEqual(url, "")

    def test_returns_empty_for_missing_article(self) -> None:
        entry = {"source_note_path": "raw/articles/ghost.md"}
        url = _read_canonical_url(entry, self.root)
        self.assertEqual(url, "")


class CmdShowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # slug = source_id.lower().replace("-", "") = "src202604120001"
        slug = _slug_for("SRC-20260412-0001")
        # Create synthesis note
        synth_dir = self.root / "compiled" / "source_summaries"
        synth_dir.mkdir(parents=True, exist_ok=True)
        (synth_dir / f"{slug}-synthesis.md").write_text(
            "---\napproved: false\n---\n\n# Synthesis\n\nTest synthesis body.\n",
            encoding="utf-8",
        )
        # Create raw article
        articles_dir = self.root / "raw" / "articles"
        articles_dir.mkdir(parents=True, exist_ok=True)
        (articles_dir / f"{slug}.md").write_text(
            '---\ntitle: "T"\ncanonical_url: "https://example.com"\n---\n\nBody.\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_queue_file(self, entries: list) -> Path:
        meta = self.root / "metadata"
        meta.mkdir(parents=True, exist_ok=True)
        qpath = meta / "review-queue.json"
        qpath.write_text(json.dumps(entries) + "\n", encoding="utf-8")
        return qpath

    def test_show_not_found_returns_1(self) -> None:
        self._make_queue_file([])
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            result = cmd_show("SRC-DOESNT-EXIST", root=self.root)
        self.assertEqual(result, 1)

    def test_show_existing_item_prints_content(self) -> None:
        entry = _make_queue_entry(source_id="SRC-20260412-0001")
        self._make_queue_file([entry])
        captured = io.StringIO()
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            with patch("sys.stdout", captured):
                result = cmd_show("SRC-20260412-0001", root=self.root)
        self.assertEqual(result, 0)
        output = captured.getvalue()
        self.assertIn("SRC-20260412-0001", output)
        self.assertIn("Test Article", output)


class CmdListFullTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        slug = _slug_for("SRC-20260412-0001")
        synth_dir = self.root / "compiled" / "source_summaries"
        synth_dir.mkdir(parents=True, exist_ok=True)
        (synth_dir / f"{slug}-synthesis.md").write_text(
            "---\napproved: false\n---\n\n# Synthesis\n\nFull body text here.\n",
            encoding="utf-8",
        )
        meta = self.root / "metadata"
        meta.mkdir(parents=True, exist_ok=True)
        queue = [_make_queue_entry()]
        (meta / "review-queue.json").write_text(json.dumps(queue) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_list_full_includes_synthesis_text(self) -> None:
        captured = io.StringIO()
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            with patch("review.ROOT", self.root):
                with patch("sys.stdout", captured):
                    result = cmd_list(full=True)
        self.assertEqual(result, 0)
        output = captured.getvalue()
        self.assertIn("Full body text here", output)

    def test_list_without_full_does_not_include_synthesis(self) -> None:
        captured = io.StringIO()
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            with patch("review.ROOT", self.root):
                with patch("sys.stdout", captured):
                    result = cmd_list(full=False)
        self.assertEqual(result, 0)
        output = captured.getvalue()
        self.assertNotIn("Full body text here", output)


class CmdSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        slug1 = _slug_for("SRC-20260412-0001")
        slug2 = _slug_for("SRC-20260412-0002")
        synth_dir = self.root / "compiled" / "source_summaries"
        synth_dir.mkdir(parents=True, exist_ok=True)
        (synth_dir / f"{slug1}-synthesis.md").write_text(
            "---\napproved: false\n---\n\n# Synthesis\n\nBody.\n", encoding="utf-8"
        )
        (synth_dir / f"{slug2}-synthesis.md").write_text(
            "---\napproved: false\n---\n\n# Synthesis\n\nBody 2.\n", encoding="utf-8"
        )
        meta = self.root / "metadata"
        meta.mkdir(parents=True, exist_ok=True)
        queue = [
            _make_queue_entry("SRC-20260412-0001", "Article One"),
            _make_queue_entry("SRC-20260412-0002", "Article Two"),
        ]
        (meta / "review-queue.json").write_text(json.dumps(queue) + "\n", encoding="utf-8")
        (meta / "review-queue.md").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_session_approve_updates_queue(self) -> None:
        # Simulate keypresses: 'a' (approve first), 'q' (quit)
        keypresses = iter(["a", "q"])
        captured = io.StringIO()
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            with patch("review.REVIEW_QUEUE_REPORT_PATH", self.root / "metadata" / "review-queue.md"):
                with patch("review.ROOT", self.root):
                    with patch("review._getch", side_effect=keypresses):
                        with patch("sys.stdout", captured):
                            with patch("review.commit_pipeline_stage"):
                                result = cmd_session(root=self.root, no_commit=True)
        self.assertEqual(result, 0)
        output = captured.getvalue()
        self.assertIn("approved: 1", output)

    def test_session_reject_updates_queue(self) -> None:
        # Simulate keypresses: 'r' (reject first), 'q' (quit)
        keypresses = iter(["r", "q"])
        captured = io.StringIO()
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            with patch("review.REVIEW_QUEUE_REPORT_PATH", self.root / "metadata" / "review-queue.md"):
                with patch("review.ROOT", self.root):
                    with patch("review._getch", side_effect=keypresses):
                        with patch("sys.stdout", captured):
                            with patch("review.commit_pipeline_stage"):
                                result = cmd_session(root=self.root, no_commit=True)
        self.assertEqual(result, 0)
        output = captured.getvalue()
        self.assertIn("rejected: 1", output)

    def test_session_skip_does_not_change_queue(self) -> None:
        keypresses = iter(["s", "s"])
        captured = io.StringIO()
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            with patch("review.REVIEW_QUEUE_REPORT_PATH", self.root / "metadata" / "review-queue.md"):
                with patch("review.ROOT", self.root):
                    with patch("review._getch", side_effect=keypresses):
                        with patch("sys.stdout", captured):
                            with patch("review.commit_pipeline_stage"):
                                result = cmd_session(root=self.root, no_commit=True)
        self.assertEqual(result, 0)
        queue = json.loads((self.root / "metadata" / "review-queue.json").read_text())
        reviewed = [e for e in queue if e.get("review_action") is not None]
        self.assertEqual(len(reviewed), 0)
        output = captured.getvalue()
        self.assertIn("skipped: 2", output)

    def test_session_empty_queue_returns_0(self) -> None:
        (self.root / "metadata" / "review-queue.json").write_text("[]", encoding="utf-8")
        captured = io.StringIO()
        with patch("review.REVIEW_QUEUE_PATH", self.root / "metadata" / "review-queue.json"):
            with patch("review.ROOT", self.root):
                with patch("sys.stdout", captured):
                    result = cmd_session(root=self.root, no_commit=True)
        self.assertEqual(result, 0)
        self.assertIn("Queue is empty", captured.getvalue())


if __name__ == "__main__":
    unittest.main()

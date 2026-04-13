"""Tests for scripts/synthesize.py (Phase 2)."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.synthesize import (
    _update_status,
    cmd_list,
    find_item,
    load_queue,
    pending_items,
    save_queue,
    synthesize_item,
)


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------

def _make_entry(
    source_id: str = "SRC-20260412-0001",
    title: str = "Test Article",
    note_path: str = "raw/articles/test-article.md",
    review_status: str = "pending_review",
    validation_status: str = "validated",
    validation_issues: list | None = None,
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "source_note_path": note_path,
        "adapter": "browser",
        "source_type": "article",
        "origin": "web",
        "queued_at": "2026-04-12T20:00:00",
        "review_status": review_status,
        "validation_status": validation_status,
        "validation_issues": validation_issues or [],
    }


class LoadSaveQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_load_returns_empty_list_when_file_missing(self) -> None:
        import scripts.synthesize as mod
        orig = mod.REVIEW_QUEUE_PATH
        mod.REVIEW_QUEUE_PATH = self.root / "metadata" / "review-queue.json"
        try:
            self.assertEqual(load_queue(), [])
        finally:
            mod.REVIEW_QUEUE_PATH = orig

    def test_save_and_reload_roundtrip(self) -> None:
        import scripts.synthesize as mod
        orig_q = mod.REVIEW_QUEUE_PATH
        orig_r = mod.REVIEW_QUEUE_REPORT_PATH
        mod.REVIEW_QUEUE_PATH = self.root / "metadata" / "review-queue.json"
        mod.REVIEW_QUEUE_REPORT_PATH = self.root / "metadata" / "review-queue.md"
        try:
            entries = [_make_entry()]
            save_queue(entries)
            reloaded = load_queue()
            self.assertEqual(len(reloaded), 1)
            self.assertEqual(reloaded[0]["source_id"], "SRC-20260412-0001")
        finally:
            mod.REVIEW_QUEUE_PATH = orig_q
            mod.REVIEW_QUEUE_REPORT_PATH = orig_r

    def test_save_writes_markdown_report(self) -> None:
        import scripts.synthesize as mod
        orig_q = mod.REVIEW_QUEUE_PATH
        orig_r = mod.REVIEW_QUEUE_REPORT_PATH
        mod.REVIEW_QUEUE_PATH = self.root / "metadata" / "review-queue.json"
        mod.REVIEW_QUEUE_REPORT_PATH = self.root / "metadata" / "review-queue.md"
        try:
            save_queue([_make_entry(title="My Article")])
            report = (self.root / "metadata" / "review-queue.md").read_text(encoding="utf-8")
            self.assertIn("My Article", report)
            self.assertIn("# Review Queue", report)
        finally:
            mod.REVIEW_QUEUE_PATH = orig_q
            mod.REVIEW_QUEUE_REPORT_PATH = orig_r


class QueueHelperTests(unittest.TestCase):
    def test_find_item_returns_matching_entry(self) -> None:
        queue = [_make_entry("SRC-001"), _make_entry("SRC-002")]
        self.assertEqual(find_item(queue, "SRC-002")["source_id"], "SRC-002")

    def test_find_item_returns_none_when_not_found(self) -> None:
        queue = [_make_entry("SRC-001")]
        self.assertIsNone(find_item(queue, "SRC-999"))

    def test_pending_items_filters_by_review_status(self) -> None:
        queue = [
            _make_entry("SRC-001", review_status="pending_review"),
            _make_entry("SRC-002", review_status="synthesized"),
            _make_entry("SRC-003", review_status="pending_review"),
        ]
        pending = pending_items(queue)
        self.assertEqual(len(pending), 2)
        self.assertNotIn("SRC-002", [e["source_id"] for e in pending])

    def test_update_status_changes_review_status(self) -> None:
        queue = [_make_entry("SRC-001")]
        updated = _update_status(queue, "SRC-001", "synthesized")
        self.assertEqual(updated[0]["review_status"], "synthesized")

    def test_update_status_preserves_other_entries(self) -> None:
        queue = [_make_entry("SRC-001"), _make_entry("SRC-002")]
        updated = _update_status(queue, "SRC-001", "synthesized")
        other = find_item(updated, "SRC-002")
        self.assertEqual(other["review_status"], "pending_review")

    def test_update_status_merges_extra_fields(self) -> None:
        queue = [_make_entry("SRC-001")]
        updated = _update_status(queue, "SRC-001", "synthesized", {"synthesized_at": "2026-04-12T21:00:00"})
        self.assertIn("synthesized_at", updated[0])


# ---------------------------------------------------------------------------
# List command
# ---------------------------------------------------------------------------

class CmdListTests(unittest.TestCase):
    def test_list_prints_pending_items(self) -> None:
        queue = [
            _make_entry("SRC-001", title="Article One"),
            _make_entry("SRC-002", title="Article Two", review_status="synthesized"),
        ]
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = cmd_list(queue)
        output = buf.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("SRC-001", output)
        self.assertIn("Article One", output)
        self.assertNotIn("SRC-002", output)

    def test_list_reports_empty_queue(self) -> None:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = cmd_list([])
        self.assertEqual(result, 0)
        self.assertIn("No pending", buf.getvalue())

    def test_list_shows_validation_issue_count(self) -> None:
        queue = [_make_entry("SRC-001", validation_issues=["missing field: topics", "missing section"])]
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_list(queue)
        self.assertIn("2 issue", buf.getvalue())


# ---------------------------------------------------------------------------
# synthesize_item — pipeline orchestration
# ---------------------------------------------------------------------------

class SynthesizeItemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ["raw/articles", "raw/notes", "raw/pdfs", "metadata/prompts",
                  "compiled/source_summaries", "compiled/topics", "tmp"]:
            (self.root / d).mkdir(parents=True)

        (self.root / "metadata" / "source-manifest.json").write_text(
            json.dumps({"manifest_version": "0.2.0", "last_updated": "", "description": "", "sources": []}),
            encoding="utf-8",
        )
        self.note_path = self.root / "raw" / "articles" / "test-article.md"
        self.note_path.write_text(
            '---\ntitle: "Test Article"\nsource_type: "article"\norigin: "web"\n'
            'date_ingested: "2026-04-12"\nstatus: "raw"\ntopics: []\ntags: []\n'
            'author: ""\ndate_created: ""\ndate_published: ""\nlanguage: "en"\n'
            'summary: ""\nsource_id: "SRC-20260412-0001"\ncanonical_url: ""\n'
            'related_sources: []\nconfidence: ""\nlicense: ""\n---\n\n'
            "# Overview\n\nTest overview.\n\n"
            "# Source Content\n\nSome article content.\n\n"
            "# Key Points\n\n- Point one\n\n"
            "# Notes\n\n# Lineage\n\n- Ingested via: scripts/ingest.py\n",
            encoding="utf-8",
        )
        self.item = _make_entry(
            source_id="SRC-20260412-0001",
            title="Test Article",
            note_path="raw/articles/test-article.md",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_returns_false_when_source_note_missing(self) -> None:
        item = _make_entry(note_path="raw/articles/nonexistent.md")
        result = synthesize_item(
            item, title_override="", model=DEFAULT_MODEL, force=False, root=self.root
        )
        self.assertFalse(result)

    def test_scaffold_fallback_when_llm_unavailable(self) -> None:
        """When Ollama is down, synthesize_item falls back to scaffold mode."""
        import scripts.synthesize as mod
        with patch("scripts.synthesize._run_llm", return_value=None):
            result = synthesize_item(
                self.item,
                title_override="",
                model=DEFAULT_MODEL,
                force=False,
                root=self.root,
            )
        self.assertTrue(result)
        scaffold_files = list((self.root / "compiled" / "source_summaries").glob("*.md"))
        self.assertEqual(len(scaffold_files), 1)

    def test_full_pipeline_success_with_mocked_llm(self) -> None:
        """Happy path: prompt-pack generated, LLM synthesized, compiled note written."""
        fake_synthesis = (
            '---\ntitle: "Test Article"\nnote_type: "source_summary"\n'
            'compiled_from:\n  - "test-article"\ndate_compiled: "2026-04-12"\n'
            'topics: []\ntags: []\nconfidence: "medium"\ngeneration_method: "ollama_local"\n---\n\n'
            "# Summary\n\nSynthesized summary.\n\n"
            "# Key Insights\n\n- Insight one\n\n"
            "# Related Concepts\n\n- \n\n"
            "# Source Notes\n\n- [[test-article]]\n\n"
            "# Source Highlights\n\n## [[test-article]]\n- Key excerpt: Some article content.\n\n"
            "# Lineage\n\nThis note was derived from:\n- [[test-article]]"
        )
        fake_tmp = self.root / "tmp" / "synthesis-output.md"

        def fake_run_llm(prompt_pack_path, model, force, root):
            fake_tmp.write_text(fake_synthesis, encoding="utf-8")
            return fake_tmp

        import scripts.synthesize as mod
        with patch("scripts.synthesize._run_llm", side_effect=fake_run_llm):
            result = synthesize_item(
                self.item,
                title_override="",
                model=DEFAULT_MODEL,
                force=False,
                root=self.root,
            )
        self.assertTrue(result)
        compiled_files = list((self.root / "compiled" / "source_summaries").glob("*.md"))
        self.assertEqual(len(compiled_files), 1)
        content = compiled_files[0].read_text(encoding="utf-8")
        self.assertIn("Synthesized summary", content)

    def test_prompt_pack_written_to_metadata_prompts(self) -> None:
        import scripts.synthesize as mod
        with patch("scripts.synthesize._run_llm", return_value=None):
            synthesize_item(
                self.item,
                title_override="",
                model=DEFAULT_MODEL,
                force=False,
                root=self.root,
            )
        prompt_files = list((self.root / "metadata" / "prompts").glob("*.md"))
        self.assertEqual(len(prompt_files), 1)
        self.assertIn("test-article", prompt_files[0].name)
        self.assertIn("synthesis", prompt_files[0].name)

    def test_compiled_slug_differs_from_raw_note_slug(self) -> None:
        """Compiled note must have a distinct filename from its source raw note."""
        with patch("scripts.synthesize._run_llm", return_value=None):
            synthesize_item(
                self.item,
                title_override="",
                model=DEFAULT_MODEL,
                force=False,
                root=self.root,
            )
        compiled_files = list((self.root / "compiled" / "source_summaries").glob("*.md"))
        self.assertEqual(len(compiled_files), 1)
        compiled_stem = compiled_files[0].stem
        raw_stem = self.note_path.stem
        self.assertNotEqual(compiled_stem, raw_stem)
        self.assertIn("synthesis", compiled_stem)


DEFAULT_MODEL = "qwen2.5:14b"

if __name__ == "__main__":
    unittest.main()

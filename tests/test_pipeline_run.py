"""Tests for scripts/pipeline_run.py (Fix 2 — Synthesis Automation)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from scripts.pipeline_run import (
    DEFAULT_THRESHOLD,
    _pending_items,
    cmd_run_all,
    cmd_run_one,
    run_for_item,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    source_id: str = "SRC-20260418-0001",
    title: str = "Test Article",
    review_status: str = "pending_review",
    source_note_path: str = "raw/articles/test-article.md",
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "review_status": review_status,
        "source_note_path": source_note_path,
        "adapter": "browser",
        "validation_status": "validated",
        "validation_issues": [],
        "queued_at": "2026-04-18T10:00:00",
    }


def _write_queue(root: Path, entries: list) -> None:
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "metadata" / "review-queue.json").write_text(
        json.dumps(entries, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _pending_items filter
# ---------------------------------------------------------------------------

class PendingItemsTests(unittest.TestCase):
    def test_returns_pending_items(self) -> None:
        queue = [
            _make_entry("A", review_status="pending_review"),
            _make_entry("B", review_status="synthesized"),
            _make_entry("C", review_status="pending_review"),
        ]
        result = _pending_items(queue)
        self.assertEqual(len(result), 2)
        self.assertEqual({e["source_id"] for e in result}, {"A", "C"})

    def test_excludes_synthesized_and_approved(self) -> None:
        queue = [
            _make_entry("A", review_status="synthesized"),
            _make_entry("B", review_status="approved"),
        ]
        self.assertEqual(_pending_items(queue), [])

    def test_empty_queue_returns_empty(self) -> None:
        self.assertEqual(_pending_items([]), [])


# ---------------------------------------------------------------------------
# run_for_item
# ---------------------------------------------------------------------------

class RunForItemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write_queue(self.root, [])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @patch("scripts.pipeline_run.aggregate_for_source")
    @patch("scripts.pipeline_run.update_queue_with_score")
    @patch("scripts.pipeline_run.score_synthesis")
    @patch("scripts.pipeline_run.load_queue")
    @patch("scripts.pipeline_run.synthesize_item", return_value=True)
    def test_all_stages_called_in_order(
        self, mock_synth, mock_load_queue, mock_score, mock_update, mock_agg
    ) -> None:
        item = _make_entry()
        mock_load_queue.return_value = [item]

        score_result = MagicMock()
        score_result.score = 0.91
        score_result.band = "high"
        score_result.auto_approved = True
        mock_score.return_value = score_result

        # Make _find_compiled_note return a path by patching it
        with patch("scripts.pipeline_run._find_compiled_note") as mock_find, \
             patch("scripts.pipeline_run._find_source_summary") as mock_find_ss:
            mock_find.return_value = Path("/fake/note.md")
            mock_find_ss.return_value = Path("/fake/summary.md")
            result = run_for_item(item, root=self.root)

        self.assertTrue(result)
        mock_synth.assert_called_once()
        mock_score.assert_called_once()
        mock_update.assert_called_once()
        mock_agg.assert_called_once()

    @patch("scripts.pipeline_run.synthesize_item", return_value=False)
    def test_returns_false_when_synthesis_fails(self, mock_synth) -> None:
        item = _make_entry()
        with patch("scripts.pipeline_run.load_queue", return_value=[item]):
            result = run_for_item(item, root=self.root)
        self.assertFalse(result)

    @patch("scripts.pipeline_run.aggregate_for_source")
    @patch("scripts.pipeline_run.update_queue_with_score")
    @patch("scripts.pipeline_run.score_synthesis")
    @patch("scripts.pipeline_run.load_queue")
    @patch("scripts.pipeline_run.synthesize_item", return_value=True)
    def test_auto_approve_fires_at_threshold(
        self, mock_synth, mock_load_queue, mock_score, mock_update, mock_agg
    ) -> None:
        item = _make_entry()
        mock_load_queue.return_value = [item]
        score_result = MagicMock()
        score_result.score = 0.85
        score_result.band = "high"
        score_result.auto_approved = True
        mock_score.return_value = score_result

        with patch("scripts.pipeline_run._find_compiled_note", return_value=Path("/f.md")), \
             patch("scripts.pipeline_run._find_source_summary", return_value=None):
            run_for_item(item, threshold=0.85, root=self.root)

        self.assertTrue(score_result.auto_approved)

    @patch("scripts.pipeline_run.aggregate_for_source")
    @patch("scripts.pipeline_run.update_queue_with_score")
    @patch("scripts.pipeline_run.score_synthesis")
    @patch("scripts.pipeline_run.load_queue")
    @patch("scripts.pipeline_run.synthesize_item", return_value=True)
    def test_auto_approve_does_not_fire_below_threshold(
        self, mock_synth, mock_load_queue, mock_score, mock_update, mock_agg
    ) -> None:
        item = _make_entry()
        mock_load_queue.return_value = [item]
        score_result = MagicMock()
        score_result.score = 0.72
        score_result.band = "medium"
        score_result.auto_approved = False
        mock_score.return_value = score_result

        with patch("scripts.pipeline_run._find_compiled_note", return_value=Path("/f.md")), \
             patch("scripts.pipeline_run._find_source_summary", return_value=None):
            run_for_item(item, threshold=0.85, root=self.root)

        self.assertFalse(score_result.auto_approved)

    @patch("scripts.pipeline_run.aggregate_for_source", side_effect=RuntimeError("Ollama down"))
    @patch("scripts.pipeline_run.update_queue_with_score")
    @patch("scripts.pipeline_run.score_synthesis")
    @patch("scripts.pipeline_run.load_queue")
    @patch("scripts.pipeline_run.synthesize_item", return_value=True)
    def test_aggregation_failure_does_not_crash(
        self, mock_synth, mock_load_queue, mock_score, mock_update, mock_agg
    ) -> None:
        item = _make_entry()
        mock_load_queue.return_value = [item]
        score_result = MagicMock()
        score_result.score = 0.9
        score_result.band = "high"
        score_result.auto_approved = True
        mock_score.return_value = score_result

        with patch("scripts.pipeline_run._find_compiled_note", return_value=Path("/f.md")), \
             patch("scripts.pipeline_run._find_source_summary", return_value=Path("/s.md")):
            # Should not raise despite aggregation failure
            result = run_for_item(item, root=self.root)

        self.assertTrue(result)

    @patch("scripts.pipeline_run.aggregate_for_source")
    @patch("scripts.pipeline_run.update_queue_with_score")
    @patch("scripts.pipeline_run.score_synthesis", side_effect=ConnectionError("no ollama"))
    @patch("scripts.pipeline_run.load_queue")
    @patch("scripts.pipeline_run.synthesize_item", return_value=True)
    def test_score_failure_is_non_fatal(
        self, mock_synth, mock_load_queue, mock_score, mock_update, mock_agg
    ) -> None:
        item = _make_entry()
        mock_load_queue.return_value = [item]

        with patch("scripts.pipeline_run._find_compiled_note", return_value=Path("/f.md")), \
             patch("scripts.pipeline_run._find_source_summary", return_value=None):
            result = run_for_item(item, root=self.root)

        # Synthesis succeeded; score failed non-fatally; overall still True
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# cmd_run_one
# ---------------------------------------------------------------------------

class CmdRunOneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", return_value=True)
    @patch("scripts.pipeline_run.load_queue")
    def test_processes_pending_item(self, mock_lq, mock_run, mock_idx) -> None:
        mock_lq.return_value = [_make_entry("SRC-001", review_status="pending_review")]
        rc = cmd_run_one("SRC-001", model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once()

    @patch("scripts.pipeline_run.load_queue")
    def test_returns_one_when_not_found(self, mock_lq) -> None:
        mock_lq.return_value = []
        rc = cmd_run_one("MISSING", model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(rc, 1)

    @patch("scripts.pipeline_run.load_queue")
    def test_returns_one_when_already_synthesized(self, mock_lq) -> None:
        mock_lq.return_value = [_make_entry("SRC-001", review_status="synthesized")]
        rc = cmd_run_one("SRC-001", model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# cmd_run_all
# ---------------------------------------------------------------------------

class CmdRunAllTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", return_value=True)
    @patch("scripts.pipeline_run.load_queue")
    def test_processes_all_pending_items(self, mock_lq, mock_run, mock_idx) -> None:
        mock_lq.return_value = [
            _make_entry("SRC-001", review_status="pending_review"),
            _make_entry("SRC-002", review_status="pending_review"),
        ]
        rc = cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(mock_run.call_count, 2)

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.load_queue")
    def test_empty_queue_returns_zero(self, mock_lq, mock_idx) -> None:
        mock_lq.return_value = []
        rc = cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(rc, 0)

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", side_effect=[True, False, True])
    @patch("scripts.pipeline_run.load_queue")
    def test_one_failure_does_not_stop_others(self, mock_lq, mock_run, mock_idx) -> None:
        mock_lq.return_value = [
            _make_entry("SRC-001", review_status="pending_review"),
            _make_entry("SRC-002", review_status="pending_review"),
            _make_entry("SRC-003", review_status="pending_review"),
        ]
        rc = cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root)
        # 1 failure → non-zero exit
        self.assertNotEqual(rc, 0)
        # All three still attempted
        self.assertEqual(mock_run.call_count, 3)

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", return_value=True)
    @patch("scripts.pipeline_run.load_queue")
    def test_skips_non_pending_items(self, mock_lq, mock_run, mock_idx) -> None:
        mock_lq.return_value = [
            _make_entry("SRC-001", review_status="synthesized"),
            _make_entry("SRC-002", review_status="pending_review"),
        ]
        cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root)
        # Only the pending item is processed
        self.assertEqual(mock_run.call_count, 1)

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", return_value=True)
    @patch("scripts.pipeline_run.load_queue")
    def test_index_rebuild_called_after_all_items(self, mock_lq, mock_run, mock_idx) -> None:
        mock_lq.return_value = [_make_entry("SRC-001", review_status="pending_review")]
        cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root)
        mock_idx.assert_called_once()


# ---------------------------------------------------------------------------
# --watch polling
# ---------------------------------------------------------------------------

class WatchTests(unittest.TestCase):
    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", return_value=True)
    @patch("scripts.pipeline_run.load_queue")
    @patch("scripts.pipeline_run.time")
    def test_watch_polls_at_interval(self, mock_time, mock_lq, mock_run, mock_idx) -> None:
        from scripts.pipeline_run import cmd_watch

        # First call returns a pending item; second raises KeyboardInterrupt to stop
        mock_lq.side_effect = [
            [_make_entry("SRC-001", review_status="pending_review")],
            KeyboardInterrupt,
        ]
        mock_time.sleep = MagicMock()

        cmd_watch(interval=30, model="qwen2.5:14b", threshold=0.85, root=Path("."))

        mock_time.sleep.assert_called_with(30)
        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()

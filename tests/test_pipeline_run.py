"""Tests for scripts/pipeline_run.py (Fix 2 — Synthesis Automation)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from scripts.pipeline_run import (
    DEFAULT_THRESHOLD,
    _domain_for_item,
    _domain_slugs_for_arg,
    _domains_for_items,
    _is_aggregated,
    _pending_items,
    _processable_items,
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
    domain: str = "",
) -> dict:
    entry = {
        "source_id": source_id,
        "title": title,
        "review_status": review_status,
        "source_note_path": source_note_path,
        "adapter": "browser",
        "validation_status": "validated",
        "validation_issues": [],
        "queued_at": "2026-04-18T10:00:00",
    }
    if domain:
        entry["domain"] = domain
    return entry


def _write_queue(root: Path, entries: list) -> None:
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "metadata" / "review-queue.json").write_text(
        json.dumps(entries, indent=2) + "\n", encoding="utf-8"
    )


def _write_domains(root: Path, slugs: list[str]) -> None:
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "default_domain": "ai",
        "domains": [
            {
                "display_name": slug.upper(),
                "slug": slug,
                "description": "",
                "created_at": "2026-04-18T10:00:00+00:00",
                "active": True,
            }
            for slug in slugs
        ],
    }
    (root / "metadata" / "domains.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
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

    def test_processable_includes_pending_and_approved_actions(self) -> None:
        approved = _make_entry("B", review_status="synthesized")
        approved["review_action"] = "approved"
        queue = [
            _make_entry("A", review_status="pending_review"),
            approved,
            _make_entry("C", review_status="synthesized"),
        ]
        self.assertEqual([e["source_id"] for e in _processable_items(queue)], ["A", "B"])

    def test_processable_excludes_approved_item_already_in_topic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topics = root / "compiled" / "domains" / "ai" / "topics"
            topics.mkdir(parents=True)
            topics.joinpath("test-topic.md").write_text(
                "---\ncompiled_from:\n  - \"test-article-synthesis\"\napproved: true\n---\n",
                encoding="utf-8",
            )
            approved = _make_entry("B", review_status="synthesized")
            approved["review_action"] = "approved"

            self.assertTrue(_is_aggregated(approved, root))
            self.assertEqual(_processable_items([approved], root=root), [])

    def test_empty_queue_returns_empty(self) -> None:
        self.assertEqual(_pending_items([]), [])

    def test_domain_defaults_to_ai_for_legacy_queue_items(self) -> None:
        self.assertEqual(_domain_for_item(_make_entry()), "ai")

    def test_domains_for_items_are_unique_in_order(self) -> None:
        queue = [
            _make_entry("A", domain="ai"),
            _make_entry("B", domain="civil-war-history"),
            _make_entry("C", domain="ai"),
            _make_entry("D"),
        ]
        self.assertEqual(_domains_for_items(queue), ["ai", "civil-war-history"])

    def test_all_domain_arg_loads_active_domain_slugs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_domains(root, ["ai", "aws"])
            self.assertEqual(_domain_slugs_for_arg("all", root), ["ai", "aws"])


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
    @patch("scripts.pipeline_run.run_score_synthesis")
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
            mock_find_ss.side_effect = [None, Path("/fake/summary.md")]
            result = run_for_item(item, root=self.root)

        self.assertTrue(result)
        mock_synth.assert_called_once()
        mock_score.assert_called_once()
        mock_update.assert_called_once()
        mock_agg.assert_called_once()

    @patch("scripts.pipeline_run.extract_concepts")
    @patch("scripts.pipeline_run.aggregate_for_source")
    @patch("scripts.pipeline_run.run_score_synthesis")
    @patch("scripts.pipeline_run.load_queue")
    @patch("scripts.pipeline_run.synthesize_item")
    def test_approved_existing_summary_skips_synthesis_and_score(
        self, mock_synth, mock_load_queue, mock_score, mock_agg, mock_extract
    ) -> None:
        item = _make_entry(review_status="synthesized")
        item["review_action"] = "approved"
        mock_load_queue.return_value = [item]
        mock_extract.return_value = {"concepts_written": [], "entities_written": []}

        with patch("scripts.pipeline_run._find_compiled_note", return_value=Path("/f.md")), \
             patch("scripts.pipeline_run._find_source_summary", return_value=Path("/s.md")), \
             patch("scripts.pipeline_run._patch_note_approved") as mock_patch:
            result = run_for_item(item, root=self.root)

        self.assertTrue(result)
        mock_synth.assert_not_called()
        mock_score.assert_not_called()
        mock_patch.assert_called_once_with(Path("/f.md"), approved=True)
        mock_agg.assert_called_once()

    @patch("scripts.pipeline_run.synthesize_item", return_value=False)
    def test_returns_false_when_synthesis_fails(self, mock_synth) -> None:
        item = _make_entry()
        with patch("scripts.pipeline_run.load_queue", return_value=[item]):
            result = run_for_item(item, root=self.root)
        self.assertFalse(result)

    @patch("scripts.pipeline_run.aggregate_for_source")
    @patch("scripts.pipeline_run.update_queue_with_score")
    @patch("scripts.pipeline_run.run_score_synthesis")
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
    @patch("scripts.pipeline_run.run_score_synthesis")
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
    @patch("scripts.pipeline_run.run_score_synthesis")
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
    @patch("scripts.pipeline_run.run_score_synthesis", side_effect=ConnectionError("no ollama"))
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
        mock_idx.assert_called_once_with(self.root, no_commit=False, domain="ai")

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

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", return_value=True)
    @patch("scripts.pipeline_run.load_queue")
    def test_processes_approved_item(self, mock_lq, mock_run, mock_idx) -> None:
        item = _make_entry("SRC-001", review_status="synthesized")
        item["review_action"] = "approved"
        mock_lq.return_value = [item]
        rc = cmd_run_one("SRC-001", model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(rc, 0)
        mock_run.assert_called_once()
        mock_idx.assert_called_once_with(self.root, no_commit=False, domain="ai")


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
            _make_entry("SRC-001", review_status="pending_review", domain="ai"),
            _make_entry("SRC-002", review_status="pending_review", domain="civil-war-history"),
        ]
        rc = cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(mock_run.call_count, 2)
        mock_idx.assert_has_calls([
            call(self.root, no_commit=False, domain="ai"),
            call(self.root, no_commit=False, domain="civil-war-history"),
        ])

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
    def test_processes_pending_and_approved_items(self, mock_lq, mock_run, mock_idx) -> None:
        approved = _make_entry("SRC-003", review_status="synthesized")
        approved["review_action"] = "approved"
        mock_lq.return_value = [
            _make_entry("SRC-001", review_status="synthesized"),
            _make_entry("SRC-002", review_status="pending_review"),
            approved,
        ]
        cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root)
        self.assertEqual(mock_run.call_count, 2)

    @patch("scripts.pipeline_run.run_index_rebuild")
    @patch("scripts.pipeline_run.run_for_item", return_value=True)
    def test_all_domain_processes_each_domain_queue(self, mock_run, mock_idx) -> None:
        _write_domains(self.root, ["ai", "aws"])
        ai_queue = self.root / "metadata" / "domains" / "ai" / "review-queue.json"
        aws_queue = self.root / "metadata" / "domains" / "aws" / "review-queue.json"
        ai_queue.parent.mkdir(parents=True, exist_ok=True)
        aws_queue.parent.mkdir(parents=True, exist_ok=True)
        ai_queue.write_text(
            json.dumps([_make_entry("SRC-AI", review_status="pending_review", domain="ai")]),
            encoding="utf-8",
        )
        aws_queue.write_text(
            json.dumps([_make_entry("SRC-AWS", review_status="pending_review", domain="aws")]),
            encoding="utf-8",
        )

        rc = cmd_run_all(model="qwen2.5:14b", threshold=0.85, root=self.root, domain="all")

        self.assertEqual(rc, 0)
        self.assertEqual(
            [call_args.args[0]["source_id"] for call_args in mock_run.call_args_list],
            ["SRC-AI", "SRC-AWS"],
        )
        mock_idx.assert_has_calls([
            call(self.root, no_commit=False, domain="ai"),
            call(self.root, no_commit=False, domain="aws"),
        ])

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

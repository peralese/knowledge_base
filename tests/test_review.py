"""Tests for scripts/review.py (Phase 4)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.review import (
    _reviewable_items,
    _write_queue_report,
    approve,
    approve_all_high_confidence,
    list_pending_review,
    load_queue,
    reject,
    save_queue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    source_id: str = "SRC-20260412-0001",
    title: str = "Test Article",
    review_status: str = "synthesized",
    confidence_score: float | None = None,
    confidence_band: str | None = None,
    review_action: str | None = None,
) -> dict:
    entry: dict = {
        "source_id": source_id,
        "title": title,
        "source_note_path": f"raw/articles/{source_id.lower()}.md",
        "adapter": "browser",
        "source_type": "article",
        "origin": "web",
        "queued_at": "2026-04-15T10:00:00",
        "review_status": review_status,
        "validation_status": "validated",
        "validation_issues": [],
        "review_action": review_action,
        "review_method": None,
        "reviewed_at": None,
    }
    if confidence_score is not None:
        entry["confidence_score"] = confidence_score
        entry["confidence_band"] = confidence_band or _band(confidence_score)
        entry["confidence_reasoning"] = "Test reasoning."
        entry["scored_at"] = "2026-04-15T10:01:00"
    return entry


def _band(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# ApproveTests
# ---------------------------------------------------------------------------

class ApproveTests(unittest.TestCase):
    def test_approve_sets_review_action(self) -> None:
        queue = [_make_entry()]
        updated, found = approve(queue, "SRC-20260412-0001")
        self.assertTrue(found)
        self.assertEqual(updated[0]["review_action"], "approved")

    def test_approve_sets_manual_method_by_default(self) -> None:
        queue = [_make_entry()]
        updated, _ = approve(queue, "SRC-20260412-0001")
        self.assertEqual(updated[0]["review_method"], "manual")

    def test_approve_sets_reviewed_at_timestamp(self) -> None:
        queue = [_make_entry()]
        updated, _ = approve(queue, "SRC-20260412-0001")
        self.assertIsNotNone(updated[0]["reviewed_at"])

    def test_approve_returns_false_when_not_found(self) -> None:
        queue = [_make_entry("SRC-001")]
        _, found = approve(queue, "SRC-999")
        self.assertFalse(found)

    def test_approve_does_not_mutate_other_entries(self) -> None:
        queue = [_make_entry("SRC-001"), _make_entry("SRC-002")]
        updated, _ = approve(queue, "SRC-001")
        self.assertIsNone(updated[1]["review_action"])

    def test_approve_original_queue_not_mutated(self) -> None:
        queue = [_make_entry()]
        approve(queue, "SRC-20260412-0001")
        self.assertIsNone(queue[0]["review_action"])

    def test_approve_custom_method(self) -> None:
        queue = [_make_entry()]
        updated, _ = approve(queue, "SRC-20260412-0001", method="auto")
        self.assertEqual(updated[0]["review_method"], "auto")


# ---------------------------------------------------------------------------
# RejectTests
# ---------------------------------------------------------------------------

class RejectTests(unittest.TestCase):
    def test_reject_sets_review_action(self) -> None:
        queue = [_make_entry()]
        updated, found = reject(queue, "SRC-20260412-0001")
        self.assertTrue(found)
        self.assertEqual(updated[0]["review_action"], "rejected")

    def test_reject_sets_manual_method(self) -> None:
        queue = [_make_entry()]
        updated, _ = reject(queue, "SRC-20260412-0001")
        self.assertEqual(updated[0]["review_method"], "manual")

    def test_reject_stores_reason(self) -> None:
        queue = [_make_entry()]
        updated, _ = reject(queue, "SRC-20260412-0001", reason="off-topic")
        self.assertEqual(updated[0]["rejection_reason"], "off-topic")

    def test_reject_no_reason_omits_rejection_reason_key(self) -> None:
        queue = [_make_entry()]
        updated, _ = reject(queue, "SRC-20260412-0001", reason="")
        self.assertNotIn("rejection_reason", updated[0])

    def test_reject_returns_false_when_not_found(self) -> None:
        queue = [_make_entry("SRC-001")]
        _, found = reject(queue, "SRC-999")
        self.assertFalse(found)

    def test_reject_sets_reviewed_at_timestamp(self) -> None:
        queue = [_make_entry()]
        updated, _ = reject(queue, "SRC-20260412-0001")
        self.assertIsNotNone(updated[0]["reviewed_at"])

    def test_reject_does_not_mutate_original(self) -> None:
        queue = [_make_entry()]
        reject(queue, "SRC-20260412-0001")
        self.assertIsNone(queue[0]["review_action"])


# ---------------------------------------------------------------------------
# ApproveAllHighConfidenceTests
# ---------------------------------------------------------------------------

class ApproveAllHighConfidenceTests(unittest.TestCase):
    def test_approves_items_at_or_above_threshold(self) -> None:
        queue = [
            _make_entry("SRC-001", confidence_score=0.91),
            _make_entry("SRC-002", confidence_score=0.85),
            _make_entry("SRC-003", confidence_score=0.84),
        ]
        updated, count = approve_all_high_confidence(queue, threshold=0.85)
        self.assertEqual(count, 2)
        self.assertEqual(updated[0]["review_action"], "approved")
        self.assertEqual(updated[1]["review_action"], "approved")
        self.assertIsNone(updated[2]["review_action"])

    def test_skips_already_reviewed_items(self) -> None:
        queue = [
            _make_entry("SRC-001", confidence_score=0.91, review_action="approved"),
            _make_entry("SRC-002", confidence_score=0.91),
        ]
        updated, count = approve_all_high_confidence(queue, threshold=0.85)
        self.assertEqual(count, 1)

    def test_skips_unscored_items(self) -> None:
        queue = [_make_entry("SRC-001")]  # no confidence_score
        updated, count = approve_all_high_confidence(queue, threshold=0.85)
        self.assertEqual(count, 0)

    def test_skips_non_synthesized_items(self) -> None:
        queue = [_make_entry("SRC-001", review_status="pending_review", confidence_score=0.91)]
        updated, count = approve_all_high_confidence(queue, threshold=0.85)
        self.assertEqual(count, 0)

    def test_returns_zero_count_when_nothing_qualifies(self) -> None:
        queue = [_make_entry("SRC-001", confidence_score=0.50)]
        _, count = approve_all_high_confidence(queue, threshold=0.85)
        self.assertEqual(count, 0)

    def test_custom_threshold_respected(self) -> None:
        queue = [_make_entry("SRC-001", confidence_score=0.75)]
        _, count = approve_all_high_confidence(queue, threshold=0.70)
        self.assertEqual(count, 1)


# ---------------------------------------------------------------------------
# ReviewableItemsTests
# ---------------------------------------------------------------------------

class ReviewableItemsTests(unittest.TestCase):
    def test_excludes_pending_review_items(self) -> None:
        queue = [
            _make_entry("SRC-001", review_status="pending_review"),
            _make_entry("SRC-002", review_status="synthesized"),
        ]
        result = _reviewable_items(queue)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_id"], "SRC-002")

    def test_excludes_already_approved(self) -> None:
        queue = [
            _make_entry("SRC-001", review_action="approved"),
            _make_entry("SRC-002"),
        ]
        result = _reviewable_items(queue)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_id"], "SRC-002")

    def test_excludes_already_rejected(self) -> None:
        queue = [
            _make_entry("SRC-001", review_action="rejected"),
            _make_entry("SRC-002"),
        ]
        result = _reviewable_items(queue)
        self.assertEqual(len(result), 1)

    def test_sorted_low_confidence_first(self) -> None:
        queue = [
            _make_entry("SRC-001", confidence_score=0.91, confidence_band="high"),
            _make_entry("SRC-002", confidence_score=0.40, confidence_band="low"),
            _make_entry("SRC-003", confidence_score=0.70, confidence_band="medium"),
        ]
        result = _reviewable_items(queue)
        self.assertEqual(result[0]["source_id"], "SRC-002")
        self.assertEqual(result[1]["source_id"], "SRC-003")
        self.assertEqual(result[2]["source_id"], "SRC-001")

    def test_empty_queue_returns_empty(self) -> None:
        self.assertEqual(_reviewable_items([]), [])


# ---------------------------------------------------------------------------
# ListPendingReviewTests
# ---------------------------------------------------------------------------

class ListPendingReviewTests(unittest.TestCase):
    def test_returns_zero_with_items(self) -> None:
        queue = [_make_entry()]
        self.assertEqual(list_pending_review(queue), 0)

    def test_returns_zero_with_empty_queue(self) -> None:
        self.assertEqual(list_pending_review([]), 0)


# ---------------------------------------------------------------------------
# LoadSaveQueueTests
# ---------------------------------------------------------------------------

class LoadSaveQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)
        self.queue_path = self.root / "metadata" / "review-queue.json"
        self.report_path = self.root / "metadata" / "review-queue.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _patch(self):
        import scripts.review as mod
        return (
            patch.object(mod, "REVIEW_QUEUE_PATH", self.queue_path),
            patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path),
        )

    def test_load_returns_empty_when_file_missing(self) -> None:
        import scripts.review as mod
        with patch.object(mod, "REVIEW_QUEUE_PATH", self.queue_path):
            self.assertEqual(load_queue(), [])

    def test_save_and_reload_roundtrip(self) -> None:
        entries = [_make_entry()]
        p1, p2 = self._patch()
        with p1, p2:
            save_queue(entries)
            reloaded = load_queue()
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0]["source_id"], "SRC-20260412-0001")

    def test_save_writes_markdown_report(self) -> None:
        p1, p2 = self._patch()
        with p1, p2:
            save_queue([_make_entry(title="My Article")])
        report = self.report_path.read_text(encoding="utf-8")
        self.assertIn("My Article", report)
        self.assertIn("Confidence", report)

    def test_approve_then_save_persists(self) -> None:
        entries = [_make_entry()]
        self.queue_path.write_text(json.dumps(entries) + "\n", encoding="utf-8")

        p1, p2 = self._patch()
        with p1, p2:
            queue = load_queue()
            updated, _ = approve(queue, "SRC-20260412-0001")
            save_queue(updated)
            reloaded = load_queue()

        self.assertEqual(reloaded[0]["review_action"], "approved")


# ---------------------------------------------------------------------------
# QueueReportTests
# ---------------------------------------------------------------------------

class QueueReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)
        self.report_path = self.root / "metadata" / "review-queue.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_report_shows_confidence_column(self) -> None:
        import scripts.review as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([_make_entry(confidence_score=0.85)])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("Confidence", content)
        self.assertIn("0.85", content)

    def test_report_shows_dash_for_unscored(self) -> None:
        import scripts.review as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([_make_entry()])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("—", content)

    def test_empty_queue_report(self) -> None:
        import scripts.review as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("No items in queue", content)

    def test_approved_action_shown_in_report(self) -> None:
        import scripts.review as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([_make_entry(confidence_score=0.91, review_action="approved")])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("approved", content)


if __name__ == "__main__":
    unittest.main()

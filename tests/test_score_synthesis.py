"""Tests for scripts/score_synthesis.py (Phase 4)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.score_synthesis import (
    ScoreRequest,
    ScoreResult,
    _build_critique_prompt,
    _find_compiled_note,
    _parse_score_response,
    _patch_note_with_score,
    _set_frontmatter_field,
    _synthesized_unscored,
    _write_queue_report,
    band_from_score,
    load_queue,
    save_queue,
    score_synthesis,
    update_entry_with_score,
    update_queue_with_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    source_id: str = "SRC-20260412-0001",
    title: str = "Test Article",
    note_path: str = "raw/articles/test-article.md",
    review_status: str = "synthesized",
    confidence_score: float | None = None,
    review_action: str | None = None,
) -> dict:
    entry: dict = {
        "source_id": source_id,
        "title": title,
        "source_note_path": note_path,
        "adapter": "browser",
        "source_type": "article",
        "origin": "web",
        "queued_at": "2026-04-15T10:00:00",
        "review_status": review_status,
        "validation_status": "validated",
        "validation_issues": [],
    }
    if confidence_score is not None:
        entry["confidence_score"] = confidence_score
        entry["confidence_band"] = band_from_score(confidence_score)
        entry["confidence_reasoning"] = "Test reasoning."
        entry["scored_at"] = "2026-04-15T10:01:00"
        entry["review_action"] = review_action
        entry["review_method"] = "auto" if review_action == "approved" else None
        entry["reviewed_at"] = "2026-04-15T10:01:00" if review_action else None
    return entry


def _make_result(
    source_id: str = "SRC-20260412-0001",
    score: float = 0.91,
    auto_approved: bool = True,
) -> ScoreResult:
    band = band_from_score(score)
    return ScoreResult(
        source_id=source_id,
        score=score,
        band=band,
        reasoning="The synthesis captures all key points clearly.",
        auto_approved=auto_approved,
    )


# ---------------------------------------------------------------------------
# BandFromScoreTests
# ---------------------------------------------------------------------------

class BandFromScoreTests(unittest.TestCase):
    def test_score_at_threshold_is_high(self) -> None:
        self.assertEqual(band_from_score(0.85), "high")

    def test_score_above_threshold_is_high(self) -> None:
        self.assertEqual(band_from_score(1.0), "high")
        self.assertEqual(band_from_score(0.91), "high")

    def test_score_just_below_threshold_is_medium(self) -> None:
        self.assertEqual(band_from_score(0.84), "medium")

    def test_score_at_medium_floor_is_medium(self) -> None:
        self.assertEqual(band_from_score(0.65), "medium")

    def test_score_just_below_medium_floor_is_low(self) -> None:
        self.assertEqual(band_from_score(0.64), "low")

    def test_score_zero_is_low(self) -> None:
        self.assertEqual(band_from_score(0.0), "low")

    def test_custom_threshold_respected(self) -> None:
        self.assertEqual(band_from_score(0.75, threshold=0.70), "high")
        self.assertEqual(band_from_score(0.69, threshold=0.70), "medium")


# ---------------------------------------------------------------------------
# ParseScoreResponseTests
# ---------------------------------------------------------------------------

class ParseScoreResponseTests(unittest.TestCase):
    def test_valid_json_parsed(self) -> None:
        raw = '{"score": 0.87, "reasoning": "Well written."}'
        score, reasoning = _parse_score_response(raw)
        self.assertAlmostEqual(score, 0.87)
        self.assertEqual(reasoning, "Well written.")

    def test_json_embedded_in_prose(self) -> None:
        raw = 'Here is my evaluation:\n{"score": 0.72, "reasoning": "Good but incomplete."}\nDone.'
        score, reasoning = _parse_score_response(raw)
        self.assertAlmostEqual(score, 0.72)
        self.assertEqual(reasoning, "Good but incomplete.")

    def test_malformed_json_falls_back(self) -> None:
        score, reasoning = _parse_score_response("not json at all")
        self.assertAlmostEqual(score, 0.5)
        self.assertEqual(reasoning, "Score parse failed")

    def test_missing_reasoning_falls_back(self) -> None:
        raw = '{"score": 0.80}'
        score, reasoning = _parse_score_response(raw)
        self.assertAlmostEqual(score, 0.5)
        self.assertEqual(reasoning, "Score parse failed")

    def test_score_out_of_range_falls_back(self) -> None:
        raw = '{"score": 1.5, "reasoning": "Too high."}'
        score, reasoning = _parse_score_response(raw)
        self.assertAlmostEqual(score, 0.5)
        self.assertEqual(reasoning, "Score parse failed")

    def test_score_negative_falls_back(self) -> None:
        raw = '{"score": -0.1, "reasoning": "Negative."}'
        score, reasoning = _parse_score_response(raw)
        self.assertAlmostEqual(score, 0.5)
        self.assertEqual(reasoning, "Score parse failed")

    def test_score_exactly_zero_is_valid(self) -> None:
        raw = '{"score": 0.0, "reasoning": "No useful content."}'
        score, reasoning = _parse_score_response(raw)
        self.assertAlmostEqual(score, 0.0)
        self.assertEqual(reasoning, "No useful content.")

    def test_score_exactly_one_is_valid(self) -> None:
        raw = '{"score": 1.0, "reasoning": "Perfect synthesis."}'
        score, reasoning = _parse_score_response(raw)
        self.assertAlmostEqual(score, 1.0)


# ---------------------------------------------------------------------------
# BuildCritiquePromptTests
# ---------------------------------------------------------------------------

class BuildCritiquePromptTests(unittest.TestCase):
    def test_note_text_appears_in_prompt(self) -> None:
        prompt = _build_critique_prompt("My synthesis content.")
        self.assertIn("My synthesis content.", prompt)

    def test_json_format_instruction_present(self) -> None:
        prompt = _build_critique_prompt("content")
        self.assertIn('"score"', prompt)
        self.assertIn('"reasoning"', prompt)

    def test_criteria_present(self) -> None:
        prompt = _build_critique_prompt("content")
        self.assertIn("Accuracy", prompt)
        self.assertIn("Completeness", prompt)
        self.assertIn("Clarity", prompt)


# ---------------------------------------------------------------------------
# ScoreSynthesisTests
# ---------------------------------------------------------------------------

class ScoreSynthesisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        compiled_dir = self.root / "compiled" / "source_summaries"
        compiled_dir.mkdir(parents=True)
        self.note_path = compiled_dir / "test-article-synthesis.md"
        self.note_path.write_text("# Test Synthesis\n\nSome content.", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_request(self, score: float = 0.91) -> ScoreRequest:
        return ScoreRequest(
            source_id="SRC-20260412-0001",
            compiled_note_path=self.note_path,
            root=self.root,
        )

    @patch("scripts.score_synthesis.call_ollama")
    @patch("scripts.score_synthesis._check_model_available")
    def test_high_score_auto_approves(self, mock_check: MagicMock, mock_ollama: MagicMock) -> None:
        mock_check.return_value = None
        mock_ollama.return_value = '{"score": 0.92, "reasoning": "Excellent synthesis."}'
        result = score_synthesis(self._make_request())
        self.assertAlmostEqual(result.score, 0.92)
        self.assertEqual(result.band, "high")
        self.assertTrue(result.auto_approved)

    @patch("scripts.score_synthesis.call_ollama")
    @patch("scripts.score_synthesis._check_model_available")
    def test_medium_score_not_auto_approved(self, mock_check: MagicMock, mock_ollama: MagicMock) -> None:
        mock_check.return_value = None
        mock_ollama.return_value = '{"score": 0.70, "reasoning": "Mostly accurate."}'
        result = score_synthesis(self._make_request())
        self.assertAlmostEqual(result.score, 0.70)
        self.assertEqual(result.band, "medium")
        self.assertFalse(result.auto_approved)

    @patch("scripts.score_synthesis._check_model_available")
    def test_ollama_unavailable_falls_back_to_default(self, mock_check: MagicMock) -> None:
        mock_check.side_effect = ConnectionError("Ollama not running")
        result = score_synthesis(self._make_request())
        self.assertAlmostEqual(result.score, 0.5)
        self.assertIn("unavailable", result.reasoning.lower())
        self.assertFalse(result.auto_approved)

    def test_missing_compiled_note_returns_fallback(self) -> None:
        req = ScoreRequest(
            source_id="SRC-20260412-0001",
            compiled_note_path=self.root / "nonexistent.md",
            root=self.root,
        )
        result = score_synthesis(req)
        self.assertAlmostEqual(result.score, 0.5)
        self.assertFalse(result.auto_approved)


# ---------------------------------------------------------------------------
# UpdateEntryWithScoreTests
# ---------------------------------------------------------------------------

class UpdateEntryWithScoreTests(unittest.TestCase):
    def test_high_score_sets_auto_approved(self) -> None:
        entry = _make_entry()
        result = _make_result(score=0.91, auto_approved=True)
        updated = update_entry_with_score(entry, result)
        self.assertAlmostEqual(updated["confidence_score"], 0.91)
        self.assertEqual(updated["confidence_band"], "high")
        self.assertEqual(updated["review_action"], "approved")
        self.assertEqual(updated["review_method"], "auto")
        self.assertIsNotNone(updated["reviewed_at"])

    def test_medium_score_leaves_review_action_none(self) -> None:
        entry = _make_entry()
        result = _make_result(score=0.70, auto_approved=False)
        updated = update_entry_with_score(entry, result)
        self.assertAlmostEqual(updated["confidence_score"], 0.70)
        self.assertEqual(updated["confidence_band"], "medium")
        self.assertIsNone(updated["review_action"])
        self.assertIsNone(updated["review_method"])
        self.assertIsNone(updated["reviewed_at"])

    def test_original_entry_not_mutated(self) -> None:
        entry = _make_entry()
        result = _make_result(score=0.91, auto_approved=True)
        update_entry_with_score(entry, result)
        self.assertNotIn("confidence_score", entry)

    def test_scored_at_timestamp_written(self) -> None:
        entry = _make_entry()
        result = _make_result()
        updated = update_entry_with_score(entry, result)
        self.assertIn("scored_at", updated)
        self.assertIsNotNone(updated["scored_at"])

    def test_reasoning_stored(self) -> None:
        entry = _make_entry()
        result = _make_result()
        updated = update_entry_with_score(entry, result)
        self.assertEqual(updated["confidence_reasoning"], result.reasoning)


# ---------------------------------------------------------------------------
# UpdateQueueWithScoreTests
# ---------------------------------------------------------------------------

class UpdateQueueWithScoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)
        self.queue_path = self.root / "metadata" / "review-queue.json"
        self.report_path = self.root / "metadata" / "review-queue.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _patch_paths(self):
        import scripts.score_synthesis as mod
        return (
            patch.object(mod, "REVIEW_QUEUE_PATH", self.queue_path),
            patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path),
        )

    def test_score_fields_written_to_queue(self) -> None:
        entries = [_make_entry()]
        self.queue_path.write_text(json.dumps(entries) + "\n", encoding="utf-8")
        result = _make_result(score=0.91, auto_approved=True)

        p1, p2 = self._patch_paths()
        with p1, p2:
            update_queue_with_score(result)

        reloaded = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(len(reloaded), 1)
        self.assertAlmostEqual(reloaded[0]["confidence_score"], 0.91)
        self.assertEqual(reloaded[0]["confidence_band"], "high")
        self.assertEqual(reloaded[0]["review_action"], "approved")

    def test_unmatched_source_id_not_modified(self) -> None:
        entries = [_make_entry("SRC-OTHER")]
        self.queue_path.write_text(json.dumps(entries) + "\n", encoding="utf-8")
        result = _make_result(source_id="SRC-20260412-0001")

        p1, p2 = self._patch_paths()
        with p1, p2:
            update_queue_with_score(result)

        reloaded = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertNotIn("confidence_score", reloaded[0])

    def test_markdown_report_regenerated(self) -> None:
        entries = [_make_entry(title="My Article")]
        self.queue_path.write_text(json.dumps(entries) + "\n", encoding="utf-8")
        result = _make_result()

        p1, p2 = self._patch_paths()
        with p1, p2:
            update_queue_with_score(result)

        report = self.report_path.read_text(encoding="utf-8")
        self.assertIn("My Article", report)
        self.assertIn("Confidence", report)

    def test_medium_score_does_not_auto_approve(self) -> None:
        entries = [_make_entry()]
        self.queue_path.write_text(json.dumps(entries) + "\n", encoding="utf-8")
        result = _make_result(score=0.70, auto_approved=False)

        p1, p2 = self._patch_paths()
        with p1, p2:
            update_queue_with_score(result)

        reloaded = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertIsNone(reloaded[0]["review_action"])


# ---------------------------------------------------------------------------
# SynthesizedUnscoredTests
# ---------------------------------------------------------------------------

class SynthesizedUnscoredTests(unittest.TestCase):
    def test_returns_only_synthesized_and_unscored(self) -> None:
        queue = [
            _make_entry("SRC-001", review_status="synthesized"),
            _make_entry("SRC-002", review_status="synthesized", confidence_score=0.80),
            _make_entry("SRC-003", review_status="pending_review"),
        ]
        result = _synthesized_unscored(queue)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_id"], "SRC-001")

    def test_empty_queue_returns_empty(self) -> None:
        self.assertEqual(_synthesized_unscored([]), [])


# ---------------------------------------------------------------------------
# FindCompiledNoteTests
# ---------------------------------------------------------------------------

class FindCompiledNoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "compiled" / "source_summaries").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_finds_existing_compiled_note(self) -> None:
        note = self.root / "compiled" / "source_summaries" / "my-article-synthesis.md"
        note.write_text("content", encoding="utf-8")
        item = _make_entry(note_path="raw/articles/my-article.md")
        result = _find_compiled_note(item, self.root)
        self.assertEqual(result, note)

    def test_returns_none_when_compiled_note_missing(self) -> None:
        item = _make_entry(note_path="raw/articles/nonexistent.md")
        result = _find_compiled_note(item, self.root)
        self.assertIsNone(result)

    def test_returns_none_when_source_note_path_empty(self) -> None:
        item = _make_entry(note_path="")
        result = _find_compiled_note(item, self.root)
        self.assertIsNone(result)


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

    def test_report_includes_confidence_header(self) -> None:
        import scripts.score_synthesis as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([_make_entry(confidence_score=0.91)])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("Confidence", content)
        self.assertIn("Review", content)

    def test_report_shows_dash_when_unscored(self) -> None:
        import scripts.score_synthesis as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([_make_entry()])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("—", content)

    def test_report_shows_score_when_scored(self) -> None:
        import scripts.score_synthesis as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([_make_entry(confidence_score=0.91)])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("0.91", content)

    def test_empty_queue_report(self) -> None:
        import scripts.score_synthesis as mod
        with patch.object(mod, "REVIEW_QUEUE_REPORT_PATH", self.report_path):
            _write_queue_report([])
        content = self.report_path.read_text(encoding="utf-8")
        self.assertIn("No items in queue", content)


class SetFrontmatterFieldTests(unittest.TestCase):
    def test_replaces_existing_field(self) -> None:
        text = "---\nconfidence_score: 0.5\n---\n\nBody.\n"
        result = _set_frontmatter_field(text, "confidence_score", "0.87")
        self.assertIn("confidence_score: 0.87", result)
        self.assertNotIn("confidence_score: 0.5", result)

    def test_inserts_missing_field_before_closing_fence(self) -> None:
        text = "---\ntitle: t\n---\n\nBody.\n"
        result = _set_frontmatter_field(text, "confidence_score", "0.91")
        self.assertIn("confidence_score: 0.91", result)
        self.assertEqual(result.count("\n---\n"), 1)

    def test_body_unchanged(self) -> None:
        text = "---\ntitle: t\n---\n\nKeep this.\n"
        result = _set_frontmatter_field(text, "approved", "true")
        self.assertIn("Keep this.", result)


class PatchNoteWithScoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_note(self, name: str = "note.md") -> Path:
        path = self.root / name
        path.write_text(
            "---\ntitle: Test\napproved: false\nconfidence_score: null\n---\n\nBody.\n",
            encoding="utf-8",
        )
        return path

    def test_confidence_score_written(self) -> None:
        path = self._make_note()
        _patch_note_with_score(path, 0.87, auto_approved=False)
        text = path.read_text(encoding="utf-8")
        self.assertIn("confidence_score: 0.87", text)

    def test_approved_set_true_when_auto_approved(self) -> None:
        path = self._make_note()
        _patch_note_with_score(path, 0.9, auto_approved=True)
        text = path.read_text(encoding="utf-8")
        self.assertIn("approved: true", text)

    def test_approved_not_changed_when_not_auto_approved(self) -> None:
        path = self._make_note()
        _patch_note_with_score(path, 0.7, auto_approved=False)
        text = path.read_text(encoding="utf-8")
        # approved field left as-is (false), not set to true
        self.assertNotIn("approved: true", text)

    def test_missing_file_handled_gracefully(self) -> None:
        missing = self.root / "nonexistent.md"
        # Should not raise
        _patch_note_with_score(missing, 0.8, auto_approved=False)


if __name__ == "__main__":
    unittest.main()

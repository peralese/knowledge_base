"""Tests for scripts/feedback.py (Phase 2B-1)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.feedback import (
    join_answer_file,
    list_answers,
    patch_fm_field,
    read_fm_field,
    resolve_answer_path,
    split_answer_file,
    write_feedback,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


SAMPLE_ANSWER = """\
---
question: "What is zero trust?"
topic: security
date: 2026-04-20
sources:
  - compiled/topics/security.md
---

# What is zero trust?

Zero trust means never trust, always verify.

---
*Queried on 2026-04-20 against topic: security*
"""


# ---------------------------------------------------------------------------
# split_answer_file / join_answer_file round-trip
# ---------------------------------------------------------------------------

class SplitJoinTests(unittest.TestCase):
    def test_round_trip_preserves_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            fm, body = split_answer_file(path)
            reconstructed = join_answer_file(fm, body)
            self.assertEqual(reconstructed, SAMPLE_ANSWER)

    def test_fm_contains_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            fm, _ = split_answer_file(path)
            self.assertIn("question:", fm)

    def test_body_contains_answer_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            _, body = split_answer_file(path)
            self.assertIn("# What is zero trust?", body)

    def test_no_frontmatter_returns_empty_fm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", "Just body text.\n")
            fm, body = split_answer_file(path)
            self.assertEqual(fm, "")
            self.assertIn("Just body text.", body)


# ---------------------------------------------------------------------------
# patch_fm_field
# ---------------------------------------------------------------------------

class PatchFmFieldTests(unittest.TestCase):
    def test_appends_new_field(self) -> None:
        fm = 'question: "test"\ndate: 2026-04-20'
        result = patch_fm_field(fm, "feedback", "good")
        self.assertIn('feedback: "good"', result)
        self.assertIn('question: "test"', result)

    def test_replaces_existing_field(self) -> None:
        fm = 'question: "test"\nfeedback: "good"\ndate: 2026-04-20'
        result = patch_fm_field(fm, "feedback", "bad")
        self.assertIn('feedback: "bad"', result)
        self.assertNotIn('feedback: "good"', result)

    def test_null_value_written_correctly(self) -> None:
        fm = 'question: "test"'
        result = patch_fm_field(fm, "feedback", None)
        self.assertIn("feedback: null", result)

    def test_does_not_match_sources_list_items(self) -> None:
        fm = 'question: "test"\nsources:\n  - compiled/source_summaries/feedback-thing.md'
        result = patch_fm_field(fm, "feedback", "good")
        self.assertIn('feedback: "good"', result)
        self.assertIn("  - compiled/source_summaries/feedback-thing.md", result)

    def test_idempotent_double_patch(self) -> None:
        fm = 'question: "test"'
        fm = patch_fm_field(fm, "feedback", "good")
        fm = patch_fm_field(fm, "feedback", "good")
        self.assertEqual(fm.count("feedback:"), 1)


# ---------------------------------------------------------------------------
# read_fm_field
# ---------------------------------------------------------------------------

class ReadFmFieldTests(unittest.TestCase):
    def test_reads_quoted_value(self) -> None:
        fm = 'feedback: "good"'
        self.assertEqual(read_fm_field(fm, "feedback"), "good")

    def test_reads_unquoted_value(self) -> None:
        fm = "feedback: good"
        self.assertEqual(read_fm_field(fm, "feedback"), "good")

    def test_null_returns_empty_string(self) -> None:
        fm = "feedback: null"
        self.assertEqual(read_fm_field(fm, "feedback"), "")

    def test_absent_returns_empty_string(self) -> None:
        fm = 'question: "test"'
        self.assertEqual(read_fm_field(fm, "feedback"), "")

    def test_does_not_match_partial_key(self) -> None:
        fm = 'feedback_note: "too generic"'
        self.assertEqual(read_fm_field(fm, "feedback"), "")


# ---------------------------------------------------------------------------
# write_feedback (round-trip, idempotent overwrite)
# ---------------------------------------------------------------------------

class WriteFeedbackTests(unittest.TestCase):
    def test_marks_good(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            write_feedback(path, "good")
            fm, body = split_answer_file(path)
            self.assertEqual(read_fm_field(fm, "feedback"), "good")
            self.assertIn("# What is zero trust?", body)

    def test_marks_bad_with_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            write_feedback(path, "bad", note="too generic")
            fm, _ = split_answer_file(path)
            self.assertEqual(read_fm_field(fm, "feedback"), "bad")
            self.assertEqual(read_fm_field(fm, "feedback_note"), "too generic")

    def test_idempotent_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            write_feedback(path, "good")
            write_feedback(path, "bad", note="changed my mind")
            fm, _ = split_answer_file(path)
            self.assertEqual(read_fm_field(fm, "feedback"), "bad")
            self.assertEqual(read_fm_field(fm, "feedback_note"), "changed my mind")
            # feedback field appears exactly once
            self.assertEqual(fm.count("feedback:"), 1)

    def test_good_clears_prior_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            write_feedback(path, "bad", note="too vague")
            write_feedback(path, "good")
            fm, _ = split_answer_file(path)
            self.assertEqual(read_fm_field(fm, "feedback"), "good")
            self.assertEqual(read_fm_field(fm, "feedback_note"), "")

    def test_feedback_at_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            write_feedback(path, "good")
            fm, _ = split_answer_file(path)
            at = read_fm_field(fm, "feedback_at")
            self.assertTrue(at.startswith("2026") or at.startswith("20"))

    def test_invalid_rating_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            with self.assertRaises(ValueError):
                write_feedback(path, "meh")

    def test_body_preserved_after_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "answer.md", SAMPLE_ANSWER)
            write_feedback(path, "good")
            _, body = split_answer_file(path)
            self.assertIn("Zero trust means never trust, always verify.", body)


# ---------------------------------------------------------------------------
# resolve_answer_path
# ---------------------------------------------------------------------------

class ResolveAnswerPathTests(unittest.TestCase):
    def _make_answers_dir(self, tmp: str) -> Path:
        answers = Path(tmp) / "outputs" / "answers"
        answers.mkdir(parents=True)
        return answers

    def test_resolves_by_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answers = self._make_answers_dir(tmp)
            (answers / "my-answer.md").write_text(SAMPLE_ANSWER, encoding="utf-8")
            # Monkey-patch ANSWERS_DIR
            import scripts.feedback as fb_mod
            orig = fb_mod.ANSWERS_DIR
            fb_mod.ANSWERS_DIR = answers
            try:
                path = resolve_answer_path("my-answer")
                self.assertEqual(path.name, "my-answer.md")
            finally:
                fb_mod.ANSWERS_DIR = orig

    def test_resolves_with_md_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answers = self._make_answers_dir(tmp)
            (answers / "my-answer.md").write_text(SAMPLE_ANSWER, encoding="utf-8")
            import scripts.feedback as fb_mod
            orig = fb_mod.ANSWERS_DIR
            fb_mod.ANSWERS_DIR = answers
            try:
                path = resolve_answer_path("my-answer.md")
                self.assertEqual(path.name, "my-answer.md")
            finally:
                fb_mod.ANSWERS_DIR = orig

    def test_missing_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answers = self._make_answers_dir(tmp)
            import scripts.feedback as fb_mod
            orig = fb_mod.ANSWERS_DIR
            fb_mod.ANSWERS_DIR = answers
            try:
                with self.assertRaises(FileNotFoundError):
                    resolve_answer_path("nonexistent")
            finally:
                fb_mod.ANSWERS_DIR = orig


# ---------------------------------------------------------------------------
# Stats aggregation (cmd_stats logic)
# ---------------------------------------------------------------------------

class StatsAggregationTests(unittest.TestCase):
    def _make_answer(self, answers_dir: Path, stem: str, rating: str | None = None, note: str = "") -> None:
        text = SAMPLE_ANSWER
        if rating:
            text = text.replace(
                "---\n\n# What is zero trust?",
                f'feedback: "{rating}"\nfeedback_note: "{note}"\n---\n\n# What is zero trust?',
            )
        (answers_dir / f"{stem}.md").write_text(text, encoding="utf-8")

    def test_counts_good_bad_unrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / "outputs" / "answers"
            answers.mkdir(parents=True)
            import scripts.feedback as fb_mod
            orig = fb_mod.ANSWERS_DIR
            fb_mod.ANSWERS_DIR = answers
            try:
                self._make_answer(answers, "a1", "good")
                self._make_answer(answers, "a2", "bad", "too generic")
                self._make_answer(answers, "a3")  # unrated

                paths = list_answers()
                good = bad = unrated = 0
                for p in paths:
                    fm, _ = split_answer_file(p)
                    r = read_fm_field(fm, "feedback")
                    if r == "good":
                        good += 1
                    elif r == "bad":
                        bad += 1
                    else:
                        unrated += 1

                self.assertEqual(good, 1)
                self.assertEqual(bad, 1)
                self.assertEqual(unrated, 1)
            finally:
                fb_mod.ANSWERS_DIR = orig


if __name__ == "__main__":
    unittest.main()

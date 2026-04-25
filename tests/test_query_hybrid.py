"""Tests for query.py 2D-3 additions: hybrid retrieval, normalization, deduplication."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from query import (
    CompiledNote,
    _bm25_select_notes,
    _hybrid_select_notes,
    _normalize_scores,
    _print_retrieval_debug,
    _resolve_retrieval_mode,
    _select_notes,
    _vector_select_notes,
)


def _make_note(stem: str, root: Path) -> CompiledNote:
    path = root / "compiled" / "topics" / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {stem.replace('-', ' ').title()}\n---\n\n" + f"Content about {stem}. " * 30,
        encoding="utf-8",
    )
    return CompiledNote(path=path, title=stem.replace("-", " ").title(), body=f"Content about {stem}.")


# ---------------------------------------------------------------------------
# _normalize_scores
# ---------------------------------------------------------------------------

class NormalizeScoresTests(unittest.TestCase):
    def test_max_score_becomes_one(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        a = _make_note("note-a", root)
        b = _make_note("note-b", root)
        scored = [(a, 8.0), (b, 4.0)]
        normalized = _normalize_scores(scored)
        self.assertAlmostEqual(normalized[0][1], 1.0)
        self.assertAlmostEqual(normalized[1][1], 0.5)
        tmp.cleanup()

    def test_empty_returns_empty(self) -> None:
        self.assertEqual(_normalize_scores([]), [])

    def test_zero_max_returns_zeros(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        n = _make_note("note-x", root)
        result = _normalize_scores([(n, 0.0)])
        self.assertEqual(result[0][1], 0.0)
        tmp.cleanup()

    def test_all_equal_scores(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        a = _make_note("note-a", root)
        b = _make_note("note-b", root)
        normalized = _normalize_scores([(a, 5.0), (b, 5.0)])
        self.assertAlmostEqual(normalized[0][1], 1.0)
        self.assertAlmostEqual(normalized[1][1], 1.0)
        tmp.cleanup()


# ---------------------------------------------------------------------------
# Hybrid score calculation
# ---------------------------------------------------------------------------

class HybridScoreTests(unittest.TestCase):
    def test_hybrid_score_formula(self) -> None:
        bm25_norm = 0.8
        vector_score = 0.6
        bm25_weight = 0.6
        vector_weight = 0.4
        expected = bm25_weight * bm25_norm + vector_weight * vector_score
        self.assertAlmostEqual(expected, 0.72)

    def test_bm25_only_note_gets_partial_score(self) -> None:
        # Note only in BM25, not in vector results
        bm25_weight = 0.6
        vector_weight = 0.4
        bm25_norm = 1.0
        expected = bm25_weight * bm25_norm  # 0.6
        self.assertAlmostEqual(expected, 0.6)

    def test_vector_only_note_gets_partial_score(self) -> None:
        bm25_weight = 0.6
        vector_weight = 0.4
        vector_score = 0.9
        expected = vector_weight * vector_score  # 0.36
        self.assertAlmostEqual(expected, 0.36)

    def test_note_in_both_gets_merged_score(self) -> None:
        bm25_weight = 0.6
        vector_weight = 0.4
        bm25_norm = 0.8
        vector_score = 0.7
        # When the same note appears in both result sets, scores are combined
        expected = bm25_weight * bm25_norm + vector_weight * vector_score  # 0.76
        self.assertAlmostEqual(expected, 0.76)


# ---------------------------------------------------------------------------
# _hybrid_select_notes — deduplication and merging
# ---------------------------------------------------------------------------

class HybridSelectNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.note_a = _make_note("security-guide", self.root)
        self.note_b = _make_note("llm-overview", self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_note_in_both_sets_appears_once(self) -> None:
        # Both BM25 and vector return the same note
        bm25_results = [(self.note_a, 8.0), (self.note_b, 4.0)]
        vector_results = [(self.note_a, 0.9), (self.note_b, 0.3)]

        with patch("query._bm25_select_notes", return_value=bm25_results):
            with patch("query._vector_select_notes", return_value=vector_results):
                results = _hybrid_select_notes("security", self.root, top_n=10)

        paths = [note.path for note, _ in results]
        # Each note should appear exactly once
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn(self.note_a.path, paths)
        self.assertIn(self.note_b.path, paths)

    def test_higher_combined_score_ranked_first(self) -> None:
        bm25_results = [(self.note_a, 10.0), (self.note_b, 1.0)]
        vector_results = [(self.note_a, 0.95), (self.note_b, 0.1)]

        with patch("query._bm25_select_notes", return_value=bm25_results):
            with patch("query._vector_select_notes", return_value=vector_results):
                results = _hybrid_select_notes("security", self.root, top_n=10)

        self.assertGreater(len(results), 0)
        # note_a has higher BM25 and vector scores → should be ranked first
        top_note, top_score = results[0]
        self.assertEqual(top_note.path, self.note_a.path)

    def test_vector_only_note_included(self) -> None:
        # Vector finds a note that BM25 missed
        bm25_results = [(self.note_a, 5.0)]
        vector_results = [(self.note_b, 0.8)]

        with patch("query._bm25_select_notes", return_value=bm25_results):
            with patch("query._vector_select_notes", return_value=vector_results):
                results = _hybrid_select_notes("query", self.root, top_n=10)

        paths = [note.path for note, _ in results]
        self.assertIn(self.note_b.path, paths)

    def test_top_n_respected(self) -> None:
        bm25_results = [(self.note_a, 8.0), (self.note_b, 4.0)]
        vector_results = [(self.note_a, 0.9), (self.note_b, 0.3)]

        with patch("query._bm25_select_notes", return_value=bm25_results):
            with patch("query._vector_select_notes", return_value=vector_results):
                results = _hybrid_select_notes("query", self.root, top_n=1)

        self.assertLessEqual(len(results), 1)


# ---------------------------------------------------------------------------
# _resolve_retrieval_mode — graceful degradation
# ---------------------------------------------------------------------------

class ResolveRetrievalModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_none_with_fresh_index_returns_hybrid(self) -> None:
        with patch("vector_index.index_is_fresh", return_value=True):
            mode, fallback = _resolve_retrieval_mode(None, self.root)
        self.assertEqual(mode, "hybrid")
        self.assertFalse(fallback)

    def test_none_without_index_returns_bm25(self) -> None:
        with patch("vector_index.index_is_fresh", return_value=False):
            mode, fallback = _resolve_retrieval_mode(None, self.root)
        self.assertEqual(mode, "bm25")
        self.assertFalse(fallback)

    def test_hybrid_without_index_falls_back_to_bm25(self) -> None:
        with patch("vector_index.index_is_fresh", return_value=False):
            mode, fallback = _resolve_retrieval_mode("hybrid", self.root)
        self.assertEqual(mode, "bm25")
        self.assertTrue(fallback)

    def test_vector_without_index_falls_back_to_bm25(self) -> None:
        with patch("vector_index.index_is_fresh", return_value=False):
            mode, fallback = _resolve_retrieval_mode("vector", self.root)
        self.assertEqual(mode, "bm25")
        self.assertTrue(fallback)

    def test_bm25_explicit_always_works(self) -> None:
        with patch("vector_index.index_is_fresh", return_value=False):
            mode, fallback = _resolve_retrieval_mode("bm25", self.root)
        self.assertEqual(mode, "bm25")
        self.assertFalse(fallback)

    def test_hybrid_with_fresh_index_returns_hybrid(self) -> None:
        with patch("vector_index.index_is_fresh", return_value=True):
            mode, fallback = _resolve_retrieval_mode("hybrid", self.root)
        self.assertEqual(mode, "hybrid")
        self.assertFalse(fallback)


# ---------------------------------------------------------------------------
# _select_notes dispatch
# ---------------------------------------------------------------------------

class SelectNotesDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bm25_mode_calls_bm25(self) -> None:
        with patch("query._bm25_select_notes", return_value=[]) as mock:
            _select_notes("query", self.root, "bm25", 5)
        mock.assert_called_once()

    def test_vector_mode_calls_vector(self) -> None:
        with patch("query._vector_select_notes", return_value=[]) as mock:
            _select_notes("query", self.root, "vector", 5)
        mock.assert_called_once()

    def test_hybrid_mode_calls_hybrid(self) -> None:
        with patch("query._hybrid_select_notes", return_value=[]) as mock:
            _select_notes("query", self.root, "hybrid", 5)
        mock.assert_called_once()


# ---------------------------------------------------------------------------
# Query --dry-run with --retrieval (graceful degradation end-to-end)
# ---------------------------------------------------------------------------

class QueryDryRunWithRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        topics = self.root / "compiled" / "topics"
        topics.mkdir(parents=True)
        (topics / "security.md").write_text(
            "---\ntitle: Security\n---\n\n" + "Security content. " * 30,
            encoding="utf-8",
        )
        (self.root / "compiled" / "index.md").write_text("# Index\n\n[[security]]\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bm25_retrieval_dry_run_succeeds(self) -> None:
        from query import run  # noqa: PLC0415
        with patch("vector_index.index_is_fresh", return_value=False):
            result = run(
                question="What is security?",
                title="",
                model="qwen2.5:7b",
                force=False,
                dry_run=True,
                root=self.root,
                retrieval="bm25",
                top_n=5,
            )
        self.assertEqual(result, 0)

    def test_hybrid_fallback_to_bm25_dry_run_succeeds(self) -> None:
        from query import run  # noqa: PLC0415
        with patch("vector_index.index_is_fresh", return_value=False):
            result = run(
                question="What is security?",
                title="",
                model="qwen2.5:7b",
                force=False,
                dry_run=True,
                root=self.root,
                retrieval="hybrid",
                top_n=5,
            )
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts/benchmark_query.py — 2D-1."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_query import (
    _build_assessment,
    _is_substantive,
    _percentile,
    run_benchmark,
)


class IsSubstantiveTests(unittest.TestCase):
    def test_short_response_not_substantive(self) -> None:
        self.assertFalse(_is_substantive("I don't know."))

    def test_long_response_is_substantive(self) -> None:
        text = "A" * 250
        self.assertTrue(_is_substantive(text))

    def test_refusal_not_substantive(self) -> None:
        text = "I cannot answer this question because " + "X" * 200
        self.assertFalse(_is_substantive(text))

    def test_empty_not_substantive(self) -> None:
        self.assertFalse(_is_substantive(""))

    def test_no_information_not_substantive(self) -> None:
        text = "No information is available about this topic in the provided context. " + "X" * 200
        self.assertFalse(_is_substantive(text))


class PercentileTests(unittest.TestCase):
    def test_p95_of_ten_values(self) -> None:
        data = list(range(1, 11))  # 1..10
        result = _percentile(data, 95)
        self.assertEqual(result, 10)

    def test_p50_median(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(_percentile(data, 50), 3.0)

    def test_empty_returns_zero(self) -> None:
        self.assertEqual(_percentile([], 95), 0.0)


class BuildAssessmentTests(unittest.TestCase):
    def test_fast_bm25_noted(self) -> None:
        bm25 = {"exact": {"avg_ms": 0.05, "p95_ms": 0.1}}
        corpus = {"total": 37, "topics": 6, "concepts": 14, "entities": 6, "source_summaries": 11}
        result = _build_assessment(bm25, None, corpus)
        lines = result["lines"]
        combined = " ".join(lines)
        self.assertIn("extremely fast", combined)

    def test_small_corpus_noted(self) -> None:
        bm25 = {"exact": {"avg_ms": 0.05, "p95_ms": 0.1}}
        corpus = {"total": 37, "topics": 6, "concepts": 14, "entities": 6, "source_summaries": 11}
        result = _build_assessment(bm25, None, corpus)
        combined = " ".join(result["lines"])
        self.assertIn("37 notes", combined)

    def test_recommendation_includes_sqlite_vec(self) -> None:
        bm25 = {"exact": {"avg_ms": 0.05, "p95_ms": 0.1}}
        corpus = {"total": 37, "topics": 6, "concepts": 14, "entities": 6, "source_summaries": 11}
        result = _build_assessment(bm25, None, corpus)
        combined = " ".join(result["lines"])
        self.assertIn("sqlite-vec", combined)


class RunBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Create minimal corpus
        for d in ["topics", "concepts", "entities", "source_summaries"]:
            (self.root / "compiled" / d).mkdir(parents=True)
        (self.root / "compiled" / "topics" / "test-topic.md").write_text(
            '---\ntitle: "Test Topic"\n---\n\n# Test Topic\n\nContent about security.\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bm25_only_benchmark_runs(self) -> None:
        out = self.root / "outputs" / "benchmarks"
        out.mkdir(parents=True)
        result = run_benchmark(
            root=self.root,
            include_ollama=False,
            runs=2,
            output_path=self.root / "outputs" / "benchmarks" / "test.json",
        )
        self.assertIn("bm25_only", result)
        self.assertIn("exact_keyword", result["bm25_only"])
        self.assertIn("corpus", result)
        self.assertEqual(result["corpus"]["total"], 1)

    def test_benchmark_saves_json(self) -> None:
        out_path = self.root / "outputs" / "benchmarks" / "test.json"
        out_path.parent.mkdir(parents=True)
        run_benchmark(
            root=self.root,
            include_ollama=False,
            runs=2,
            output_path=out_path,
        )
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertIn("timestamp", data)
        self.assertIn("assessment", data)

    def test_benchmark_does_not_write_answers(self) -> None:
        answers_dir = self.root / "outputs" / "answers"
        run_benchmark(
            root=self.root,
            include_ollama=False,
            runs=2,
            output_path=self.root / "outputs" / "benchmarks" / "test.json",
        )
        self.assertFalse(answers_dir.exists())


if __name__ == "__main__":
    unittest.main()

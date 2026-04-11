"""Tests for scripts/search.py (Phase 10)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.search import (
    BM25Index,
    Document,
    SearchResult,
    build_index,
    load_documents,
    search,
    tokenize,
    _parse_frontmatter_title,
    _strip_frontmatter,
    bm25_score,
    main,
)


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

class TokenizeTests(unittest.TestCase):
    def test_basic_lowercasing(self) -> None:
        self.assertEqual(tokenize("Hello World"), ["hello", "world"])

    def test_stop_words_removed(self) -> None:
        tokens = tokenize("what is the answer")
        self.assertNotIn("what", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("the", tokens)

    def test_short_tokens_removed(self) -> None:
        tokens = tokenize("a an at be it")
        self.assertEqual(tokens, [])

    def test_non_alphanumeric_splits(self) -> None:
        tokens = tokenize("kubernetes/fargate-security_tradeoffs")
        self.assertIn("kubernetes", tokens)
        self.assertIn("fargate", tokens)
        self.assertIn("security", tokens)
        self.assertIn("tradeoffs", tokens)

    def test_numbers_kept(self) -> None:
        tokens = tokenize("qwen2.5 model version 14b")
        self.assertIn("qwen2", tokens)
        self.assertIn("14b", tokens)

    def test_empty_string(self) -> None:
        self.assertEqual(tokenize(""), [])

    def test_all_stop_words(self) -> None:
        self.assertEqual(tokenize("and or but for from"), [])


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

class FrontmatterTests(unittest.TestCase):
    def test_parses_title(self) -> None:
        text = '---\ntitle: "My Note"\n---\n\nBody text.\n'
        self.assertEqual(_parse_frontmatter_title(text), "My Note")

    def test_returns_empty_when_no_frontmatter(self) -> None:
        self.assertEqual(_parse_frontmatter_title("Just body text."), "")

    def test_returns_empty_when_no_title_field(self) -> None:
        text = "---\ndate: 2026-01-01\n---\n\nBody.\n"
        self.assertEqual(_parse_frontmatter_title(text), "")

    def test_strips_frontmatter(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\nBody text here.\n"
        self.assertEqual(_strip_frontmatter(text), "Body text here.")

    def test_strip_no_frontmatter(self) -> None:
        self.assertEqual(_strip_frontmatter("Just body."), "Just body.")


# ---------------------------------------------------------------------------
# load_documents
# ---------------------------------------------------------------------------

class LoadDocumentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, rel_path: str, content: str) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_loads_compiled_topics(self) -> None:
        self._write("compiled/topics/my-topic.md", '---\ntitle: "My Topic"\n---\n\nBody.\n')
        docs = load_documents(self.root)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].title, "My Topic")
        self.assertEqual(docs[0].layer, "compiled")

    def test_loads_multiple_compiled_subdirs(self) -> None:
        self._write("compiled/topics/topic-a.md", "Topic A body.")
        self._write("compiled/concepts/concept-b.md", "Concept B body.")
        self._write("compiled/source_summaries/summary-c.md", "Summary C body.")
        docs = load_documents(self.root)
        stems = {d.path.stem for d in docs}
        self.assertIn("topic-a", stems)
        self.assertIn("concept-b", stems)
        self.assertIn("summary-c", stems)

    def test_raw_docs_excluded_by_default(self) -> None:
        self._write("compiled/topics/topic-a.md", "Topic A.")
        self._write("raw/articles/article-b.md", "Article B.")
        docs = load_documents(self.root)
        layers = {d.layer for d in docs}
        self.assertNotIn("raw", layers)

    def test_raw_docs_included_when_flag_set(self) -> None:
        self._write("compiled/topics/topic-a.md", "Topic A.")
        self._write("raw/articles/article-b.md", "Article B.")
        docs = load_documents(self.root, include_raw=True)
        layers = {d.layer for d in docs}
        self.assertIn("compiled", layers)
        self.assertIn("raw", layers)

    def test_missing_dirs_are_skipped(self) -> None:
        docs = load_documents(self.root)
        self.assertEqual(docs, [])

    def test_stem_fallback_title(self) -> None:
        self._write("compiled/topics/my-note.md", "No frontmatter.")
        docs = load_documents(self.root)
        self.assertEqual(docs[0].title, "My Note")

    def test_body_excludes_frontmatter(self) -> None:
        self._write("compiled/topics/note.md", '---\ntitle: "T"\n---\n\nJust body.\n')
        docs = load_documents(self.root)
        self.assertNotIn("---", docs[0].body)
        self.assertIn("Just body.", docs[0].body)


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

class BuildIndexTests(unittest.TestCase):
    def _doc(self, stem: str, title: str, body: str) -> Document:
        return Document(path=Path(f"{stem}.md"), title=title, body=body, layer="compiled")

    def test_doc_count(self) -> None:
        docs = [self._doc("a", "Alpha", "alpha content"), self._doc("b", "Beta", "beta content")]
        index = build_index(docs)
        self.assertEqual(index.doc_count, 2)

    def test_inverted_index_populated(self) -> None:
        docs = [self._doc("a", "Alpha", "kubernetes security fargate")]
        index = build_index(docs)
        self.assertIn("kubernetes", index.inverted)
        self.assertIn("security", index.inverted)
        self.assertIn("fargate", index.inverted)

    def test_title_tokens_boosted(self) -> None:
        # Title tokens appear 3x in the index; body once. A title-only term
        # should have a higher frequency than a body-only term.
        docs = [self._doc("a", "kubernetes fargate", "some other content words here")]
        index = build_index(docs)
        # "kubernetes" appears in title (×3); "content" appears in body only (×1)
        k8s_freq = index.inverted.get("kubernetes", {}).get(0, 0)
        content_freq = index.inverted.get("content", {}).get(0, 0)
        self.assertGreater(k8s_freq, content_freq)

    def test_avg_length_positive(self) -> None:
        docs = [self._doc("a", "Title", "Some words in the body.")]
        index = build_index(docs)
        self.assertGreater(index.avg_length, 0)

    def test_doc_lengths_match_doc_count(self) -> None:
        docs = [self._doc(str(i), f"Title {i}", f"body content {i}") for i in range(5)]
        index = build_index(docs)
        self.assertEqual(len(index.doc_lengths), 5)


# ---------------------------------------------------------------------------
# bm25_score
# ---------------------------------------------------------------------------

class BM25ScoreTests(unittest.TestCase):
    def _build(self, docs: list[Document]) -> BM25Index:
        return build_index(docs)

    def _doc(self, stem: str, title: str, body: str) -> Document:
        return Document(path=Path(f"{stem}.md"), title=title, body=body, layer="compiled")

    def test_missing_term_returns_zero(self) -> None:
        docs = [self._doc("a", "Alpha", "kubernetes security")]
        index = self._build(docs)
        self.assertEqual(bm25_score("nonexistent", 0, index), 0.0)

    def test_term_absent_from_doc_returns_zero(self) -> None:
        docs = [
            self._doc("a", "Alpha", "kubernetes security"),
            self._doc("b", "Beta", "fargate networking"),
        ]
        index = self._build(docs)
        # "fargate" is in doc 1 only; score for doc 0 should be 0
        self.assertEqual(bm25_score("fargate", 0, index), 0.0)

    def test_present_term_returns_positive_score(self) -> None:
        docs = [self._doc("a", "Alpha", "kubernetes security")]
        index = self._build(docs)
        score = bm25_score("kubernetes", 0, index)
        self.assertGreater(score, 0.0)

    def test_more_occurrences_yield_higher_score(self) -> None:
        docs = [
            self._doc("a", "Alpha", "kubernetes kubernetes kubernetes security"),
            self._doc("b", "Beta", "kubernetes security networking"),
        ]
        index = self._build(docs)
        score_a = bm25_score("kubernetes", 0, index)
        score_b = bm25_score("kubernetes", 1, index)
        self.assertGreater(score_a, score_b)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class SearchTests(unittest.TestCase):
    def _doc(self, stem: str, title: str, body: str) -> Document:
        return Document(path=Path(f"{stem}.md"), title=title, body=body, layer="compiled")

    def test_returns_empty_for_no_query_terms(self) -> None:
        docs = [self._doc("a", "Alpha", "some body")]
        index = build_index(docs)
        self.assertEqual(search("", index), [])

    def test_returns_empty_for_all_stop_word_query(self) -> None:
        docs = [self._doc("a", "Alpha", "some body")]
        index = build_index(docs)
        self.assertEqual(search("the and is", index), [])

    def test_relevant_doc_ranked_first(self) -> None:
        docs = [
            self._doc("eks", "EKS Guide", "kubernetes eks fargate security networking"),
            self._doc("gemma", "Gemma Models", "gemma llm local inference model"),
        ]
        index = build_index(docs)
        results = search("kubernetes eks security", index)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].document.path.stem, "eks")

    def test_top_n_limits_results(self) -> None:
        docs = [self._doc(f"doc-{i}", f"Doc {i}", f"kubernetes topic {i} content") for i in range(10)]
        index = build_index(docs)
        results = search("kubernetes", index, top_n=3)
        self.assertLessEqual(len(results), 3)

    def test_matched_terms_populated(self) -> None:
        docs = [self._doc("a", "Alpha", "kubernetes fargate security")]
        index = build_index(docs)
        results = search("kubernetes fargate", index)
        self.assertGreater(len(results), 0)
        self.assertIn("kubernetes", results[0].matched_terms)
        self.assertIn("fargate", results[0].matched_terms)

    def test_score_is_positive(self) -> None:
        docs = [self._doc("a", "Alpha", "kubernetes security")]
        index = build_index(docs)
        results = search("kubernetes", index)
        self.assertGreater(results[0].score, 0.0)

    def test_zero_score_docs_excluded(self) -> None:
        docs = [
            self._doc("relevant", "Relevant", "kubernetes security"),
            self._doc("irrelevant", "Irrelevant", "cooking recipes pasta"),
        ]
        index = build_index(docs)
        results = search("kubernetes", index)
        stems = [r.document.path.stem for r in results]
        self.assertNotIn("irrelevant", stems)

    def test_title_match_boosts_ranking(self) -> None:
        # One doc has "kubernetes" in title; another only in body
        docs = [
            self._doc("body-only", "Generic Guide", "kubernetes security topic details here"),
            self._doc("title-match", "Kubernetes Security", "general security guide with details"),
        ]
        index = build_index(docs)
        results = search("kubernetes", index)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].document.path.stem, "title-match")


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------

class MainCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "compiled" / "topics").mkdir(parents=True)
        (self.root / "compiled" / "topics" / "eks-guide.md").write_text(
            '---\ntitle: "EKS Guide"\n---\n\nKubernetes EKS fargate security.\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str) -> int:
        import scripts.search as mod
        original_root = mod.ROOT
        mod.ROOT = self.root
        try:
            return main(list(args))
        finally:
            mod.ROOT = original_root

    def test_returns_zero_on_successful_search(self) -> None:
        self.assertEqual(self._run("kubernetes"), 0)

    def test_returns_one_when_no_notes(self) -> None:
        import shutil
        shutil.rmtree(self.root / "compiled")
        self.assertEqual(self._run("kubernetes"), 1)

    def test_json_output_is_valid(self, capsys=None) -> None:
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run("kubernetes", "--json")
        self.assertEqual(rc, 0)
        output = buf.getvalue().strip()
        parsed = json.loads(output)
        self.assertIsInstance(parsed, list)

    def test_top_n_limits_results(self) -> None:
        # Add extra notes so top-n matters
        for i in range(5):
            (self.root / "compiled" / "topics" / f"topic-{i}.md").write_text(
                f"kubernetes content topic {i} security.\n", encoding="utf-8"
            )
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run("kubernetes", "--json", "--top-n", "2")
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue().strip())
        self.assertLessEqual(len(parsed), 2)


if __name__ == "__main__":
    unittest.main()

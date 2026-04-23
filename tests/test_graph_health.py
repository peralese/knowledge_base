"""Tests for scripts/graph_health.py (Phase 2A-1)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.graph_health import (
    STUB_THRESHOLD,
    _count_wikilinks,
    _extract_wikilinks,
    _flatten,
    _meaningful_body_lines,
    _parse_compiled_from,
    _parse_frontmatter_field,
    _strip_frontmatter,
    compute_metrics,
    format_diff,
    format_report,
    is_stub,
    load_most_recent_snapshot,
    save_snapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _topic(root: Path, stem: str, compiled_from: list[str], body: str = "") -> Path:
    refs = "\n".join('  - "' + s + '"' for s in compiled_from)
    default_body = "# Topic body\n\nSome content here.\n"
    content = (
        '---\ntitle: "' + stem + '"\nnote_type: topic\napproved: true\n'
        'compiled_from: \n' + refs + '\n---\n\n' + (body or default_body)
    )
    return _write(root, "compiled/topics/" + stem + ".md", content)


def _concept(root: Path, stem: str, body: str = "", gen_method: str = "") -> Path:
    fm_extra = f'\ngeneration_method: {gen_method}' if gen_method else ""
    content = f'---\ntitle: "{stem}"\nnote_type: concept{fm_extra}\n---\n\n{body}'
    return _write(root, f"compiled/concepts/{stem}.md", content)


def _summary(root: Path, stem: str, approved: bool = True) -> Path:
    content = (
        f'---\ntitle: "{stem}"\nnote_type: source_summary\n'
        f'approved: {"true" if approved else "false"}\n---\n\nSummary body.\n'
    )
    return _write(root, f"compiled/source_summaries/{stem}.md", content)


# ---------------------------------------------------------------------------
# _strip_frontmatter
# ---------------------------------------------------------------------------

class StripFrontmatterTests(unittest.TestCase):
    def test_strips_yaml_block(self) -> None:
        text = "---\ntitle: T\n---\n\nBody here.\n"
        self.assertEqual(_strip_frontmatter(text), "Body here.")

    def test_no_frontmatter(self) -> None:
        text = "Just body text."
        self.assertEqual(_strip_frontmatter(text), "Just body text.")

    def test_empty(self) -> None:
        self.assertEqual(_strip_frontmatter(""), "")


# ---------------------------------------------------------------------------
# _parse_frontmatter_field
# ---------------------------------------------------------------------------

class ParseFrontmatterFieldTests(unittest.TestCase):
    def test_reads_quoted(self) -> None:
        text = '---\ntitle: "My Note"\n---\n\nBody.'
        self.assertEqual(_parse_frontmatter_field(text, "title"), "My Note")

    def test_reads_unquoted(self) -> None:
        text = "---\ngeneration_method: stub\n---\n\nBody."
        self.assertEqual(_parse_frontmatter_field(text, "generation_method"), "stub")

    def test_missing_field(self) -> None:
        text = "---\ntitle: T\n---\n\nBody."
        self.assertEqual(_parse_frontmatter_field(text, "generation_method"), "")


# ---------------------------------------------------------------------------
# _meaningful_body_lines
# ---------------------------------------------------------------------------

class MeaningfulBodyLinesTests(unittest.TestCase):
    def test_empty_body(self) -> None:
        self.assertEqual(_meaningful_body_lines(""), [])

    def test_headings_excluded(self) -> None:
        body = "# Heading\n## Sub\n\nReal content here."
        result = _meaningful_body_lines(body)
        self.assertEqual(result, ["Real content here."])

    def test_placeholder_excluded(self) -> None:
        body = "_Stub page — created by lint._\n\nReal line."
        result = _meaningful_body_lines(body)
        self.assertEqual(result, ["Real line."])

    def test_blank_lines_excluded(self) -> None:
        body = "\n\n  \nContent."
        result = _meaningful_body_lines(body)
        self.assertEqual(result, ["Content."])

    def test_counts_multiple(self) -> None:
        body = "Line one.\nLine two.\nLine three.\nLine four."
        self.assertEqual(len(_meaningful_body_lines(body)), 4)

    def test_wikilink_list_entries_excluded(self) -> None:
        # "Mentioned In" cross-reference entries are not definition content.
        body = "## Mentioned In\n\n- [[source-synthesis]] — context here.\n"
        result = _meaningful_body_lines(body)
        self.assertEqual(result, [])

    def test_prose_with_wikilinks_included(self) -> None:
        # Inline wikilinks in prose lines are NOT excluded — only list items.
        body = "The [[transformer]] model is the key architecture.\n"
        result = _meaningful_body_lines(body)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# is_stub
# ---------------------------------------------------------------------------

class IsStubTests(unittest.TestCase):
    def test_stub_by_generation_method(self) -> None:
        text = "---\ngeneration_method: stub\n---\n\nSome long content that would otherwise not be a stub."
        self.assertTrue(is_stub(text))

    def test_stub_by_thin_body(self) -> None:
        # Fewer than STUB_THRESHOLD meaningful lines
        lines = "\n".join(f"Line {i}." for i in range(STUB_THRESHOLD - 1))
        text = f"---\ntitle: T\n---\n\n{lines}"
        self.assertTrue(is_stub(text))

    def test_not_stub_with_enough_content(self) -> None:
        lines = "\n".join(f"Line {i} with real content about the topic." for i in range(STUB_THRESHOLD))
        text = f"---\ntitle: T\ngeneration_method: ollama_local\n---\n\n{lines}"
        self.assertFalse(is_stub(text))

    def test_stub_only_headings(self) -> None:
        text = "---\ntitle: T\n---\n\n## Mentioned In\n\n## Related Concepts\n"
        self.assertTrue(is_stub(text))

    def test_stub_with_lint_placeholder(self) -> None:
        text = (
            "---\ntitle: T\ngeneration_method: stub\n---\n\n"
            "_Stub page — created by lint._\n\n## Mentioned In\n\n## Related Concepts\n"
        )
        self.assertTrue(is_stub(text))

    def test_not_stub_single_paragraph_definition(self) -> None:
        # Mirrors the output format of define_concepts.py: a one-paragraph
        # definition followed by section headers. Must be classified as NOT stub.
        text = (
            "---\ntitle: Context Engineering\nnote_type: concept\n"
            "generation_method: ollama_local\ngenerated_by: ollama-concept-definition\n---\n\n"
            "Context engineering is the practice of assembling relevant information "
            "for an AI agent's operations. It enhances both short-term session management "
            "and long-term memory retention.\n\n"
            "## Mentioned In\n\n## Related Concepts\n"
        )
        self.assertFalse(is_stub(text))

    def test_stub_frontmatter_only_no_body(self) -> None:
        # Note with frontmatter block but no body content at all.
        text = "---\ntitle: Empty\nnote_type: concept\ngeneration_method: ollama_local\n---\n\n"
        self.assertTrue(is_stub(text))

    def test_stub_with_only_wikilink_mentioned_in_entries(self) -> None:
        # A concept note that has a "Mentioned In" wikilink list but no definition
        # prose is still a stub — wikilink cross-references are not definition content.
        text = (
            "---\ntitle: Agent Architecture\nnote_type: concept\n"
            "generation_method: ollama_local\n---\n\n"
            "# Agent Architecture\n\n"
            "_Definition not yet written._\n\n"
            "## Mentioned In\n\n"
            "- [[some-source-synthesis]] — Provides context about the concept.\n\n"
            "## Related Concepts\n"
        )
        self.assertTrue(is_stub(text))


# ---------------------------------------------------------------------------
# Wikilink parsing
# ---------------------------------------------------------------------------

class WikilinkParsingTests(unittest.TestCase):
    def test_basic_link(self) -> None:
        body = "See [[some-concept]] for details."
        self.assertEqual(_extract_wikilinks(body), ["some-concept"])

    def test_multiple_links(self) -> None:
        body = "[[alpha]] and [[beta]] and [[gamma]]."
        self.assertEqual(_extract_wikilinks(body), ["alpha", "beta", "gamma"])

    def test_link_with_alias(self) -> None:
        body = "See [[target|display text]] here."
        self.assertEqual(_extract_wikilinks(body), ["target"])

    def test_link_with_heading(self) -> None:
        body = "See [[note#section]] here."
        self.assertEqual(_extract_wikilinks(body), ["note"])

    def test_no_links(self) -> None:
        body = "No wikilinks in this text."
        self.assertEqual(_extract_wikilinks(body), [])

    def test_count_wikilinks_strips_frontmatter(self) -> None:
        text = "---\ntitle: T\n---\n\n[[one]] and [[two]]."
        self.assertEqual(_count_wikilinks(text), 2)

    def test_count_zero_in_body(self) -> None:
        text = "---\ntitle: T\n---\n\nNo links here."
        self.assertEqual(_count_wikilinks(text), 0)


# ---------------------------------------------------------------------------
# _parse_compiled_from
# ---------------------------------------------------------------------------

class ParseCompiledFromTests(unittest.TestCase):
    def test_parses_list(self) -> None:
        text = '---\ntitle: T\ncompiled_from: \n  - "source-a"\n  - "source-b"\n---\n\nBody.'
        self.assertEqual(_parse_compiled_from(text), ["source-a", "source-b"])

    def test_empty_list(self) -> None:
        text = "---\ntitle: T\ncompiled_from: \n---\n\nBody."
        self.assertEqual(_parse_compiled_from(text), [])

    def test_no_compiled_from(self) -> None:
        text = "---\ntitle: T\n---\n\nBody."
        self.assertEqual(_parse_compiled_from(text), [])


# ---------------------------------------------------------------------------
# compute_metrics (integration)
# ---------------------------------------------------------------------------

class ComputeMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _concept_note(self, stem: str, body: str = "", gen: str = "") -> None:
        _concept(self.root, stem, body, gen)

    def test_empty_corpus(self) -> None:
        m = compute_metrics(self.root)
        self.assertEqual(m["note_counts"]["topics"], 0)
        self.assertEqual(m["note_counts"]["concepts"], 0)
        self.assertIsNone(m["stub_ratio_pct"])
        self.assertEqual(m["orphan_count"], 0)
        self.assertIsNone(m["source_coverage_pct"])

    def test_counts_notes_by_type(self) -> None:
        _topic(self.root, "topic-a", ["src-a"])
        _topic(self.root, "topic-b", ["src-a", "src-b"])
        _concept(self.root, "concept-x", "Real content line one.\nLine two.\nLine three.")
        _summary(self.root, "src-a", approved=True)
        m = compute_metrics(self.root)
        self.assertEqual(m["note_counts"]["topics"], 2)
        self.assertEqual(m["note_counts"]["concepts"], 1)
        self.assertEqual(m["note_counts"]["source_summaries"], 1)

    def test_stub_ratio_all_stubs(self) -> None:
        _concept(self.root, "stub-a", gen_method="stub")
        _concept(self.root, "stub-b", gen_method="stub")
        m = compute_metrics(self.root)
        self.assertEqual(m["stub_ratio_pct"], 100.0)
        self.assertEqual(m["stub_count"], 2)

    def test_stub_ratio_no_stubs(self) -> None:
        body = "Real content line one.\nLine two.\nLine three.\n"
        _concept(self.root, "rich-a", body=body)
        _concept(self.root, "rich-b", body=body)
        m = compute_metrics(self.root)
        self.assertEqual(m["stub_ratio_pct"], 0.0)
        self.assertEqual(m["stub_count"], 0)

    def test_orphan_detection(self) -> None:
        # Two concepts, topic links to one of them
        _concept(self.root, "linked-concept", "Body line one.\nLine two.\nLine three.")
        _concept(self.root, "orphan-concept", "Body line one.\nLine two.\nLine three.")
        _topic(self.root, "topic-a", [], body="[[linked-concept]] in body.\n")
        m = compute_metrics(self.root)
        # linked-concept has an incoming link; orphan-concept does not
        self.assertIn("orphan-concept", m["top_orphans"])
        self.assertNotIn("linked-concept", m["top_orphans"])
        self.assertEqual(m["orphaned_concepts"], 1)

    def test_source_coverage(self) -> None:
        _summary(self.root, "src-a", approved=True)
        _summary(self.root, "src-b", approved=True)
        _summary(self.root, "src-c", approved=False)
        _topic(self.root, "topic-a", ["src-a"])  # covers src-a only
        m = compute_metrics(self.root)
        # 2 approved sources, 1 covered → 50%
        self.assertEqual(m["total_approved_sources"], 2)
        self.assertEqual(m["covered_approved_sources"], 1)
        self.assertEqual(m["source_coverage_pct"], 50.0)

    def test_wikilink_density(self) -> None:
        body_with_links = "[[alpha]] and [[beta]] are linked here.\n"
        _topic(self.root, "topic-a", [], body=body_with_links)
        m = compute_metrics(self.root)
        self.assertEqual(m["wikilink_density"]["topics"], 2.0)

    def test_avg_sources_per_topic(self) -> None:
        _summary(self.root, "s1", approved=True)
        _summary(self.root, "s2", approved=True)
        _topic(self.root, "t1", ["s1", "s2"])
        _topic(self.root, "t2", ["s1"])
        m = compute_metrics(self.root)
        # t1 has 2, t2 has 1 → avg 1.5
        self.assertEqual(m["avg_approved_sources_per_topic"], 1.5)


# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------

class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_and_load_snapshot(self) -> None:
        metrics = compute_metrics(self.root)

        import scripts.graph_health as gh
        orig_dir = gh.SNAPSHOTS_DIR
        gh.SNAPSHOTS_DIR = self.root / "outputs" / "graph_health"
        try:
            path = save_snapshot(metrics)
            self.assertTrue(path.exists())
            loaded = json.loads(path.read_text())
            self.assertEqual(loaded["date"], metrics["date"])
        finally:
            gh.SNAPSHOTS_DIR = orig_dir

    def test_load_most_recent_returns_none_when_empty(self) -> None:
        import scripts.graph_health as gh
        orig_dir = gh.SNAPSHOTS_DIR
        gh.SNAPSHOTS_DIR = self.root / "outputs" / "graph_health"
        try:
            result = load_most_recent_snapshot()
            self.assertIsNone(result)
        finally:
            gh.SNAPSHOTS_DIR = orig_dir


# ---------------------------------------------------------------------------
# format_diff
# ---------------------------------------------------------------------------

class FormatDiffTests(unittest.TestCase):
    def test_diff_shows_delta(self) -> None:
        before = {"date": "2026-01-01", "stub_ratio_pct": 80.0, "orphan_count": 10,
                  "stub_count": 8, "source_coverage_pct": 50.0,
                  "avg_approved_sources_per_topic": 1.0,
                  "note_counts": {"topics": 5, "concepts": 10, "entities": 0, "source_summaries": 7},
                  "wikilink_density": {"topics": 1.0, "concepts": 0.0, "entities": 0.0,
                                       "source_summaries": 0.5}}
        after = {"date": "2026-01-02", "stub_ratio_pct": 40.0, "orphan_count": 5,
                 "stub_count": 4, "source_coverage_pct": 80.0,
                 "avg_approved_sources_per_topic": 2.0,
                 "note_counts": {"topics": 5, "concepts": 10, "entities": 0, "source_summaries": 7},
                 "wikilink_density": {"topics": 2.0, "concepts": 1.0, "entities": 0.0,
                                      "source_summaries": 0.5}}
        report = format_diff(_flatten(before), _flatten(after))
        self.assertIn("80.0% → 40.0%", report)
        self.assertIn("10 → 5", report)


if __name__ == "__main__":
    unittest.main()

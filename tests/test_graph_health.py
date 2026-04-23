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
    load_prior_snapshot,
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

    def _patch_dir(self, gh):
        gh.SNAPSHOTS_DIR = self.root / "outputs" / "graph_health"

    def test_save_uses_timestamp_filename(self) -> None:
        metrics = compute_metrics(self.root)
        import scripts.graph_health as gh
        orig_dir = gh.SNAPSHOTS_DIR
        self._patch_dir(gh)
        try:
            path = save_snapshot(metrics)
            self.assertTrue(path.exists())
            # Filename must be timestamp-based: YYYY-MM-DD-HHMMSS.json
            self.assertRegex(path.name, r"^\d{4}-\d{2}-\d{2}-\d{6}\.json$")
            loaded = json.loads(path.read_text())
            self.assertEqual(loaded["date"], metrics["date"])
            self.assertIn("timestamp", loaded)
        finally:
            gh.SNAPSHOTS_DIR = orig_dir

    def test_load_most_recent_returns_none_when_empty(self) -> None:
        import scripts.graph_health as gh
        orig_dir = gh.SNAPSHOTS_DIR
        self._patch_dir(gh)
        try:
            result = load_most_recent_snapshot()
            self.assertIsNone(result)
        finally:
            gh.SNAPSHOTS_DIR = orig_dir

    def test_load_prior_snapshot_finds_earlier(self) -> None:
        import scripts.graph_health as gh
        orig_dir = gh.SNAPSHOTS_DIR
        snap_dir = self.root / "outputs" / "graph_health"
        snap_dir.mkdir(parents=True, exist_ok=True)
        gh.SNAPSHOTS_DIR = snap_dir
        try:
            # Write two snapshots with different timestamps
            snap_a = {"date": "2026-01-01", "timestamp": "2026-01-01-090000",
                      "stub_count": 10, "stub_ratio_pct": 100.0}
            snap_b = {"date": "2026-01-01", "timestamp": "2026-01-01-120000",
                      "stub_count": 5, "stub_ratio_pct": 50.0}
            (snap_dir / "2026-01-01-090000.json").write_text(json.dumps(snap_a))
            (snap_dir / "2026-01-01-120000.json").write_text(json.dumps(snap_b))

            # Ask for prior to 120000 → should get 090000
            result = load_prior_snapshot("2026-01-01-120000")
            self.assertIsNotNone(result)
            data, stem = result
            self.assertEqual(stem, "2026-01-01-090000")
            self.assertEqual(data["stub_count"], 10)
        finally:
            gh.SNAPSHOTS_DIR = orig_dir

    def test_load_prior_snapshot_returns_none_when_only_one(self) -> None:
        import scripts.graph_health as gh
        orig_dir = gh.SNAPSHOTS_DIR
        snap_dir = self.root / "outputs" / "graph_health"
        snap_dir.mkdir(parents=True, exist_ok=True)
        gh.SNAPSHOTS_DIR = snap_dir
        try:
            snap = {"date": "2026-01-01", "timestamp": "2026-01-01-090000",
                    "stub_count": 10}
            (snap_dir / "2026-01-01-090000.json").write_text(json.dumps(snap))

            # Only one snapshot — nothing prior to it
            result = load_prior_snapshot("2026-01-01-090000")
            self.assertIsNone(result)
        finally:
            gh.SNAPSHOTS_DIR = orig_dir

    def test_load_prior_snapshot_normalises_legacy_date_filenames(self) -> None:
        import scripts.graph_health as gh
        orig_dir = gh.SNAPSHOTS_DIR
        snap_dir = self.root / "outputs" / "graph_health"
        snap_dir.mkdir(parents=True, exist_ok=True)
        gh.SNAPSHOTS_DIR = snap_dir
        try:
            # Legacy date-only filename (YYYY-MM-DD.json) treated as 000000 timestamp
            legacy = {"date": "2026-01-01", "stub_count": 14}
            (snap_dir / "2026-01-01.json").write_text(json.dumps(legacy))

            # Any later timestamp should find it as a prior
            result = load_prior_snapshot("2026-01-01-100000")
            self.assertIsNotNone(result)
            data, stem = result
            self.assertEqual(data["stub_count"], 14)
        finally:
            gh.SNAPSHOTS_DIR = orig_dir


# ---------------------------------------------------------------------------
# format_diff
# ---------------------------------------------------------------------------

def _make_metrics(stub_count: int, stub_ratio: float, orphans: int,
                  wikilink_topics: float = 2.33, wikilink_concepts: float = 0.0,
                  source_coverage: float = 100.0, timestamp: str = "2026-01-01-000000") -> dict:
    return {
        "date": timestamp[:10],
        "timestamp": timestamp,
        "note_counts": {"topics": 6, "concepts": 14, "entities": 0, "source_summaries": 7},
        "wikilink_density": {"topics": wikilink_topics, "concepts": wikilink_concepts,
                             "entities": 0.0, "source_summaries": 2.14},
        "stub_ratio_pct": stub_ratio,
        "stub_count": stub_count,
        "total_concept_notes": 14,
        "orphan_count": orphans,
        "orphaned_concepts": orphans,
        "orphaned_entities": 0,
        "top_orphans": [],
        "source_coverage_pct": source_coverage,
        "covered_approved_sources": 2,
        "total_approved_sources": 2,
        "avg_approved_sources_per_topic": 0.33,
    }


class FormatDiffTests(unittest.TestCase):
    def test_diff_shows_stub_improvement_marker(self) -> None:
        before = _make_metrics(14, 100.0, 14, timestamp="2026-01-01-000000")
        after = _make_metrics(9, 64.3, 9, timestamp="2026-01-01-100000")
        report = format_diff(before, after,
                             snap_a="2026-01-01-000000.json",
                             snap_b="2026-01-01-100000.json")
        # Stub ratio improved (down) → ✓
        self.assertIn("✓", report)
        self.assertIn("64.3%", report)
        self.assertIn("100.0%", report)

    def test_diff_shows_regression_marker(self) -> None:
        before = _make_metrics(9, 64.3, 9, wikilink_topics=3.0, timestamp="2026-01-01-000000")
        after = _make_metrics(12, 85.7, 12, wikilink_topics=2.0, timestamp="2026-01-01-100000")
        report = format_diff(before, after)
        # Wikilink density went down — that's a regression (✗)
        self.assertIn("✗", report)

    def test_diff_no_change_shows_dash(self) -> None:
        before = _make_metrics(14, 100.0, 14, timestamp="2026-01-01-000000")
        after = _make_metrics(14, 100.0, 14, timestamp="2026-01-01-100000")
        report = format_diff(before, after)
        # No change in topics → should show — for that row
        self.assertIn("—", report)

    def test_diff_includes_snapshot_names(self) -> None:
        before = _make_metrics(14, 100.0, 14, timestamp="2026-01-01-000000")
        after = _make_metrics(9, 64.3, 9, timestamp="2026-01-01-100000")
        report = format_diff(before, after,
                             snap_a="2026-01-01-000000.json",
                             snap_b="2026-01-01-100000.json")
        self.assertIn("2026-01-01-000000.json", report)
        self.assertIn("2026-01-01-100000.json", report)


if __name__ == "__main__":
    unittest.main()

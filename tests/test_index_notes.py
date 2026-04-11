"""Tests for scripts/index_notes.py (Phase 8)."""
from __future__ import annotations

import io
import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.index_notes import (
    NoteEntry,
    build_index_text,
    extract_summary,
    run,
    _load_note_entries,
    _parse_frontmatter,
    _strip_frontmatter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _entry(slug: str, title: str, summary: str, category: str = "topics") -> NoteEntry:
    return NoteEntry(slug=slug, title=title, summary=summary, category=category)


# ---------------------------------------------------------------------------
# extract_summary
# ---------------------------------------------------------------------------

class ExtractSummaryTests(unittest.TestCase):
    def test_uses_frontmatter_summary_field(self) -> None:
        text = '---\nsummary: "One-line summary."\n---\n\nBody.\n'
        self.assertEqual(extract_summary(text), "One-line summary.")

    def test_uses_frontmatter_summary_without_quotes(self) -> None:
        text = "---\nsummary: Plain summary here.\n---\n\nBody.\n"
        self.assertEqual(extract_summary(text), "Plain summary here.")

    def test_falls_back_to_first_body_sentence(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\nThis is the first prose sentence.\n"
        self.assertEqual(extract_summary(text), "This is the first prose sentence.")

    def test_skips_heading_lines(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n# Heading\n\nReal content here.\n"
        self.assertEqual(extract_summary(text), "Real content here.")

    def test_skips_list_item_lines_dash(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n- List item one\n\nProse follows.\n"
        self.assertEqual(extract_summary(text), "Prose follows.")

    def test_skips_list_item_lines_asterisk(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n* Bullet item\n\nProse follows.\n"
        self.assertEqual(extract_summary(text), "Prose follows.")

    def test_skips_numbered_list_items(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n1. First item\n\nProse follows.\n"
        self.assertEqual(extract_summary(text), "Prose follows.")

    def test_strips_bold_markers(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n**Amazon EKS** is managed Kubernetes.\n"
        result = extract_summary(text)
        self.assertNotIn("**", result)
        self.assertIn("Amazon EKS", result)

    def test_strips_italic_markers(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n*Fargate* removes node management.\n"
        result = extract_summary(text)
        self.assertNotIn("*", result)

    def test_truncates_to_120_chars(self) -> None:
        long_line = "A" * 50 + " " + "B" * 50 + " " + "C" * 50
        text = f"---\ntitle: \"T\"\n---\n\n{long_line}\n"
        result = extract_summary(text)
        self.assertLessEqual(len(result), 120 + 1)  # +1 for ellipsis char

    def test_truncation_does_not_cut_mid_word(self) -> None:
        long_line = " ".join(["word"] * 40)  # well over 120 chars
        text = f"---\ntitle: \"T\"\n---\n\n{long_line}\n"
        result = extract_summary(text)
        # Should end with … or a complete word
        without_ellipsis = result.rstrip("…")
        self.assertFalse(without_ellipsis.endswith("wor") or without_ellipsis.endswith("wo"))

    def test_empty_body_returns_empty_string(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n"
        self.assertEqual(extract_summary(text), "")

    def test_only_headings_in_body_returns_empty(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\n# Heading One\n## Heading Two\n"
        self.assertEqual(extract_summary(text), "")

    def test_no_frontmatter_uses_first_line(self) -> None:
        text = "First line of content.\n\nSecond line.\n"
        self.assertEqual(extract_summary(text), "First line of content.")


# ---------------------------------------------------------------------------
# build_index_text
# ---------------------------------------------------------------------------

class BuildIndexTextTests(unittest.TestCase):
    def _groups(self, **kwargs: list[NoteEntry]) -> dict[str, list[NoteEntry]]:
        base = {"topics": [], "concepts": [], "source_summaries": []}
        base.update(kwargs)
        return base

    def test_contains_index_frontmatter(self) -> None:
        text = build_index_text(self._groups(), "2026-04-11")
        self.assertIn("---", text)
        self.assertIn('note_type: "index"', text)

    def test_frontmatter_has_generated_on(self) -> None:
        text = build_index_text(self._groups(), "2026-04-11")
        self.assertIn('generated_on: "2026-04-11"', text)

    def test_frontmatter_note_count_zero(self) -> None:
        text = build_index_text(self._groups(), "2026-04-11")
        self.assertIn("note_count: 0", text)

    def test_frontmatter_note_count_accurate(self) -> None:
        groups = self._groups(
            topics=[_entry("a", "A", "Summary A"), _entry("b", "B", "Summary B")],
            concepts=[_entry("c", "C", "Summary C", "concepts")],
        )
        text = build_index_text(groups, "2026-04-11")
        self.assertIn("note_count: 3", text)

    def test_topics_section_present_when_non_empty(self) -> None:
        groups = self._groups(topics=[_entry("a", "A", "Summary A")])
        self.assertIn("## Topics", build_index_text(groups, "2026-04-11"))

    def test_concepts_section_present_when_non_empty(self) -> None:
        groups = self._groups(concepts=[_entry("c", "C", "Summary C", "concepts")])
        self.assertIn("## Concepts", build_index_text(groups, "2026-04-11"))

    def test_source_summaries_section_present_when_non_empty(self) -> None:
        groups = self._groups(source_summaries=[_entry("s", "S", "Summary S", "source_summaries")])
        self.assertIn("## Source Summaries", build_index_text(groups, "2026-04-11"))

    def test_empty_category_omits_heading(self) -> None:
        groups = self._groups(topics=[_entry("a", "A", "Summary A")])
        text = build_index_text(groups, "2026-04-11")
        self.assertNotIn("## Concepts", text)
        self.assertNotIn("## Source Summaries", text)

    def test_wikilink_format(self) -> None:
        groups = self._groups(topics=[_entry("aws-containers", "AWS Containers", "EKS guide")])
        self.assertIn("[[aws-containers]]", build_index_text(groups, "2026-04-11"))

    def test_wikilink_uses_slug_not_title(self) -> None:
        groups = self._groups(topics=[_entry("my-slug", "My Full Title", "Summary")])
        text = build_index_text(groups, "2026-04-11")
        self.assertIn("[[my-slug]]", text)
        # Title should not appear as a wikilink
        self.assertNotIn("[[My Full Title]]", text)

    def test_summary_separator(self) -> None:
        groups = self._groups(topics=[_entry("a", "A", "The summary")])
        text = build_index_text(groups, "2026-04-11")
        self.assertIn("[[a]] — The summary", text)

    def test_category_ordering_topics_before_concepts(self) -> None:
        groups = self._groups(
            topics=[_entry("t", "T", "Topic summary")],
            concepts=[_entry("c", "C", "Concept summary", "concepts")],
        )
        text = build_index_text(groups, "2026-04-11")
        self.assertLess(text.index("## Topics"), text.index("## Concepts"))

    def test_all_categories_empty_has_valid_frontmatter(self) -> None:
        text = build_index_text(self._groups(), "2026-04-11")
        self.assertTrue(text.startswith("---"))
        self.assertIn("note_count: 0", text)
        self.assertNotIn("## Topics", text)

    def test_entry_without_summary_omits_separator(self) -> None:
        groups = self._groups(topics=[_entry("a", "A", "")])
        text = build_index_text(groups, "2026-04-11")
        self.assertIn("[[a]]", text)
        self.assertNotIn("[[a]] — ", text)


# ---------------------------------------------------------------------------
# _load_note_entries
# ---------------------------------------------------------------------------

class LoadNoteEntriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_loads_topics(self) -> None:
        _write(self.root, "compiled/topics/my-topic.md", '---\ntitle: "My Topic"\n---\n\nBody.\n')
        groups = _load_note_entries(self.root)
        self.assertEqual(len(groups["topics"]), 1)
        self.assertEqual(groups["topics"][0].slug, "my-topic")

    def test_loads_concepts(self) -> None:
        _write(self.root, "compiled/concepts/my-concept.md", '---\ntitle: "Concept"\n---\n\nBody.\n')
        groups = _load_note_entries(self.root)
        self.assertEqual(len(groups["concepts"]), 1)

    def test_loads_source_summaries(self) -> None:
        _write(self.root, "compiled/source_summaries/my-summary.md", "Summary body.\n")
        groups = _load_note_entries(self.root)
        self.assertEqual(len(groups["source_summaries"]), 1)

    def test_skips_index_md(self) -> None:
        _write(self.root, "compiled/topics/index.md", "# Wiki Index\n")
        _write(self.root, "compiled/topics/real-topic.md", "Real content.\n")
        groups = _load_note_entries(self.root)
        slugs = [e.slug for e in groups["topics"]]
        self.assertNotIn("index", slugs)
        self.assertIn("real-topic", slugs)

    def test_missing_dir_returns_empty_list_for_category(self) -> None:
        # Only create topics dir
        (self.root / "compiled" / "topics").mkdir(parents=True)
        groups = _load_note_entries(self.root)
        self.assertEqual(groups["concepts"], [])
        self.assertEqual(groups["source_summaries"], [])

    def test_note_entry_slug_is_stem(self) -> None:
        _write(self.root, "compiled/topics/aws-containers.md", "Body.\n")
        groups = _load_note_entries(self.root)
        self.assertEqual(groups["topics"][0].slug, "aws-containers")

    def test_note_entry_title_from_frontmatter(self) -> None:
        _write(self.root, "compiled/topics/note.md", '---\ntitle: "My Custom Title"\n---\n\nBody.\n')
        groups = _load_note_entries(self.root)
        self.assertEqual(groups["topics"][0].title, "My Custom Title")

    def test_note_entry_title_fallback_from_stem(self) -> None:
        _write(self.root, "compiled/topics/my-note.md", "No frontmatter.\n")
        groups = _load_note_entries(self.root)
        self.assertEqual(groups["topics"][0].title, "My Note")

    def test_note_entry_category_set_correctly(self) -> None:
        _write(self.root, "compiled/concepts/the-concept.md", "Body.\n")
        groups = _load_note_entries(self.root)
        self.assertEqual(groups["concepts"][0].category, "concepts")


# ---------------------------------------------------------------------------
# run() integration
# ---------------------------------------------------------------------------

class RunIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ["compiled/topics", "compiled/concepts", "compiled/source_summaries"]:
            (self.root / d).mkdir(parents=True)
        _write(self.root, "compiled/topics/aws-containers.md",
               '---\ntitle: "AWS Containers"\n---\n\nEKS vs ECS vs Fargate.\n')
        _write(self.root, "compiled/topics/openclaw.md",
               '---\ntitle: "OpenClaw"\n---\n\nSecurity guide.\n')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_run_creates_index_file(self) -> None:
        rc = run(self.root)
        self.assertEqual(rc, 0)
        self.assertTrue((self.root / "compiled" / "index.md").exists())

    def test_run_returns_zero(self) -> None:
        self.assertEqual(run(self.root), 0)

    def test_index_file_has_frontmatter(self) -> None:
        run(self.root)
        content = (self.root / "compiled" / "index.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---"))

    def test_index_file_contains_wikilinks(self) -> None:
        run(self.root)
        content = (self.root / "compiled" / "index.md").read_text(encoding="utf-8")
        self.assertIn("[[aws-containers]]", content)
        self.assertIn("[[openclaw]]", content)

    def test_run_updates_existing_index(self) -> None:
        run(self.root)
        _write(self.root, "compiled/topics/new-topic.md", '---\ntitle: "New"\n---\n\nNew content.\n')
        run(self.root)
        content = (self.root / "compiled" / "index.md").read_text(encoding="utf-8")
        self.assertIn("[[new-topic]]", content)

    def test_run_returns_one_when_compiled_dir_missing(self) -> None:
        import shutil
        shutil.rmtree(self.root / "compiled")
        rc = run(self.root)
        self.assertEqual(rc, 1)

    def test_index_not_included_in_its_own_listing(self) -> None:
        # Pre-create an index.md to verify it is excluded from the re-generated index
        _write(self.root, "compiled/index.md", "# Old Index\n")
        run(self.root)
        content = (self.root / "compiled" / "index.md").read_text(encoding="utf-8")
        self.assertNotIn("[[index]]", content)


# ---------------------------------------------------------------------------
# run() dry-run
# ---------------------------------------------------------------------------

class RunDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "compiled" / "topics").mkdir(parents=True)
        _write(self.root, "compiled/topics/my-note.md", "Body text.\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_dry_run_does_not_write_file(self) -> None:
        run(self.root, dry_run=True)
        self.assertFalse((self.root / "compiled" / "index.md").exists())

    def test_dry_run_returns_zero(self) -> None:
        self.assertEqual(run(self.root, dry_run=True), 0)

    def test_dry_run_outputs_markdown(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(self.root, dry_run=True)
        output = buf.getvalue()
        self.assertIn("---", output)
        self.assertIn("note_type", output)


# ---------------------------------------------------------------------------
# run() JSON
# ---------------------------------------------------------------------------

class RunJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "compiled" / "topics").mkdir(parents=True)
        _write(self.root, "compiled/topics/my-note.md",
               '---\ntitle: "My Note"\n---\n\nBody text.\n')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_json_output_is_valid(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(self.root, as_json=True)
        parsed = json.loads(buf.getvalue().strip())
        self.assertIsInstance(parsed, dict)

    def test_json_output_has_expected_keys(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(self.root, as_json=True)
        parsed = json.loads(buf.getvalue().strip())
        for key in ["topics", "concepts", "source_summaries"]:
            self.assertIn(key, parsed)

    def test_json_does_not_write_file(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(self.root, as_json=True)
        self.assertFalse((self.root / "compiled" / "index.md").exists())

    def test_json_entries_have_expected_fields(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(self.root, as_json=True)
        parsed = json.loads(buf.getvalue().strip())
        entry = parsed["topics"][0]
        for field in ["slug", "title", "summary", "category"]:
            self.assertIn(field, entry)


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts/inject_wikilinks.py (Phase 2A-3)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.inject_wikilinks import (
    _in_zone,
    _is_approved,
    _mark_no_inject_zones,
    _should_annotate,
    _slug_to_display,
    _split_frontmatter,
    annotate_note,
    inject_wikilinks_into_body,
    load_known_targets,
    run,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _concept_note(root: Path, stem: str) -> Path:
    content = (
        '---\ntitle: "' + stem + '"\nnote_type: concept\n---\n\n'
        "This is the concept definition.\n"
    )
    return _write(root, "compiled/concepts/" + stem + ".md", content)


def _topic_note(root: Path, stem: str, body: str) -> Path:
    content = '---\ntitle: "' + stem + '"\nnote_type: topic\napproved: true\n---\n\n' + body
    return _write(root, "compiled/topics/" + stem + ".md", content)


def _raw_article(root: Path, stem: str, body: str, approved: bool = True) -> Path:
    flag = "true" if approved else "false"
    content = '---\ntitle: "' + stem + '"\napproved: ' + flag + '\n---\n\n' + body
    return _write(root, "raw/articles/" + stem + ".md", content)


# ---------------------------------------------------------------------------
# _slug_to_display
# ---------------------------------------------------------------------------

class SlugToDisplayTests(unittest.TestCase):
    def test_hyphens_to_spaces(self) -> None:
        self.assertEqual(_slug_to_display("zero-trust"), "zero trust")

    def test_underscores_to_spaces(self) -> None:
        self.assertEqual(_slug_to_display("large_language_model"), "large language model")

    def test_lowercases(self) -> None:
        self.assertEqual(_slug_to_display("LLM"), "llm")

    def test_no_change_needed(self) -> None:
        self.assertEqual(_slug_to_display("transformer"), "transformer")


# ---------------------------------------------------------------------------
# load_known_targets
# ---------------------------------------------------------------------------

class LoadKnownTargetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_loads_concepts(self) -> None:
        _concept_note(self.root, "zero-trust")
        targets = load_known_targets(self.root)
        self.assertIn("zero trust", targets)
        self.assertEqual(targets["zero trust"], "zero-trust")

    def test_loads_slug_form_as_well(self) -> None:
        _concept_note(self.root, "zero-trust")
        targets = load_known_targets(self.root)
        self.assertIn("zero-trust", targets)

    def test_loads_entities_dir(self) -> None:
        _write(self.root, "compiled/entities/ollama.md",
               '---\ntitle: Ollama\nnote_type: entity\n---\n\nOllama is a tool.\n')
        targets = load_known_targets(self.root)
        self.assertIn("ollama", targets)

    def test_empty_dirs(self) -> None:
        targets = load_known_targets(self.root)
        self.assertEqual(targets, {})


# ---------------------------------------------------------------------------
# _split_frontmatter
# ---------------------------------------------------------------------------

class SplitFrontmatterTests(unittest.TestCase):
    def test_splits_correctly(self) -> None:
        text = "---\ntitle: T\n---\n\nBody here."
        fm, body = _split_frontmatter(text)
        self.assertIn("title: T", fm)
        self.assertIn("Body here.", body)

    def test_no_frontmatter(self) -> None:
        text = "Just body text."
        fm, body = _split_frontmatter(text)
        self.assertEqual(fm, "")
        self.assertEqual(body, "Just body text.")


# ---------------------------------------------------------------------------
# _is_approved
# ---------------------------------------------------------------------------

class IsApprovedTests(unittest.TestCase):
    def test_approved_true(self) -> None:
        text = "---\napproved: true\n---\n\nBody."
        self.assertTrue(_is_approved(text))

    def test_approved_false(self) -> None:
        text = "---\napproved: false\n---\n\nBody."
        self.assertFalse(_is_approved(text))

    def test_no_approved_field(self) -> None:
        text = "---\ntitle: T\n---\n\nBody."
        self.assertFalse(_is_approved(text))


# ---------------------------------------------------------------------------
# _mark_no_inject_zones
# ---------------------------------------------------------------------------

class MarkNoInjectZonesTests(unittest.TestCase):
    def test_existing_wikilinks_are_zones(self) -> None:
        body = "See [[existing-link]] for details."
        zones = _mark_no_inject_zones(body)
        # Should have at least one zone covering the wikilink
        self.assertTrue(any(body[s:e] == "[[existing-link]]" for s, e in zones))

    def test_code_block_is_zone(self) -> None:
        body = "Before.\n```\ncode here\n```\nAfter."
        zones = _mark_no_inject_zones(body)
        self.assertTrue(len(zones) > 0)

    def test_inline_code_is_zone(self) -> None:
        body = "Use `some_function()` here."
        zones = _mark_no_inject_zones(body)
        self.assertTrue(len(zones) > 0)

    def test_heading_is_zone(self) -> None:
        body = "# My Heading\n\nParagraph text."
        zones = _mark_no_inject_zones(body)
        self.assertTrue(any(body[s:e].startswith("#") for s, e in zones))


# ---------------------------------------------------------------------------
# _in_zone
# ---------------------------------------------------------------------------

class InZoneTests(unittest.TestCase):
    def test_inside_zone(self) -> None:
        zones = [(10, 20)]
        self.assertTrue(_in_zone(12, 18, zones))

    def test_outside_zone(self) -> None:
        zones = [(10, 20)]
        self.assertFalse(_in_zone(25, 30, zones))

    def test_overlaps_zone(self) -> None:
        zones = [(10, 20)]
        self.assertTrue(_in_zone(15, 25, zones))

    def test_adjacent_not_in_zone(self) -> None:
        zones = [(10, 20)]
        self.assertFalse(_in_zone(20, 25, zones))


# ---------------------------------------------------------------------------
# inject_wikilinks_into_body
# ---------------------------------------------------------------------------

class InjectWikilinksIntoBodyTests(unittest.TestCase):
    def test_basic_injection(self) -> None:
        body = "The transformer model is powerful.\n"
        targets = {"transformer": "transformer"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        self.assertIn("[[transformer]]", new_body)
        self.assertEqual(len(injections), 1)
        self.assertEqual(injections[0][2], "transformer")

    def test_first_occurrence_only(self) -> None:
        body = "transformer is great. transformer is also fast.\n"
        targets = {"transformer": "transformer"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        self.assertEqual(new_body.count("[[transformer]]"), 1)
        self.assertEqual(len(injections), 1)

    def test_does_not_inject_inside_existing_link(self) -> None:
        body = "See [[transformer]] which is a transformer model.\n"
        targets = {"transformer": "transformer"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        # First mention is inside existing [[...]] — skip (already linked).
        # Second mention "transformer model" is injected.
        # Result has exactly 2 [[transformer]] (original + new injection)
        self.assertEqual(new_body.count("[[transformer]]"), 2)

    def test_does_not_inject_in_heading(self) -> None:
        body = "# Transformer Overview\n\nThe transformer is the key architecture.\n"
        targets = {"transformer": "transformer"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        # First mention is in heading (zone) → skipped.
        # Second mention in body paragraph → injected.
        self.assertIn("[[transformer]]", new_body)
        # Heading should NOT contain [[
        heading_line = new_body.splitlines()[0]
        self.assertNotIn("[[", heading_line)

    def test_does_not_inject_in_inline_code(self) -> None:
        body = "Use `transformer` here. The transformer model is fast.\n"
        targets = {"transformer": "transformer"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        # inline code match is skipped; plain text match is injected
        self.assertIn("[[transformer]]", new_body)
        # The backtick span should remain unchanged
        self.assertIn("`transformer`", new_body)

    def test_case_insensitive_match(self) -> None:
        body = "The Transformer architecture changed NLP.\n"
        targets = {"transformer": "transformer"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        self.assertIn("[[transformer]]", new_body)

    def test_hyphenated_slug_match(self) -> None:
        body = "The zero-trust model assumes breach.\n"
        targets = {"zero trust": "zero-trust", "zero-trust": "zero-trust"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        self.assertIn("[[zero-trust]]", new_body)
        self.assertEqual(len(injections), 1)

    def test_no_targets_no_injection(self) -> None:
        body = "Some text here.\n"
        new_body, injections = inject_wikilinks_into_body(body, {})
        self.assertEqual(new_body, body)
        self.assertEqual(injections, [])

    def test_multiple_different_targets(self) -> None:
        body = "Both transformer and attention are important.\n"
        targets = {"transformer": "transformer", "attention": "attention"}
        new_body, injections = inject_wikilinks_into_body(body, targets)
        self.assertIn("[[transformer]]", new_body)
        self.assertIn("[[attention]]", new_body)
        self.assertEqual(len(injections), 2)

    def test_line_number_reported(self) -> None:
        body = "Line one.\nLine two with transformer here.\n"
        targets = {"transformer": "transformer"}
        _, injections = inject_wikilinks_into_body(body, targets)
        self.assertEqual(injections[0][1], 2)  # line 2


# ---------------------------------------------------------------------------
# annotate_note
# ---------------------------------------------------------------------------

class AnnotateNoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_annotates_topic_note(self) -> None:
        _concept_note(self.root, "transformer")
        path = _topic_note(self.root, "ml", "The transformer model is key.\n")
        targets = load_known_targets(self.root)
        injections = annotate_note(path, targets, dry_run=False, root=self.root)
        self.assertEqual(len(injections), 1)
        self.assertIn("[[transformer]]", path.read_text())

    def test_dry_run_does_not_modify(self) -> None:
        _concept_note(self.root, "transformer")
        path = _topic_note(self.root, "ml", "The transformer model is key.\n")
        original = path.read_text()
        targets = load_known_targets(self.root)
        annotate_note(path, targets, dry_run=True, root=self.root)
        self.assertEqual(original, path.read_text())

    def test_frontmatter_not_modified(self) -> None:
        _concept_note(self.root, "transformer")
        path = _topic_note(self.root, "ml", "The transformer model is key.\n")
        targets = load_known_targets(self.root)
        annotate_note(path, targets, dry_run=False, root=self.root)
        result = path.read_text()
        self.assertTrue(result.startswith("---\n"))
        self.assertIn('title: "ml"', result)

    def test_returns_empty_if_no_matches(self) -> None:
        _concept_note(self.root, "transformer")
        path = _topic_note(self.root, "ml", "No matching concepts here.\n")
        targets = load_known_targets(self.root)
        injections = annotate_note(path, targets, dry_run=False, root=self.root)
        self.assertEqual(injections, [])


# ---------------------------------------------------------------------------
# _should_annotate
# ---------------------------------------------------------------------------

class ShouldAnnotateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_topic_note_eligible(self) -> None:
        path = _topic_note(self.root, "ml", "Body.")
        self.assertTrue(_should_annotate(path, self.root))

    def test_approved_raw_article_eligible(self) -> None:
        path = _raw_article(self.root, "article", "Body.", approved=True)
        self.assertTrue(_should_annotate(path, self.root))

    def test_unapproved_raw_article_not_eligible(self) -> None:
        path = _raw_article(self.root, "article", "Body.", approved=False)
        self.assertFalse(_should_annotate(path, self.root))

    def test_concept_note_not_eligible(self) -> None:
        path = _concept_note(self.root, "transformer")
        self.assertFalse(_should_annotate(path, self.root))


# ---------------------------------------------------------------------------
# run (integration)
# ---------------------------------------------------------------------------

class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_run_dry_run_no_changes(self) -> None:
        _concept_note(self.root, "transformer")
        path = _topic_note(self.root, "ml", "The transformer model is key.\n")
        original = path.read_text()
        run(self.root, dry_run=True, note_path=None, no_commit=True)
        self.assertEqual(original, path.read_text())

    def test_run_injects_into_topic(self) -> None:
        _concept_note(self.root, "transformer")
        path = _topic_note(self.root, "ml", "The transformer model is key.\n")
        run(self.root, dry_run=False, note_path=None, no_commit=True)
        self.assertIn("[[transformer]]", path.read_text())

    def test_run_single_note(self) -> None:
        _concept_note(self.root, "transformer")
        path = _topic_note(self.root, "ml", "The transformer model is key.\n")
        other = _topic_note(self.root, "other", "The transformer appears here too.\n")
        run(self.root, dry_run=False, note_path=path, no_commit=True)
        # Only the specified note was annotated
        self.assertIn("[[transformer]]", path.read_text())
        self.assertNotIn("[[transformer]]", other.read_text())

    def test_run_no_targets(self) -> None:
        path = _topic_note(self.root, "ml", "The transformer model is key.\n")
        # No concepts directory — should exit cleanly with code 0
        result = run(self.root, dry_run=False, note_path=None, no_commit=True)
        self.assertEqual(result, 0)
        self.assertNotIn("[[", path.read_text())


if __name__ == "__main__":
    unittest.main()

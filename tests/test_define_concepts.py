"""Tests for scripts/define_concepts.py (Phase 2A-2)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.define_concepts import (
    MIN_SOURCE_EXCERPTS,
    _build_definition_prompt,
    _count_sentences,
    _find_source_excerpts,
    _inject_frontmatter_fields,
    _slug_to_name,
    _split_frontmatter_raw,
    _whole_word_pattern,
    _write_definition,
    process_stubs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _stub_note(stem: str) -> str:
    return (
        f'---\ntitle: "{stem}"\nnote_type: concept\ngeneration_method: stub\n---\n\n'
        "_Stub page._\n\n## Mentioned In\n\n## Related Concepts\n"
    )


def _rich_note(stem: str) -> str:
    return (
        '---\ntitle: "' + stem + '"\nnote_type: concept\ngeneration_method: ollama_local\n---\n\n'
        "Rich content line one.\nRich content line two.\nRich content line three.\n"
    )


def _summary(stem: str, approved: bool = True, content: str = "") -> str:
    body = content or f"This discusses {stem} in detail. More text here."
    flag = "true" if approved else "false"
    return f"---\ntitle: {stem}\napproved: {flag}\n---\n\n{body}\n"


# ---------------------------------------------------------------------------
# _split_frontmatter_raw
# ---------------------------------------------------------------------------

class SplitFrontmatterRawTests(unittest.TestCase):
    def test_splits_correctly(self) -> None:
        text = "---\ntitle: T\n---\n\nBody."
        fm, body = _split_frontmatter_raw(text)
        self.assertTrue(fm.startswith("---\n"))
        self.assertIn("title: T", fm)
        self.assertEqual(body.strip(), "Body.")

    def test_no_frontmatter(self) -> None:
        text = "Just body."
        fm, body = _split_frontmatter_raw(text)
        self.assertEqual(fm, "")
        self.assertEqual(body, "Just body.")


# ---------------------------------------------------------------------------
# _inject_frontmatter_fields
# ---------------------------------------------------------------------------

class InjectFrontmatterFieldsTests(unittest.TestCase):
    def test_injects_string_field(self) -> None:
        text = "---\ntitle: T\n---\n\nBody."
        result = _inject_frontmatter_fields(text, {"generated_by": "ollama-concept-definition"})
        self.assertIn("generated_by:", result)
        self.assertIn("ollama-concept-definition", result)
        self.assertIn("Body.", result)

    def test_injects_list_field(self) -> None:
        text = "---\ntitle: T\n---\n\nBody."
        result = _inject_frontmatter_fields(text, {"definition_sources": ["src-a", "src-b"]})
        self.assertIn("definition_sources:", result)
        self.assertIn("  - src-a", result)
        self.assertIn("  - src-b", result)

    def test_preserves_existing_fields(self) -> None:
        text = "---\ntitle: My Title\nslug: my-slug\n---\n\nBody."
        result = _inject_frontmatter_fields(text, {"new_field": "value"})
        self.assertIn("title: My Title", result)
        self.assertIn("slug: my-slug", result)

    def test_body_preserved(self) -> None:
        text = "---\ntitle: T\n---\n\nOriginal body content.\n"
        result = _inject_frontmatter_fields(text, {"x": "y"})
        self.assertIn("Original body content.", result)

    def test_empty_fields_skipped(self) -> None:
        text = "---\ntitle: T\n---\n\nBody."
        result = _inject_frontmatter_fields(text, {"empty_list": [], "empty_str": ""})
        self.assertNotIn("empty_list", result)
        self.assertNotIn("empty_str", result)


# ---------------------------------------------------------------------------
# _whole_word_pattern
# ---------------------------------------------------------------------------

class WholeWordPatternTests(unittest.TestCase):
    def test_matches_whole_word(self) -> None:
        pattern = _whole_word_pattern("transformer")
        self.assertIsNotNone(pattern.search("The transformer model is used here."))

    def test_does_not_match_partial(self) -> None:
        pattern = _whole_word_pattern("form")
        self.assertIsNone(pattern.search("transformer"))

    def test_case_insensitive(self) -> None:
        pattern = _whole_word_pattern("LLM")
        self.assertIsNotNone(pattern.search("An llm is a large model."))


# ---------------------------------------------------------------------------
# _find_source_excerpts
# ---------------------------------------------------------------------------

class FindSourceExcerptsTests(unittest.TestCase):
    def test_finds_matching_source(self) -> None:
        sources = {
            "src-a": "---\napproved: true\n---\n\nThis discusses transformers in detail. " * 5,
            "src-b": "---\napproved: true\n---\n\nNothing relevant here.",
        }
        excerpts = _find_source_excerpts("transformers", sources)
        self.assertEqual(len(excerpts), 1)
        self.assertEqual(excerpts[0][0], "src-a")

    def test_returns_up_to_max(self) -> None:
        sources = {f"src-{i}": f"Content about concept here, more content." for i in range(10)}
        excerpts = _find_source_excerpts("concept", sources, max_excerpts=3)
        self.assertLessEqual(len(excerpts), 3)

    def test_excerpt_contains_context(self) -> None:
        sources = {"src-a": "---\n---\n\n" + "A" * 100 + " keyword " + "B" * 100}
        excerpts = _find_source_excerpts("keyword", sources)
        self.assertEqual(len(excerpts), 1)
        self.assertIn("keyword", excerpts[0][1])

    def test_no_match(self) -> None:
        sources = {"src-a": "Nothing about the concept here."}
        excerpts = _find_source_excerpts("xyznomatch", sources)
        self.assertEqual(excerpts, [])


# ---------------------------------------------------------------------------
# _count_sentences
# ---------------------------------------------------------------------------

class CountSentencesTests(unittest.TestCase):
    def test_single_sentence(self) -> None:
        self.assertEqual(_count_sentences("This is one sentence."), 1)

    def test_two_sentences(self) -> None:
        self.assertEqual(_count_sentences("First sentence. Second sentence."), 2)

    def test_question_and_exclamation(self) -> None:
        self.assertEqual(_count_sentences("Really? Yes! Absolutely."), 3)

    def test_empty_string(self) -> None:
        self.assertEqual(_count_sentences(""), 0)

    def test_multiline(self) -> None:
        text = "Line one.\nLine two.\nLine three."
        self.assertEqual(_count_sentences(text), 3)


# ---------------------------------------------------------------------------
# _slug_to_name
# ---------------------------------------------------------------------------

class SlugToNameTests(unittest.TestCase):
    def test_hyphen_to_space(self) -> None:
        self.assertEqual(_slug_to_name("zero-trust"), "zero trust")

    def test_underscore_to_space(self) -> None:
        self.assertEqual(_slug_to_name("large_language_model"), "large language model")

    def test_single_word(self) -> None:
        self.assertEqual(_slug_to_name("transformer"), "transformer")


# ---------------------------------------------------------------------------
# _build_definition_prompt
# ---------------------------------------------------------------------------

class BuildDefinitionPromptTests(unittest.TestCase):
    def test_includes_concept_name(self) -> None:
        excerpts = [("src-a", "Some excerpt text.")]
        prompt = _build_definition_prompt("zero trust", excerpts)
        self.assertIn("zero trust", prompt)

    def test_includes_excerpt_text(self) -> None:
        excerpts = [("src-a", "Specific excerpt content here.")]
        prompt = _build_definition_prompt("concept", excerpts)
        self.assertIn("Specific excerpt content here.", prompt)

    def test_multiple_excerpts(self) -> None:
        excerpts = [("src-a", "Excerpt A."), ("src-b", "Excerpt B.")]
        prompt = _build_definition_prompt("concept", excerpts)
        self.assertIn("src-a", prompt)
        self.assertIn("src-b", prompt)


# ---------------------------------------------------------------------------
# _write_definition
# ---------------------------------------------------------------------------

class WriteDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_writes_definition_to_body(self) -> None:
        path = _write(self.root, "concepts/zero-trust.md", _stub_note("zero-trust"))
        _write_definition(path, "Zero trust is a security model.", ["src-a"])
        result = path.read_text()
        self.assertIn("Zero trust is a security model.", result)

    def test_injects_generated_by_field(self) -> None:
        path = _write(self.root, "concepts/zero-trust.md", _stub_note("zero-trust"))
        _write_definition(path, "A definition.", ["src-a"])
        result = path.read_text()
        self.assertIn("generated_by", result)
        self.assertIn("ollama-concept-definition", result)

    def test_injects_definition_sources(self) -> None:
        path = _write(self.root, "concepts/zero-trust.md", _stub_note("zero-trust"))
        _write_definition(path, "A definition.", ["src-a", "src-b"])
        result = path.read_text()
        self.assertIn("definition_sources:", result)
        self.assertIn("src-a", result)
        self.assertIn("src-b", result)

    def test_preserves_existing_frontmatter(self) -> None:
        text = "---\ntitle: Zero Trust\nslug: zero-trust\ngeneration_method: stub\n---\n\n_Stub._\n"
        path = _write(self.root, "concepts/zero-trust.md", text)
        _write_definition(path, "A definition.", ["src-a"])
        result = path.read_text()
        self.assertIn("title: Zero Trust", result)
        self.assertIn("slug: zero-trust", result)


# ---------------------------------------------------------------------------
# process_stubs (integration with mocked Ollama)
# ---------------------------------------------------------------------------

class ProcessStubsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _concept(self, stem: str, stub: bool = True) -> Path:
        content = _stub_note(stem) if stub else _rich_note(stem)
        return _write(self.root, "compiled/concepts/" + stem + ".md", content)

    def _source(self, stem: str, body: str = "", approved: bool = True) -> None:
        _write(
            self.root,
            "compiled/source_summaries/" + stem + ".md",
            _summary(stem, approved, body),
        )

    def test_dry_run_no_file_changes(self) -> None:
        self._concept("zero-trust")
        original = (self.root / "compiled/concepts/zero-trust.md").read_text()
        self._source("src-a", "zero-trust is a security model used here.")
        self._source("src-b", "zero-trust architecture eliminates implicit trust.")

        with patch("scripts.define_concepts.call_ollama") as mock_ollama:
            mock_ollama.return_value = "A definition."
            process_stubs(self.root, "qwen2.5:14b", dry_run=True,
                          concept_filter=None, limit=None, no_commit=True)

        result = (self.root / "compiled/concepts/zero-trust.md").read_text()
        self.assertEqual(original, result)
        mock_ollama.assert_not_called()

    def test_skips_non_stubs(self) -> None:
        self._concept("rich-note", stub=False)
        self._source("src-a", "rich-note is a well-documented topic.")
        self._source("src-b", "rich-note is discussed extensively.")

        with patch("scripts.define_concepts._check_model_available"):
            with patch("scripts.define_concepts.call_ollama") as mock_ollama:
                mock_ollama.return_value = "A definition. Second sentence."
                process_stubs(self.root, "qwen2.5:14b", dry_run=False,
                              concept_filter=None, limit=None, no_commit=True)

        mock_ollama.assert_not_called()

    def test_skips_with_too_few_sources(self) -> None:
        self._concept("rare-concept")
        self._source("src-a", "Something unrelated.")  # no match for "rare concept"

        with patch("scripts.define_concepts._check_model_available"):
            with patch("scripts.define_concepts.call_ollama") as mock_ollama:
                process_stubs(self.root, "qwen2.5:14b", dry_run=False,
                              concept_filter=None, limit=None, no_commit=True)

        mock_ollama.assert_not_called()

    def test_writes_definition_when_sources_found(self) -> None:
        self._concept("zero-trust")
        self._source("src-a", "zero-trust is a security model used in enterprise.")
        self._source("src-b", "zero-trust architecture assumes breach by default.")

        with patch("scripts.define_concepts._check_model_available"):
            with patch("scripts.define_concepts.call_ollama") as mock_ollama:
                mock_ollama.return_value = (
                    "Zero trust is a security model. "
                    "It assumes breach by default. "
                    "It requires strict verification."
                )
                process_stubs(self.root, "qwen2.5:14b", dry_run=False,
                              concept_filter=None, limit=None, no_commit=True)

        result = (self.root / "compiled/concepts/zero-trust.md").read_text()
        self.assertIn("Zero trust is a security model.", result)
        self.assertIn("generated_by", result)

    def test_limit_restricts_count(self) -> None:
        for i in range(5):
            self._concept(f"concept-{i}")
        for i in range(5):
            self._source(f"src-{i}-a", f"concept {i} is described here in context.")
            self._source(f"src-{i}-b", f"concept {i} has important properties.")

        called_count = 0

        def _fake_ollama(prompt: str, model: str) -> str:
            nonlocal called_count
            called_count += 1
            return "A definition sentence. Second sentence. Third sentence."

        with patch("scripts.define_concepts._check_model_available"):
            with patch("scripts.define_concepts.call_ollama", side_effect=_fake_ollama):
                process_stubs(self.root, "qwen2.5:14b", dry_run=False,
                              concept_filter=None, limit=2, no_commit=True)

        self.assertLessEqual(called_count, 2)

    def test_skips_bad_llm_output_too_short(self) -> None:
        self._concept("short-output")
        self._source("src-a", "short-output is a concept used in systems.")
        self._source("src-b", "short-output has multiple applications in practice.")

        path = self.root / "compiled/concepts/short-output.md"
        original = path.read_text()

        with patch("scripts.define_concepts._check_model_available"):
            with patch("scripts.define_concepts.call_ollama") as mock_ollama:
                mock_ollama.return_value = ""  # empty — 0 sentences → skip
                process_stubs(self.root, "qwen2.5:14b", dry_run=False,
                              concept_filter=None, limit=None, no_commit=True)

        self.assertEqual(original, path.read_text())


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts/concept_aggregator.py (Phase 13)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.concept_aggregator import (
    _already_extracted,
    _append_mentioned_in,
    _parse_sources_from_note,
    _slugify,
    _update_registry_entry,
    build_concept_note,
    build_entity_note,
    build_extraction_prompt,
    extract_concepts_and_entities,
    load_registry,
    save_registry,
    _parse_extraction_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_summary(approved: bool = True, body: str = "# Summary\n\nTest content.") -> str:
    approved_val = "true" if approved else "false"
    return (
        f"---\n"
        f'title: "Test Source"\n'
        f"note_type: source_summary\n"
        f"approved: {approved_val}\n"
        f"---\n\n"
        f"{body}"
    )


def _make_concept_note(
    slug: str = "zero-trust",
    title: str = "Zero Trust",
    sources: list[str] | None = None,
    date_compiled: str = "2026-04-01",
) -> str:
    sources = sources or ["existing-source-synthesis"]
    sources_lines = "\n".join(f"  - {s}" for s in sources)
    return (
        f"---\n"
        f'title: "{title}"\n'
        f"note_type: concept\n"
        f"slug: {slug}\n"
        f'date_compiled: "{date_compiled}"\n'
        f'date_updated: "{date_compiled}"\n'
        f"sources:\n{sources_lines}\n"
        f"approved: true\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"Existing definition.\n\n"
        f"## Mentioned In\n\n"
        f"- [[existing-source-synthesis]] — it was mentioned here\n\n"
        f"## Related Concepts\n"
    )


# ---------------------------------------------------------------------------
# SlugifyTests
# ---------------------------------------------------------------------------

class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_slugify("zero trust"), "zero-trust")

    def test_uppercase(self):
        self.assertEqual(_slugify("RAG"), "rag")

    def test_already_slug(self):
        self.assertEqual(_slugify("zero-trust"), "zero-trust")

    def test_special_chars(self):
        self.assertEqual(_slugify("C++ Programming!"), "c-programming")

    def test_multiple_spaces(self):
        self.assertEqual(_slugify("retrieval  augmented generation"), "retrieval-augmented-generation")

    def test_leading_trailing_hyphens(self):
        self.assertEqual(_slugify("  hello world  "), "hello-world")


# ---------------------------------------------------------------------------
# ParseExtractionJsonTests
# ---------------------------------------------------------------------------

class ParseExtractionJsonTests(unittest.TestCase):
    def test_valid_object(self):
        raw = '{"concepts": [{"slug": "rag", "title": "RAG", "context": "used here"}], "entities": []}'
        result = _parse_extraction_json(raw)
        self.assertEqual(len(result["concepts"]), 1)
        self.assertEqual(result["concepts"][0]["slug"], "rag")
        self.assertEqual(result["entities"], [])

    def test_json_in_fences(self):
        raw = '```json\n{"concepts": [], "entities": [{"slug": "ollama", "title": "Ollama", "entity_type": "tool", "context": "used"}]}\n```'
        result = _parse_extraction_json(raw)
        self.assertEqual(len(result["entities"]), 1)

    def test_plain_text_returns_empty(self):
        result = _parse_extraction_json("Here are some concepts: RAG, BM25.")
        self.assertEqual(result, {"concepts": [], "entities": []})

    def test_partial_json_returns_empty(self):
        result = _parse_extraction_json('{"concepts": [')
        self.assertEqual(result, {"concepts": [], "entities": []})

    def test_missing_concepts_key(self):
        result = _parse_extraction_json('{"entities": []}')
        self.assertEqual(result["concepts"], [])

    def test_empty_arrays_valid(self):
        result = _parse_extraction_json('{"concepts": [], "entities": []}')
        self.assertEqual(result["concepts"], [])
        self.assertEqual(result["entities"], [])

    def test_non_list_concepts_normalised(self):
        result = _parse_extraction_json('{"concepts": "not a list", "entities": []}')
        self.assertEqual(result["concepts"], [])


# ---------------------------------------------------------------------------
# BuildExtractionPromptTests
# ---------------------------------------------------------------------------

class BuildExtractionPromptTests(unittest.TestCase):
    def test_source_text_in_prompt(self):
        prompt = build_extraction_prompt("My unique source content 12345")
        self.assertIn("My unique source content 12345", prompt)

    def test_keywords_present(self):
        prompt = build_extraction_prompt("x")
        self.assertIn("concepts", prompt.lower())
        self.assertIn("entities", prompt.lower())

    def test_json_schema_in_prompt(self):
        prompt = build_extraction_prompt("x")
        self.assertIn('"slug"', prompt)
        self.assertIn('"context"', prompt)
        self.assertIn("entity_type", prompt)


# ---------------------------------------------------------------------------
# BuildConceptNoteTests
# ---------------------------------------------------------------------------

class BuildConceptNoteTests(unittest.TestCase):
    def test_new_note_frontmatter(self):
        note = build_concept_note(
            existing_text=None,
            slug="zero-trust",
            title="Zero Trust",
            source_stem="my-article-synthesis",
            context="discussed extensively",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertIn("note_type: concept", note)
        self.assertIn("slug: zero-trust", note)
        self.assertIn("date_compiled: 2026-04-21", note)
        self.assertIn("approved: true", note)
        self.assertIn("my-article-synthesis", note)

    def test_new_note_mentioned_in(self):
        note = build_concept_note(
            existing_text=None,
            slug="rag",
            title="RAG",
            source_stem="source-one-synthesis",
            context="core technique",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertIn("## Mentioned In", note)
        self.assertIn("[[source-one-synthesis]]", note)
        self.assertIn("core technique", note)

    def test_new_note_scaffold(self):
        note = build_concept_note(
            existing_text=None,
            slug="rag",
            title="RAG",
            source_stem="src",
            context="ctx",
            generation_method="scaffold",
            today="2026-04-21",
        )
        self.assertIn('"scaffold"', note)

    def test_update_existing_appends_source(self):
        existing = _make_concept_note(slug="zero-trust", sources=["old-source"])
        note = build_concept_note(
            existing_text=existing,
            slug="zero-trust",
            title="Zero Trust",
            source_stem="new-source-synthesis",
            context="new context",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertIn("old-source", note)
        self.assertIn("new-source-synthesis", note)

    def test_update_preserves_date_compiled(self):
        existing = _make_concept_note(date_compiled="2026-01-01")
        note = build_concept_note(
            existing_text=existing,
            slug="zero-trust",
            title="Zero Trust",
            source_stem="new",
            context="ctx",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertIn("2026-01-01", note)
        self.assertIn("date_updated: 2026-04-21", note)

    def test_update_idempotent_same_source(self):
        existing = _make_concept_note(sources=["same-source"])
        note = build_concept_note(
            existing_text=existing,
            slug="zero-trust",
            title="Zero Trust",
            source_stem="same-source",
            context="repeated",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertEqual(note.count("same-source"), existing.count("same-source"))


# ---------------------------------------------------------------------------
# BuildEntityNoteTests
# ---------------------------------------------------------------------------

class BuildEntityNoteTests(unittest.TestCase):
    def test_entity_type_in_frontmatter(self):
        note = build_entity_note(
            existing_text=None,
            slug="ollama",
            title="Ollama",
            entity_type="tool",
            source_stem="src",
            context="local LLM runtime",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertIn("entity_type: tool", note)
        self.assertIn("note_type: entity", note)

    def test_unknown_entity_type_clamped(self):
        note = build_entity_note(
            existing_text=None,
            slug="some-lib",
            title="Some Lib",
            entity_type="library",
            source_stem="src",
            context="ctx",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertIn("entity_type: tool", note)

    def test_update_entity_appends_source(self):
        existing = (
            "---\ntitle: \"Ollama\"\nnote_type: entity\nentity_type: tool\n"
            "slug: ollama\ndate_compiled: 2026-01-01\ndate_updated: 2026-01-01\n"
            "sources:\n  - first-source\napproved: true\n---\n\n"
            "# Ollama\n\nDescription.\n\n## Mentioned In\n\n- [[first-source]] — ctx\n"
        )
        note = build_entity_note(
            existing_text=existing,
            slug="ollama",
            title="Ollama",
            entity_type="tool",
            source_stem="second-source",
            context="new ctx",
            generation_method="ollama_local",
            today="2026-04-21",
        )
        self.assertIn("first-source", note)
        self.assertIn("second-source", note)


# ---------------------------------------------------------------------------
# AppendMentionedInTests
# ---------------------------------------------------------------------------

class AppendMentionedInTests(unittest.TestCase):
    def test_appends_to_existing_section(self):
        body = "# Title\n\n## Mentioned In\n\n- [[old-source]] — old ctx\n\n## Related Concepts\n"
        result = _append_mentioned_in(body, "new-source", "new ctx")
        self.assertIn("[[new-source]]", result)
        self.assertIn("[[old-source]]", result)

    def test_creates_section_if_missing(self):
        body = "# Title\n\nSome text."
        result = _append_mentioned_in(body, "new-source", "ctx")
        self.assertIn("## Mentioned In", result)
        self.assertIn("[[new-source]]", result)

    def test_no_duplicate_if_already_present(self):
        body = "# Title\n\n## Mentioned In\n\n- [[existing]] — ctx\n"
        result = _append_mentioned_in(body, "existing", "ctx")
        self.assertEqual(result.count("[[existing]]"), 1)


# ---------------------------------------------------------------------------
# UpdateRegistryEntryTests
# ---------------------------------------------------------------------------

class UpdateRegistryEntryTests(unittest.TestCase):
    def test_new_slug_added(self):
        registry = {"concepts": []}
        _update_registry_entry(registry, "concepts", "rag", "RAG", "source-a", "2026-04-21")
        self.assertEqual(len(registry["concepts"]), 1)
        self.assertEqual(registry["concepts"][0]["slug"], "rag")
        self.assertIn("source-a", registry["concepts"][0]["sources"])

    def test_existing_slug_source_appended(self):
        registry = {"concepts": [{"slug": "rag", "title": "RAG", "sources": ["src-a"], "date_first_seen": "2026-01-01", "date_updated": "2026-01-01"}]}
        _update_registry_entry(registry, "concepts", "rag", "RAG", "src-b", "2026-04-21")
        self.assertIn("src-b", registry["concepts"][0]["sources"])
        self.assertIn("src-a", registry["concepts"][0]["sources"])

    def test_no_duplicate_source(self):
        registry = {"concepts": [{"slug": "rag", "title": "RAG", "sources": ["src-a"], "date_first_seen": "2026-01-01", "date_updated": "2026-01-01"}]}
        _update_registry_entry(registry, "concepts", "rag", "RAG", "src-a", "2026-04-21")
        self.assertEqual(registry["concepts"][0]["sources"].count("src-a"), 1)

    def test_extra_fields_stored(self):
        registry = {"entities": []}
        _update_registry_entry(registry, "entities", "ollama", "Ollama", "src", "2026-04-21", extra={"entity_type": "tool"})
        self.assertEqual(registry["entities"][0]["entity_type"], "tool")


# ---------------------------------------------------------------------------
# ParseSourcesFromNoteTests
# ---------------------------------------------------------------------------

class ParseSourcesFromNoteTests(unittest.TestCase):
    def test_list_sources(self):
        note = "---\nsources:\n  - source-a\n  - source-b\n---\n\nbody"
        self.assertEqual(_parse_sources_from_note(note), ["source-a", "source-b"])

    def test_empty_sources(self):
        note = "---\nsources: []\n---\n\nbody"
        self.assertEqual(_parse_sources_from_note(note), [])

    def test_missing_sources(self):
        note = "---\ntitle: foo\n---\n\nbody"
        self.assertEqual(_parse_sources_from_note(note), [])


# ---------------------------------------------------------------------------
# ExtractConceptsAndEntitiesTests (integration with tmp dir)
# ---------------------------------------------------------------------------

SAMPLE_EXTRACTION = {
    "concepts": [
        {"slug": "zero-trust", "title": "Zero Trust", "context": "described as a security model"},
    ],
    "entities": [
        {"slug": "ollama", "title": "Ollama", "entity_type": "tool", "context": "used for local LLM inference"},
    ],
}


class ExtractConceptsAndEntitiesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "compiled" / "concepts").mkdir(parents=True)
        (self.root / "compiled" / "source_summaries").mkdir(parents=True)
        (self.root / "metadata").mkdir(parents=True)
        (self.root / "metadata" / "concept-registry.json").write_text('{"concepts": []}')
        (self.root / "metadata" / "entity-registry.json").write_text('{"entities": []}')

    def tearDown(self):
        self.tmp.cleanup()

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator.call_ollama")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_creates_concept_note(self, mock_check, mock_ollama, mock_commit):
        mock_ollama.return_value = json.dumps(SAMPLE_EXTRACTION)
        result = extract_concepts_and_entities(
            "source body text", "my-source-synthesis",
            root=self.root, model="test-model",
        )
        self.assertEqual(len(result["concepts_written"]), 1)
        concept_path = self.root / "compiled" / "concepts" / "zero-trust.md"
        self.assertTrue(concept_path.exists())
        content = concept_path.read_text()
        self.assertIn("Zero Trust", content)
        self.assertIn("my-source-synthesis", content)

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator.call_ollama")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_creates_entity_note_and_dir(self, mock_check, mock_ollama, mock_commit):
        mock_ollama.return_value = json.dumps(SAMPLE_EXTRACTION)
        result = extract_concepts_and_entities(
            "source body text", "my-source-synthesis",
            root=self.root, model="test-model",
        )
        self.assertEqual(len(result["entities_written"]), 1)
        entity_path = self.root / "compiled" / "entities" / "ollama.md"
        self.assertTrue(entity_path.exists())
        content = entity_path.read_text()
        self.assertIn("entity_type: tool", content)

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator.call_ollama")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_registries_updated(self, mock_check, mock_ollama, mock_commit):
        mock_ollama.return_value = json.dumps(SAMPLE_EXTRACTION)
        extract_concepts_and_entities(
            "source body", "my-source",
            root=self.root, model="test-model",
        )
        creg = json.loads((self.root / "metadata" / "concept-registry.json").read_text())
        ereg = json.loads((self.root / "metadata" / "entity-registry.json").read_text())
        self.assertEqual(creg["concepts"][0]["slug"], "zero-trust")
        self.assertEqual(ereg["entities"][0]["slug"], "ollama")

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator.call_ollama")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_idempotent_same_source(self, mock_check, mock_ollama, mock_commit):
        mock_ollama.return_value = json.dumps(SAMPLE_EXTRACTION)
        extract_concepts_and_entities("body", "src", root=self.root, model="m")
        extract_concepts_and_entities("body", "src", root=self.root, model="m")
        concept_path = self.root / "compiled" / "concepts" / "zero-trust.md"
        content = concept_path.read_text()
        self.assertEqual(content.count("[[src]]"), 1)

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_scaffold_fallback_no_crash(self, mock_check, mock_commit):
        mock_check.side_effect = ConnectionError("Ollama down")
        result = extract_concepts_and_entities("body", "src", root=self.root, model="m")
        self.assertEqual(result["concepts_written"], [])
        self.assertEqual(result["entities_written"], [])

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator.call_ollama")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_dry_run_no_files_written(self, mock_check, mock_ollama, mock_commit):
        mock_ollama.return_value = json.dumps(SAMPLE_EXTRACTION)
        result = extract_concepts_and_entities(
            "body", "src", root=self.root, model="m", dry_run=True
        )
        self.assertEqual(result.get("concepts_written", []), [])
        concept_path = self.root / "compiled" / "concepts" / "zero-trust.md"
        self.assertFalse(concept_path.exists())
        mock_commit.assert_not_called()

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator.call_ollama")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_commit_called_with_written_paths(self, mock_check, mock_ollama, mock_commit):
        mock_ollama.return_value = json.dumps(SAMPLE_EXTRACTION)
        extract_concepts_and_entities("body", "src", root=self.root, model="m")
        mock_commit.assert_called_once()
        call_args = mock_commit.call_args
        paths = call_args[1]["paths"] if "paths" in call_args[1] else call_args[0][1]
        path_names = [p.name for p in paths]
        self.assertIn("zero-trust.md", path_names)
        self.assertIn("ollama.md", path_names)

    @patch("scripts.concept_aggregator.commit_pipeline_stage")
    @patch("scripts.concept_aggregator.call_ollama")
    @patch("scripts.concept_aggregator._check_model_available")
    def test_empty_extraction_no_files_or_commit(self, mock_check, mock_ollama, mock_commit):
        mock_ollama.return_value = '{"concepts": [], "entities": []}'
        result = extract_concepts_and_entities("body", "src", root=self.root, model="m")
        self.assertEqual(result["concepts_written"], [])
        self.assertEqual(result["entities_written"], [])
        mock_commit.assert_not_called()


# ---------------------------------------------------------------------------
# AlreadyExtractedTests
# ---------------------------------------------------------------------------

class AlreadyExtractedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_not_extracted_when_registry_empty(self):
        (self.root / "metadata" / "concept-registry.json").write_text('{"concepts": []}')
        (self.root / "metadata" / "entity-registry.json").write_text('{"entities": []}')
        self.assertFalse(_already_extracted("my-source", self.root))

    def test_extracted_when_in_concept_registry(self):
        reg = {"concepts": [{"slug": "rag", "title": "RAG", "sources": ["my-source"]}]}
        (self.root / "metadata" / "concept-registry.json").write_text(json.dumps(reg))
        (self.root / "metadata" / "entity-registry.json").write_text('{"entities": []}')
        self.assertTrue(_already_extracted("my-source", self.root))

    def test_not_extracted_when_different_source(self):
        reg = {"concepts": [{"slug": "rag", "title": "RAG", "sources": ["other-source"]}]}
        (self.root / "metadata" / "concept-registry.json").write_text(json.dumps(reg))
        (self.root / "metadata" / "entity-registry.json").write_text('{"entities": []}')
        self.assertFalse(_already_extracted("my-source", self.root))


# ---------------------------------------------------------------------------
# CliParserTests
# ---------------------------------------------------------------------------

class CliParserTests(unittest.TestCase):
    def setUp(self):
        from scripts.concept_aggregator import build_parser
        self.parser = build_parser()

    def test_source_flag(self):
        args = self.parser.parse_args(["--source", "my-source"])
        self.assertEqual(args.source, "my-source")

    def test_all_flag(self):
        args = self.parser.parse_args(["--all"])
        self.assertTrue(args.all)

    def test_dry_run_flag(self):
        args = self.parser.parse_args(["--all", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_no_commit_flag(self):
        args = self.parser.parse_args(["--all", "--no-commit"])
        self.assertTrue(args.no_commit)

    def test_source_and_all_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--source", "foo", "--all"])

    def test_no_args_raises(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])


if __name__ == "__main__":
    unittest.main()

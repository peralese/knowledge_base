"""Tests for scripts/topic_aggregator.py (Phase 5)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.topic_aggregator import (
    AggregateRequest,
    _build_topic_note,
    _ensure_source_notes_section,
    _find_source_summary,
    _normalize_text,
    _parse_compiled_from,
    _parse_date_compiled,
    _strip_fence,
    _strip_frontmatter,
    _title_for_slug,
    aggregate_for_source,
    aggregate_topic,
    build_aggregate_prompt,
    classify_to_topic,
    load_topic_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_REGISTRY = {
    "topics": [
        {
            "slug": "openclaw-security",
            "title": "OpenClaw Security",
            "aliases": ["openclaw security", "open-claw security", "open claw security"],
        },
        {
            "slug": "docker-containers",
            "title": "Docker Containers",
            "aliases": ["docker containerization", "container security"],
        },
    ]
}


def _make_topic_note(
    slug: str = "openclaw-security",
    title: str = "OpenClaw Security",
    compiled_from: list[str] | None = None,
    date_compiled: str = "2026-04-15",
) -> str:
    cf = compiled_from or ["source-summary-one"]
    cf_lines = "\n".join(f'  - "{s}"' for s in cf)
    return (
        f'---\n'
        f'title: "{title}"\n'
        f'note_type: "topic"\n'
        f'compiled_from: \n'
        f'{cf_lines}\n'
        f'date_compiled: "{date_compiled}"\n'
        f'date_updated: "2026-04-15"\n'
        f'topics:\n'
        f'  - "{title}"\n'
        f'tags:\n'
        f'  - "topic"\n'
        f'  - "{slug}"\n'
        f'confidence: "medium"\n'
        f'generation_method: "ollama_local"\n'
        f'---\n\n'
        f'# Summary\n\nExisting summary.\n\n'
        f'# Key Insights\n\n- Existing insight.\n\n'
        f'# Source Notes\n\n- [[source-summary-one]]\n\n'
        f'# Lineage\n\n- [[source-summary-one]]\n'
    )


def _make_queue_entry(
    source_id: str = "SRC-20260415-0001",
    title: str = "How to Harden OpenClaw Security",
    note_path: str = "raw/articles/how-to-harden-openclaw.md",
    review_status: str = "synthesized",
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "source_note_path": note_path,
        "review_status": review_status,
        "adapter": "browser",
    }


# ---------------------------------------------------------------------------
# ClassifyToTopicTests
# ---------------------------------------------------------------------------

class ClassifyToTopicTests(unittest.TestCase):
    def test_matches_slug_in_title(self) -> None:
        result = classify_to_topic("openclaw security risks", "", SAMPLE_REGISTRY)
        self.assertEqual(result, "openclaw-security")

    def test_matches_alias_in_title(self) -> None:
        result = classify_to_topic("open claw security guide", "", SAMPLE_REGISTRY)
        self.assertEqual(result, "openclaw-security")

    def test_matches_alias_in_body(self) -> None:
        result = classify_to_topic("Security Guide", "This article covers openclaw security best practices.", SAMPLE_REGISTRY)
        self.assertEqual(result, "openclaw-security")

    def test_case_insensitive_match(self) -> None:
        result = classify_to_topic("OPENCLAW SECURITY Overview", "", SAMPLE_REGISTRY)
        self.assertEqual(result, "openclaw-security")

    def test_no_match_returns_none(self) -> None:
        result = classify_to_topic("Python async patterns", "asyncio and aiohttp usage", SAMPLE_REGISTRY)
        self.assertIsNone(result)

    def test_empty_registry_returns_none(self) -> None:
        result = classify_to_topic("OpenClaw Security", "content", {"topics": []})
        self.assertIsNone(result)

    def test_body_truncated_to_2000_chars(self) -> None:
        # alias appears only beyond 2000 chars — should NOT match
        padding = "x " * 1001          # > 2000 chars of non-matching text
        body = padding + "openclaw security"
        result = classify_to_topic("Article", body, SAMPLE_REGISTRY)
        self.assertIsNone(result)

    def test_punctuation_normalized_before_matching(self) -> None:
        # "OpenClaw: Security" has a colon — should still match "openclaw security" alias
        result = classify_to_topic("How to Harden OpenClaw: Security Best Practices", "", SAMPLE_REGISTRY)
        self.assertEqual(result, "openclaw-security")

    def test_second_topic_matched(self) -> None:
        result = classify_to_topic("Docker containerization guide", "", SAMPLE_REGISTRY)
        self.assertEqual(result, "docker-containers")

    def test_hyphenated_slug_matches(self) -> None:
        # slug "docker-containers" → "docker containers" in text search
        result = classify_to_topic("docker containers overview", "", SAMPLE_REGISTRY)
        self.assertEqual(result, "docker-containers")


# ---------------------------------------------------------------------------
# TitleForSlugTests
# ---------------------------------------------------------------------------

class TitleForSlugTests(unittest.TestCase):
    def test_returns_canonical_title(self) -> None:
        self.assertEqual(_title_for_slug("openclaw-security", SAMPLE_REGISTRY), "OpenClaw Security")

    def test_falls_back_to_title_cased_slug(self) -> None:
        self.assertEqual(_title_for_slug("unknown-topic", SAMPLE_REGISTRY), "Unknown Topic")


# ---------------------------------------------------------------------------
# ParseFrontmatterTests
# ---------------------------------------------------------------------------

class ParseFrontmatterTests(unittest.TestCase):
    def test_parse_compiled_from_single(self) -> None:
        note = _make_topic_note(compiled_from=["source-one"])
        result = _parse_compiled_from(note)
        self.assertEqual(result, ["source-one"])

    def test_parse_compiled_from_multiple(self) -> None:
        note = _make_topic_note(compiled_from=["source-one", "source-two"])
        result = _parse_compiled_from(note)
        self.assertEqual(result, ["source-one", "source-two"])

    def test_parse_compiled_from_empty_when_no_frontmatter(self) -> None:
        result = _parse_compiled_from("# Just a body\nno frontmatter")
        self.assertEqual(result, [])

    def test_parse_date_compiled(self) -> None:
        note = _make_topic_note(date_compiled="2026-04-10")
        result = _parse_date_compiled(note)
        self.assertEqual(result, "2026-04-10")


# ---------------------------------------------------------------------------
# StripHelpersTests
# ---------------------------------------------------------------------------

class StripHelpersTests(unittest.TestCase):
    def test_strip_frontmatter_removes_yaml_block(self) -> None:
        text = "---\ntitle: Test\n---\n\n# Body\n\nContent."
        result = _strip_frontmatter(text)
        self.assertEqual(result.strip(), "# Body\n\nContent.")

    def test_strip_frontmatter_noop_when_no_frontmatter(self) -> None:
        text = "# Body\n\nContent."
        self.assertEqual(_strip_frontmatter(text).strip(), text)

    def test_strip_fence_removes_markdown_fence(self) -> None:
        text = "```markdown\n# Body\n```"
        self.assertEqual(_strip_fence(text), "# Body")

    def test_strip_fence_removes_plain_fence(self) -> None:
        text = "```\n# Body\n```"
        self.assertEqual(_strip_fence(text), "# Body")

    def test_strip_fence_noop_when_no_fence(self) -> None:
        text = "# Body\n\nContent."
        self.assertEqual(_strip_fence(text).strip(), text.strip())


# ---------------------------------------------------------------------------
# EnsureSourceNotesSectionTests
# ---------------------------------------------------------------------------

class EnsureSourceNotesSectionTests(unittest.TestCase):
    def test_appends_source_notes_when_missing(self) -> None:
        body = "# Summary\n\nContent.\n\n# Key Insights\n\n- Point."
        result = _ensure_source_notes_section(body, ["source-one"])
        self.assertIn("# Source Notes", result)
        self.assertIn("[[source-one]]", result)

    def test_replaces_existing_source_notes(self) -> None:
        body = "# Summary\n\nContent.\n\n# Source Notes\n\n- [[old-source]]\n"
        result = _ensure_source_notes_section(body, ["new-source"])
        self.assertIn("[[new-source]]", result)
        self.assertNotIn("[[old-source]]", result)

    def test_multiple_sources_all_appear(self) -> None:
        body = "# Summary\n\nContent."
        result = _ensure_source_notes_section(body, ["source-one", "source-two"])
        self.assertIn("[[source-one]]", result)
        self.assertIn("[[source-two]]", result)

    def test_lineage_section_added(self) -> None:
        body = "# Summary\n\nContent."
        result = _ensure_source_notes_section(body, ["source-one"])
        self.assertIn("# Lineage", result)


# ---------------------------------------------------------------------------
# BuildTopicNoteTests
# ---------------------------------------------------------------------------

class BuildTopicNoteTests(unittest.TestCase):
    def test_new_note_has_correct_frontmatter(self) -> None:
        result = _build_topic_note(
            existing_md=None,
            topic_slug="openclaw-security",
            topic_title="OpenClaw Security",
            new_source_stem="new-source-synthesis",
            llm_body="# Summary\n\nContent.\n\n# Key Insights\n\n- Point.",
            generation_method="ollama_local",
        )
        self.assertIn('note_type: "topic"', result)
        self.assertIn('"new-source-synthesis"', result)
        self.assertIn('title: "OpenClaw Security"', result)

    def test_existing_note_compiled_from_extended(self) -> None:
        existing = _make_topic_note(compiled_from=["old-source-synthesis"])
        result = _build_topic_note(
            existing_md=existing,
            topic_slug="openclaw-security",
            topic_title="OpenClaw Security",
            new_source_stem="new-source-synthesis",
            llm_body="# Summary\n\nUpdated.\n\n# Key Insights\n\n- New point.",
            generation_method="ollama_local",
        )
        self.assertIn('"old-source-synthesis"', result)
        self.assertIn('"new-source-synthesis"', result)

    def test_duplicate_stem_not_added_twice(self) -> None:
        existing = _make_topic_note(compiled_from=["same-source"])
        result = _build_topic_note(
            existing_md=existing,
            topic_slug="openclaw-security",
            topic_title="OpenClaw Security",
            new_source_stem="same-source",
            llm_body="# Summary\n\nContent.",
            generation_method="ollama_local",
        )
        self.assertEqual(result.count('"same-source"'), 1)

    def test_date_compiled_preserved_from_existing(self) -> None:
        existing = _make_topic_note(date_compiled="2026-04-10")
        result = _build_topic_note(
            existing_md=existing,
            topic_slug="openclaw-security",
            topic_title="OpenClaw Security",
            new_source_stem="new-source",
            llm_body="# Summary\n\nContent.",
            generation_method="ollama_local",
        )
        self.assertIn('"2026-04-10"', result)

    def test_scaffold_generation_method_recorded(self) -> None:
        result = _build_topic_note(
            existing_md=None,
            topic_slug="openclaw-security",
            topic_title="OpenClaw Security",
            new_source_stem="source",
            llm_body="# Summary\n\nContent.",
            generation_method="scaffold",
        )
        self.assertIn('generation_method: "scaffold"', result)


# ---------------------------------------------------------------------------
# BuildAggregatePromptTests
# ---------------------------------------------------------------------------

class BuildAggregatePromptTests(unittest.TestCase):
    def test_new_topic_prompt_contains_title(self) -> None:
        prompt = build_aggregate_prompt("OpenClaw Security", None, "source content")
        self.assertIn("OpenClaw Security", prompt)
        self.assertIn("source content", prompt)

    def test_new_topic_prompt_no_existing_note_section(self) -> None:
        prompt = build_aggregate_prompt("OpenClaw Security", None, "source content")
        self.assertNotIn("Existing topic note", prompt)

    def test_update_prompt_contains_existing_body(self) -> None:
        existing = _make_topic_note()
        prompt = build_aggregate_prompt("OpenClaw Security", existing, "new content")
        self.assertIn("Existing summary", prompt)
        self.assertIn("new content", prompt)

    def test_update_prompt_strips_frontmatter_from_existing(self) -> None:
        existing = _make_topic_note()
        prompt = build_aggregate_prompt("OpenClaw Security", existing, "new content")
        self.assertNotIn("note_type:", prompt)
        self.assertNotIn("compiled_from:", prompt)

    def test_sections_requested_in_prompt(self) -> None:
        prompt = build_aggregate_prompt("OpenClaw Security", None, "content")
        self.assertIn("# Summary", prompt)
        self.assertIn("# Key Insights", prompt)


# ---------------------------------------------------------------------------
# AggregateTopicTests
# ---------------------------------------------------------------------------

class AggregateTopicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Set up directory structure
        (self.root / "metadata").mkdir(parents=True)
        (self.root / "compiled" / "topics").mkdir(parents=True)
        (self.root / "compiled" / "source_summaries").mkdir(parents=True)
        # Write topic registry
        (self.root / "metadata" / "topic-registry.json").write_text(
            json.dumps(SAMPLE_REGISTRY), encoding="utf-8"
        )
        # Write a source summary
        self.summary_path = self.root / "compiled" / "source_summaries" / "test-article-synthesis.md"
        self.summary_path.write_text(
            "# Summary\n\nOpenClaw security best practices.\n\n# Key Insights\n\n- Use Docker.",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_request(self) -> AggregateRequest:
        return AggregateRequest(
            topic_slug="openclaw-security",
            new_source_summary_path=self.summary_path,
            new_source_id="SRC-20260415-0001",
            root=self.root,
        )

    @patch("scripts.topic_aggregator.call_ollama")
    @patch("scripts.topic_aggregator._check_model_available")
    def test_creates_new_topic_note(self, mock_check: MagicMock, mock_ollama: MagicMock) -> None:
        mock_check.return_value = None
        mock_ollama.return_value = "# Summary\n\nSynthesized.\n\n# Key Insights\n\n- Point."
        result = aggregate_topic(self._make_request())
        self.assertTrue(result.exists())
        content = result.read_text(encoding="utf-8")
        self.assertIn('note_type: "topic"', content)
        self.assertIn("OpenClaw Security", content)

    @patch("scripts.topic_aggregator.call_ollama")
    @patch("scripts.topic_aggregator._check_model_available")
    def test_updates_existing_topic_note(self, mock_check: MagicMock, mock_ollama: MagicMock) -> None:
        mock_check.return_value = None
        mock_ollama.return_value = "# Summary\n\nUpdated.\n\n# Key Insights\n\n- Updated point."
        topic_path = self.root / "compiled" / "topics" / "openclaw-security.md"
        topic_path.write_text(_make_topic_note(compiled_from=["old-synthesis"]), encoding="utf-8")

        result = aggregate_topic(self._make_request())
        content = result.read_text(encoding="utf-8")
        self.assertIn('"old-synthesis"', content)
        self.assertIn('"test-article-synthesis"', content)

    @patch("scripts.topic_aggregator._check_model_available")
    def test_scaffold_fallback_when_ollama_unavailable(self, mock_check: MagicMock) -> None:
        mock_check.side_effect = ConnectionError("Ollama not running")
        result = aggregate_topic(self._make_request())
        self.assertTrue(result.exists())
        content = result.read_text(encoding="utf-8")
        self.assertIn('generation_method: "scaffold"', content)

    @patch("scripts.topic_aggregator.call_ollama")
    @patch("scripts.topic_aggregator._check_model_available")
    def test_source_notes_section_correct(self, mock_check: MagicMock, mock_ollama: MagicMock) -> None:
        mock_check.return_value = None
        mock_ollama.return_value = "# Summary\n\nContent.\n\n# Key Insights\n\n- Point."
        result = aggregate_topic(self._make_request())
        content = result.read_text(encoding="utf-8")
        self.assertIn("# Source Notes", content)
        self.assertIn("[[test-article-synthesis]]", content)

    @patch("scripts.topic_aggregator.call_ollama")
    @patch("scripts.topic_aggregator._check_model_available")
    def test_topic_note_output_path_correct(self, mock_check: MagicMock, mock_ollama: MagicMock) -> None:
        mock_check.return_value = None
        mock_ollama.return_value = "# Summary\n\nContent."
        result = aggregate_topic(self._make_request())
        self.assertEqual(result, self.root / "compiled" / "topics" / "openclaw-security.md")


# ---------------------------------------------------------------------------
# AggregateForSourceTests
# ---------------------------------------------------------------------------

class AggregateForSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)
        (self.root / "compiled" / "topics").mkdir(parents=True)
        (self.root / "compiled" / "source_summaries").mkdir(parents=True)
        (self.root / "raw" / "articles").mkdir(parents=True)
        (self.root / "metadata" / "topic-registry.json").write_text(
            json.dumps(SAMPLE_REGISTRY), encoding="utf-8"
        )
        # Write raw article (contains match text)
        self.raw_path = self.root / "raw" / "articles" / "hardening-openclaw.md"
        self.raw_path.write_text(
            "---\ntitle: OpenClaw Security Guide\n---\n\nopenClaw security content.",
            encoding="utf-8",
        )
        # Write source summary
        self.summary_path = self.root / "compiled" / "source_summaries" / "hardening-openclaw-synthesis.md"
        self.summary_path.write_text("# Summary\n\nSecurity content.", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_item(self) -> dict:
        return {
            "source_id": "SRC-20260415-0001",
            "title": "OpenClaw Security Guide",
            "source_note_path": "raw/articles/hardening-openclaw.md",
            "review_status": "synthesized",
        }

    @patch("scripts.topic_aggregator.call_ollama")
    @patch("scripts.topic_aggregator._check_model_available")
    def test_creates_topic_note_on_match(self, mock_check: MagicMock, mock_ollama: MagicMock) -> None:
        mock_check.return_value = None
        mock_ollama.return_value = "# Summary\n\nContent.\n\n# Key Insights\n\n- Point."
        aggregate_for_source(self._make_item(), self.summary_path, root=self.root)
        topic_note = self.root / "compiled" / "topics" / "openclaw-security.md"
        self.assertTrue(topic_note.exists())

    def test_skips_when_no_registry_match(self) -> None:
        item = {
            "source_id": "SRC-001",
            "title": "Python async patterns",
            "source_note_path": "raw/articles/python-async.md",
            "review_status": "synthesized",
        }
        # Should not raise, just skip
        aggregate_for_source(item, self.summary_path, root=self.root)
        topic_note = self.root / "compiled" / "topics" / "openclaw-security.md"
        self.assertFalse(topic_note.exists())


# ---------------------------------------------------------------------------
# FindSourceSummaryTests
# ---------------------------------------------------------------------------

class FindSourceSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "compiled" / "source_summaries").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_finds_existing_summary(self) -> None:
        path = self.root / "compiled" / "source_summaries" / "my-article-synthesis.md"
        path.write_text("content", encoding="utf-8")
        item = {"source_note_path": "raw/articles/my-article.md"}
        result = _find_source_summary(item, self.root)
        self.assertEqual(result, path)

    def test_returns_none_when_missing(self) -> None:
        item = {"source_note_path": "raw/articles/nonexistent.md"}
        result = _find_source_summary(item, self.root)
        self.assertIsNone(result)

    def test_returns_none_when_path_empty(self) -> None:
        item = {"source_note_path": ""}
        result = _find_source_summary(item, self.root)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# LoadTopicRegistryTests
# ---------------------------------------------------------------------------

class LoadTopicRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_loads_registry(self) -> None:
        (self.root / "metadata" / "topic-registry.json").write_text(
            json.dumps(SAMPLE_REGISTRY), encoding="utf-8"
        )
        result = load_topic_registry(self.root)
        self.assertEqual(len(result["topics"]), 2)

    def test_returns_empty_when_file_missing(self) -> None:
        result = load_topic_registry(self.root)
        self.assertEqual(result, {"topics": []})


if __name__ == "__main__":
    unittest.main()

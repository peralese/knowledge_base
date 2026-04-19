from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.apply_synthesis import ApplySynthesisRequest
from scripts.apply_synthesis import _set_frontmatter_field
from scripts.apply_synthesis import apply_synthesis
from scripts.apply_synthesis import build_compiled_frontmatter
from scripts.apply_synthesis import ensure_source_notes_section
from scripts.apply_synthesis import extract_prompt_pack_metadata
from scripts.apply_synthesis import sanitize_markdown_body
from scripts.apply_synthesis import slugify_title


class ApplySynthesisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        for relative in [
            "compiled/source_summaries",
            "compiled/concepts",
            "compiled/topics",
            "outputs/answers",
            "outputs/reports",
            "metadata/prompts",
            "metadata",
            "tmp",
        ]:
            (self.root / relative).mkdir(parents=True, exist_ok=True)

        (self.root / "metadata" / "topic-registry.json").write_text(
            json.dumps(
                {
                    "topics": [
                        {
                            "slug": "openclaw-security",
                            "title": "OpenClaw Security",
                            "aliases": [
                                "openclaw security",
                                "open-claw security",
                                "open claw security",
                            ],
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        self.prompt_pack = self.root / "metadata" / "prompts" / "compile-openclaw-security.md"
        self.prompt_pack.write_text(
            (
                "# Compilation Request\n\n"
                "- Requested title: OpenClaw Security\n"
                "- Canonical title: OpenClaw Security\n"
                "- Canonical slug: openclaw-security\n"
                "- Note category: topic\n"
                "- Repository phase: Phase 3 compilation workflow\n"
                "- Required generation method value: prompt_pack\n\n"
                "# Canonical Identity Rules\n\n"
                "- Use the exact canonical title provided: OpenClaw Security\n"
                "- Use the exact canonical topic slug provided: openclaw-security\n"
                "- Do not invent, modify, pluralize, misspell, or rename the topic.\n"
                "- Do not create alternative topic identities.\n\n"
                "# Source Notes\n\n"
                "## [[openclaw-security-best-practices]]\n\n"
                "## [[openclaw-security-hardening-guide]]\n"
            ),
            encoding="utf-8",
        )

        for relative in [
            "raw/articles/openclaw-security-best-practices.md",
            "raw/articles/openclaw-security-hardening-guide.md",
        ]:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Source\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_slug_generation(self) -> None:
        self.assertEqual(slugify_title("OpenClaw Security"), "openclaw-security")

    def test_prompt_pack_metadata_extraction(self) -> None:
        metadata = extract_prompt_pack_metadata(self.prompt_pack)

        self.assertEqual(metadata.requested_title, "OpenClaw Security")
        self.assertEqual(metadata.canonical_title, "OpenClaw Security")
        self.assertEqual(metadata.canonical_slug, "openclaw-security")
        self.assertEqual(metadata.note_category, "topic")
        self.assertEqual(
            metadata.source_notes,
            ["openclaw-security-best-practices", "openclaw-security-hardening-guide"],
        )

    def test_mismatched_title_gets_patched_to_canonical_title(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "---\n"
                    'title: "openclaw secruity"\n'
                    'generation_method: "prompt_pack"\n'
                    "---\n\n"
                    "# Summary\n\nSecurity guidance.\n"
                ),
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertIn('title: "OpenClaw Security"', saved)
        self.assertNotIn('title: "openclaw secruity"', saved)

    def test_destination_uses_canonical_slug_not_model_drifted_slug(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text="# Summary\n\nOpenClaw secruity recommendations.\n",
                root=self.root,
            )
        )

        self.assertEqual(output_path, self.root / "compiled" / "topics" / "openclaw-security.md")

    def test_wrapping_markdown_fences_are_removed(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "```markdown\n"
                    "# Summary\n\n"
                    "OpenClaw hardening guidance.\n"
                    "```\n"
                ),
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertNotIn("```markdown", saved)
        self.assertNotIn("\n```\n", saved)
        self.assertIn("OpenClaw hardening guidance.", saved)

    def test_wrapping_fence_with_trailing_llm_junk_is_removed(self) -> None:
        """LLM sometimes appends instructions after the closing fence — strip the fence and the junk."""
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "```markdown\n"
                    "# Summary\n\n"
                    "OpenClaw hardening guidance.\n"
                    "```\n\n"
                    "Please adjust `date_compiled` to reflect the actual compilation date.\n"
                ),
                root=self.root,
                force=True,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertNotIn("```markdown", saved)
        self.assertNotIn("Please adjust", saved)
        self.assertIn("OpenClaw hardening guidance.", saved)

    def test_truncated_fence_no_closing_backticks_still_stripped(self) -> None:
        """Ollama sometimes truncates before emitting the closing fence — content must not stay in a code block."""
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "```markdown\n"
                    "# Summary\n\n"
                    "OpenClaw hardening guidance.\n"
                    # deliberately no closing ```
                ),
                root=self.root,
                force=True,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertNotIn("```markdown", saved)
        self.assertIn("OpenClaw hardening guidance.", saved)

    def test_duplicate_inner_frontmatter_is_handled_correctly(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "# Summary\n\n"
                    "Good summary.\n\n"
                    "---\n"
                    'title: "Wrong Inner Title"\n'
                    'note_type: "topic"\n'
                    "---\n\n"
                    "# Key Insights\n\n"
                    "- Insight\n"
                ),
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertIn("Good summary.", saved)
        self.assertNotIn("Wrong Inner Title", saved)
        self.assertEqual(saved.count('title: "OpenClaw Security"'), 1)

    def test_citation_junk_is_removed(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text="# Summary\n\nUseful text. [oaicite:7] :contentReference[oaicite:2]{index=0}\n",
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertIn("Useful text.", saved)
        self.assertNotIn("[oaicite:", saved)
        self.assertNotIn(":contentReference[", saved)
        self.assertNotIn("{index=0}", saved)

    def test_valid_wikilinks_are_preserved(self) -> None:
        sanitized = sanitize_markdown_body(
            "# Lineage\n\n- [[open-claw-security]]\n- [[openclaw-security-best-practices]]\n"
        )

        self.assertIn("[[open-claw-security]]", sanitized.text)
        self.assertIn("[[openclaw-security-best-practices]]", sanitized.text)

    def test_unresolved_invalid_wikilinks_cause_clear_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, r"Validation failed: unresolved wikilinks"):
            apply_synthesis(
                ApplySynthesisRequest(
                    prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                    text="# Summary\n\nSee [[totally-missing-note]].\n",
                    root=self.root,
                )
            )

    def test_source_wikilinks_from_prompt_pack_are_recognized_correctly(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text="# Source Notes\n\n- [[openclaw security best practices]]\n- [[openclaw-security-hardening-guide]]\n",
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertIn("[[openclaw-security-best-practices]]", saved)
        self.assertIn("[[openclaw-security-hardening-guide]]", saved)

    def test_generation_method_becomes_manual_paste(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "---\n"
                    'title: "Existing Draft"\n'
                    'generation_method: "prompt_pack"\n'
                    "---\n\n"
                    "# Summary\n\nApplied synthesis.\n"
                ),
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertIn('generation_method: "manual_paste"', saved)
        self.assertNotIn('generation_method: "prompt_pack"', saved)

    def test_missing_source_notes_section_is_injected(self) -> None:
        """LLM output with no # Source Notes section gets one injected with wikilinks.

        The test prompt pack (built in setUp) has two source notes:
        openclaw-security-best-practices and openclaw-security-hardening-guide.
        """
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text="# Summary\n\nContent with no source notes section at all.\n",
                root=self.root,
            )
        )
        saved = output_path.read_text(encoding="utf-8")
        self.assertIn("# Source Notes", saved)
        self.assertIn("[[openclaw-security-best-practices]]", saved)
        self.assertIn("[[openclaw-security-hardening-guide]]", saved)

    def test_partial_source_notes_section_gets_missing_links_appended(self) -> None:
        """If LLM included some but not all source wikilinks, missing ones are injected."""
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "# Summary\n\nGood content.\n\n"
                    "# Source Notes\n\n"
                    "- [[openclaw-security-best-practices]]\n"
                ),
                root=self.root,
            )
        )
        saved = output_path.read_text(encoding="utf-8")
        self.assertIn("[[openclaw-security-best-practices]]", saved)
        self.assertIn("[[openclaw-security-hardening-guide]]", saved)

    def test_complete_source_notes_section_is_not_duplicated(self) -> None:
        """If all source wikilinks are present, nothing extra is injected."""
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
                text=(
                    "# Summary\n\nGood content.\n\n"
                    "# Source Notes\n\n"
                    "- [[openclaw-security-best-practices]]\n"
                    "- [[openclaw-security-hardening-guide]]\n"
                ),
                root=self.root,
            )
        )
        saved = output_path.read_text(encoding="utf-8")
        # Each wikilink should appear exactly once
        self.assertEqual(saved.count("[[openclaw-security-best-practices]]"), 1)
        self.assertEqual(saved.count("[[openclaw-security-hardening-guide]]"), 1)

    def test_ensure_source_notes_section_unit(self) -> None:
        """Direct unit test of ensure_source_notes_section."""
        body = "# Summary\n\nSome content.\n"
        updated, changed = ensure_source_notes_section(body, ["note-a", "note-b"])
        self.assertTrue(changed)
        self.assertIn("[[note-a]]", updated)
        self.assertIn("[[note-b]]", updated)
        self.assertIn("# Source Notes", updated)

    def test_ensure_source_notes_no_change_when_links_present(self) -> None:
        body = "# Summary\n\nContent.\n\n# Source Notes\n\n- [[note-a]]\n- [[note-b]]\n"
        updated, changed = ensure_source_notes_section(body, ["note-a", "note-b"])
        self.assertFalse(changed)
        self.assertEqual(updated, body)

    def test_no_overwrite_by_default(self) -> None:
        request = ApplySynthesisRequest(
            prompt_pack=Path("metadata/prompts/compile-openclaw-security.md"),
            text="# Summary\n\nInitial synthesis.",
            root=self.root,
        )

        first_output = apply_synthesis(request)
        self.assertTrue(first_output.exists())

        with self.assertRaises(FileExistsError):
            apply_synthesis(request)


class SetFrontmatterFieldTests(unittest.TestCase):
    def test_replaces_existing_field(self) -> None:
        text = "---\ntitle: old\n---\n\nBody.\n"
        result = _set_frontmatter_field(text, "title", "new")
        self.assertIn("title: new", result)
        self.assertNotIn("title: old", result)

    def test_inserts_missing_field_before_closing_fence(self) -> None:
        text = "---\ntitle: existing\n---\n\nBody.\n"
        result = _set_frontmatter_field(text, "approved", "false")
        self.assertIn("approved: false", result)
        # Closing --- must still be present exactly once
        self.assertEqual(result.count("\n---\n"), 1)

    def test_body_text_is_unchanged(self) -> None:
        text = "---\ntitle: t\n---\n\nImportant body content.\n"
        result = _set_frontmatter_field(text, "title", "t2")
        self.assertIn("Important body content.", result)


class BuildCompiledFrontmatterTests(unittest.TestCase):
    def _call(self, existing_metadata: dict | None = None) -> str:
        return build_compiled_frontmatter(
            title="Test Note",
            note_type="source_summary",
            compiled_from=["raw/articles/test.md"],
            topics=["topic-a"],
            tags=["source_summary"],
            generation_method="ollama_local",
            today="2026-04-16",
            existing_metadata=existing_metadata or {},
        )

    def test_approved_false_by_default(self) -> None:
        fm = self._call()
        self.assertIn("approved: false", fm)

    def test_confidence_score_null_by_default(self) -> None:
        fm = self._call()
        self.assertIn("confidence_score: null", fm)

    def test_date_updated_matches_today(self) -> None:
        fm = self._call()
        self.assertIn('date_updated: "2026-04-16"', fm)

    def test_preserves_existing_approved_true(self) -> None:
        fm = self._call(existing_metadata={"approved": True})
        self.assertIn("approved: true", fm)
        self.assertNotIn("approved: false", fm)

    def test_preserves_existing_confidence_score(self) -> None:
        fm = self._call(existing_metadata={"confidence_score": 0.87})
        self.assertIn("confidence_score: 0.87", fm)
        self.assertNotIn("confidence_score: null", fm)


if __name__ == "__main__":
    unittest.main()

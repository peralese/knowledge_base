from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.compile_notes import CompileRequest
from scripts.compile_notes import build_compiled_frontmatter
from scripts.compile_notes import compile_notes
from scripts.compile_notes import destination_dir_for_category
from scripts.compile_notes import resolve_canonical_topic
from scripts.compile_notes import slugify_title


class CompileNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        for relative in [
            "raw/articles",
            "compiled/source_summaries",
            "compiled/concepts",
            "compiled/topics",
            "metadata",
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
                            ],
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        self.source_one = self.root / "raw" / "articles" / "openclaw-security-best-practices.md"
        self.source_one.write_text(
            (
                "---\n"
                'title: "OpenClaw Security Best Practices"\n'
                'source_type: "article-note"\n'
                'origin: "OpenClaw docs"\n'
                'summary: "Security recommendations for OpenClaw."\n'
                "topics:\n"
                '  - "security"\n'
                '  - "openclaw"\n'
                "tags:\n"
                '  - "hardening"\n'
                "---\n\n"
                "# Source Content\n\n"
                "OpenClaw should be deployed with least privilege and hardened defaults.\n"
            ),
            encoding="utf-8",
        )

        self.source_two = self.root / "raw" / "articles" / "openclaw-security-hardening-guide.md"
        self.source_two.write_text(
            (
                "---\n"
                'title: "OpenClaw Security Hardening Guide"\n'
                'source_type: "article-note"\n'
                'origin: "OpenClaw guide"\n'
                'summary: "Operational hardening guidance."\n'
                "topics:\n"
                '  - "security"\n'
                '  - "operations"\n'
                "tags:\n"
                '  - "openclaw"\n'
                "---\n\n"
                "# Source Content\n\n"
                "Use network isolation, patch discipline, and secret rotation.\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_slug_generation_for_unregistered_topic(self) -> None:
        self.assertEqual(slugify_title("AI Research Notes"), "ai-research-notes")
        self.assertEqual(slugify_title("  Mixed CASE / spacing  "), "mixed-case-spacing")

    def test_destination_folder_selection(self) -> None:
        self.assertEqual(destination_dir_for_category("source_summary"), Path("compiled/source_summaries"))
        self.assertEqual(destination_dir_for_category("concept"), Path("compiled/concepts"))
        self.assertEqual(destination_dir_for_category("topic"), Path("compiled/topics"))

    def test_frontmatter_generation(self) -> None:
        frontmatter = build_compiled_frontmatter(
            title="OpenClaw Security",
            category="topic",
            compiled_from=["openclaw-security-best-practices", "openclaw-security-hardening-guide"],
            topics=["security", "operations"],
            tags=["topic", "openclaw"],
            generation_method="manual_scaffold",
            today="2026-04-05",
        )

        self.assertIn('title: "OpenClaw Security"', frontmatter)
        self.assertIn('note_type: "topic"', frontmatter)
        self.assertIn('generation_method: "manual_scaffold"', frontmatter)
        self.assertIn('confidence: "medium"', frontmatter)

    def test_topic_registry_canonicalization_from_alias(self) -> None:
        resolved = resolve_canonical_topic("open-claw security", self.root / "metadata" / "topic-registry.json")

        self.assertTrue(resolved.matched_registry)
        self.assertEqual(resolved.slug, "openclaw-security")
        self.assertEqual(resolved.title, "OpenClaw Security")

    def test_scaffold_uses_canonical_slug_and_title(self) -> None:
        created = compile_notes(
            CompileRequest(
                sources=[
                    Path("raw/articles/openclaw-security-best-practices.md"),
                    Path("raw/articles/openclaw-security-hardening-guide.md"),
                ],
                title="openclaw security",
                category="topic",
                mode="scaffold",
                root=self.root,
            )
        )

        output_path = created["scaffold"]
        self.assertEqual(output_path, self.root / "compiled" / "topics" / "openclaw-security.md")

        note_text = output_path.read_text(encoding="utf-8")
        self.assertIn('title: "OpenClaw Security"', note_text)
        self.assertIn("- [[openclaw-security-best-practices]]", note_text)

    def test_prompt_pack_includes_canonical_slug_instruction(self) -> None:
        created = compile_notes(
            CompileRequest(
                sources=[
                    Path("raw/articles/openclaw-security-best-practices.md"),
                    Path("raw/articles/openclaw-security-hardening-guide.md"),
                ],
                title="open-claw security",
                category="topic",
                mode="prompt-pack",
                root=self.root,
            )
        )

        prompt_path = created["prompt-pack"]
        prompt_text = prompt_path.read_text(encoding="utf-8")

        self.assertIn("- Canonical title: OpenClaw Security", prompt_text)
        self.assertIn("- Canonical slug: openclaw-security", prompt_text)
        self.assertIn("Use the exact canonical title provided: OpenClaw Security", prompt_text)
        self.assertIn("Use the exact canonical topic slug provided: openclaw-security", prompt_text)
        self.assertIn("Do not create alternative topic identities.", prompt_text)

    def test_no_overwrite_by_default(self) -> None:
        request = CompileRequest(
            sources=[Path("raw/articles/openclaw-security-best-practices.md")],
            title="OpenClaw Security",
            category="concept",
            mode="scaffold",
            root=self.root,
        )

        first_created = compile_notes(request)
        self.assertTrue(first_created["scaffold"].exists())

        with self.assertRaises(FileExistsError):
            compile_notes(request)


if __name__ == "__main__":
    unittest.main()

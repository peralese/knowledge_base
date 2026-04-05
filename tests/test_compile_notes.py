from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.compile_notes import CompileRequest
from scripts.compile_notes import build_compiled_frontmatter
from scripts.compile_notes import compile_notes
from scripts.compile_notes import destination_dir_for_category
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

        self.source_one = self.root / "raw" / "articles" / "aws-patch-manager-basics.md"
        self.source_one.write_text(
            (
                "---\n"
                'title: "AWS Patch Manager Basics"\n'
                'source_type: "article-note"\n'
                'origin: "AWS documentation"\n'
                'summary: "Patch Manager automates patching."\n'
                "topics:\n"
                '  - "aws"\n'
                '  - "patching"\n'
                "tags:\n"
                '  - "patch-manager"\n'
                "---\n\n"
                "# Source Content\n\n"
                "Patch Manager defines approved patches and applies them during maintenance windows.\n"
            ),
            encoding="utf-8",
        )

        self.source_two = self.root / "raw" / "articles" / "aws-inspector-overview.md"
        self.source_two.write_text(
            (
                "---\n"
                'title: "AWS Inspector Overview"\n'
                'source_type: "article-note"\n'
                'origin: "AWS documentation"\n'
                'summary: "Inspector surfaces vulnerabilities."\n'
                "topics:\n"
                '  - "aws"\n'
                '  - "security"\n'
                "tags:\n"
                '  - "inspector"\n'
                "---\n\n"
                "# Source Content\n\n"
                "Inspector continuously evaluates supported resources and produces findings.\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_slug_generation(self) -> None:
        self.assertEqual(
            slugify_title("AWS Patching and Vulnerability Management Overview"),
            "aws-patching-and-vulnerability-management-overview",
        )
        self.assertEqual(slugify_title("  Mixed CASE / spacing  "), "mixed-case-spacing")

    def test_destination_folder_selection(self) -> None:
        self.assertEqual(destination_dir_for_category("source_summary"), Path("compiled/source_summaries"))
        self.assertEqual(destination_dir_for_category("concept"), Path("compiled/concepts"))
        self.assertEqual(destination_dir_for_category("topic"), Path("compiled/topics"))

    def test_frontmatter_generation(self) -> None:
        frontmatter = build_compiled_frontmatter(
            title="AWS Overview",
            category="topic",
            compiled_from=["aws-patch-manager-basics", "aws-inspector-overview"],
            topics=["aws", "security"],
            tags=["topic", "patch-manager"],
            generation_method="manual_scaffold",
            today="2026-04-04",
        )

        self.assertIn('title: "AWS Overview"', frontmatter)
        self.assertIn('note_type: "topic"', frontmatter)
        self.assertIn('generation_method: "manual_scaffold"', frontmatter)
        self.assertIn('confidence: "medium"', frontmatter)
        self.assertIn('  - "aws-patch-manager-basics"', frontmatter)

    def test_scaffold_includes_source_wikilinks(self) -> None:
        created = compile_notes(
            CompileRequest(
                sources=[
                    Path("raw/articles/aws-patch-manager-basics.md"),
                    Path("raw/articles/aws-inspector-overview.md"),
                ],
                title="AWS Patching and Vulnerability Management Overview",
                category="topic",
                mode="scaffold",
                root=self.root,
            )
        )

        output_path = created["scaffold"]
        self.assertTrue(output_path.exists())

        note_text = output_path.read_text(encoding="utf-8")
        self.assertIn('note_type: "topic"', note_text)
        self.assertIn('generation_method: "manual_scaffold"', note_text)
        self.assertIn("- [[aws-patch-manager-basics]]", note_text)
        self.assertIn("- [[aws-inspector-overview]]", note_text)
        self.assertIn("## [[aws-patch-manager-basics]]", note_text)
        self.assertIn("## [[aws-inspector-overview]]", note_text)

    def test_no_overwrite_by_default(self) -> None:
        request = CompileRequest(
            sources=[Path("raw/articles/aws-patch-manager-basics.md")],
            title="Existing Compiled Note",
            category="concept",
            mode="scaffold",
            root=self.root,
        )

        first_created = compile_notes(request)
        self.assertTrue(first_created["scaffold"].exists())

        with self.assertRaises(FileExistsError):
            compile_notes(request)

    def test_prompt_pack_generation(self) -> None:
        created = compile_notes(
            CompileRequest(
                sources=[
                    Path("raw/articles/aws-patch-manager-basics.md"),
                    Path("raw/articles/aws-inspector-overview.md"),
                ],
                title="AWS Patching and Vulnerability Management Overview",
                category="topic",
                mode="prompt-pack",
                root=self.root,
            )
        )

        prompt_path = created["prompt-pack"]
        self.assertTrue(prompt_path.exists())

        prompt_text = prompt_path.read_text(encoding="utf-8")
        self.assertIn("# Compilation Request", prompt_text)
        self.assertIn("- Requested title: AWS Patching and Vulnerability Management Overview", prompt_text)
        self.assertIn("Do not invent unsupported claims.", prompt_text)
        self.assertIn("## [[aws-patch-manager-basics]]", prompt_text)
        self.assertIn("## [[aws-inspector-overview]]", prompt_text)
        self.assertIn("generation_method: \"prompt_pack\"", prompt_text)


if __name__ == "__main__":
    unittest.main()

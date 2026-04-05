from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.apply_synthesis import ApplySynthesisRequest
from scripts.apply_synthesis import apply_synthesis
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
            "tmp",
        ]:
            (self.root / relative).mkdir(parents=True, exist_ok=True)

        self.prompt_pack = self.root / "metadata" / "prompts" / "compile-aws-patching-strategy.md"
        self.prompt_pack.write_text(
            (
                "# Compilation Request\n\n"
                "- Requested title: AWS Patching Strategy\n"
                "- Note category: topic\n"
                "- Repository phase: Phase 3 compilation workflow\n"
                "- Required generation method value: prompt_pack\n\n"
                "# Source Notes\n\n"
                "## [[aws-patch-manager-basics]]\n\n"
                "## [[aws-inspector-overview]]\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_slug_generation(self) -> None:
        self.assertEqual(slugify_title("AWS Patching Strategy"), "aws-patching-strategy")

    def test_prompt_pack_metadata_extraction(self) -> None:
        metadata = extract_prompt_pack_metadata(self.prompt_pack)

        self.assertEqual(metadata.requested_title, "AWS Patching Strategy")
        self.assertEqual(metadata.note_category, "topic")
        self.assertEqual(
            metadata.source_notes,
            ["aws-patch-manager-basics", "aws-inspector-overview"],
        )

    def test_compiled_output_creation_from_file(self) -> None:
        synthesized_file = self.root / "tmp" / "synthesized-note.md"
        synthesized_file.write_text(
            (
                "# Summary\n\n"
                "This synthesis combines patch execution and vulnerability visibility.\n\n"
                "# Related Concepts\n\n"
                "- patching\n"
                "- security\n"
            ),
            encoding="utf-8",
        )

        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-aws-patching-strategy.md"),
                synthesized_file=Path("tmp/synthesized-note.md"),
                root=self.root,
            )
        )

        self.assertEqual(output_path, self.root / "compiled" / "topics" / "aws-patching-strategy.md")
        saved = output_path.read_text(encoding="utf-8")
        self.assertIn('title: "AWS Patching Strategy"', saved)
        self.assertIn('note_type: "topic"', saved)
        self.assertIn('generation_method: "manual_paste"', saved)
        self.assertIn('  - "aws-patch-manager-basics"', saved)
        self.assertIn("# Summary", saved)

    def test_answer_output_creation_from_text(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-aws-patching-strategy.md"),
                text="# Prompt\n\nWhat is the relationship between Patch Manager and Inspector?\n\n# Answer\n\nThey complement each other.\n",
                output_type="answer",
                root=self.root,
            )
        )

        self.assertEqual(output_path, self.root / "outputs" / "answers" / "aws-patching-strategy.md")
        saved = output_path.read_text(encoding="utf-8")
        self.assertIn('output_type: "answer"', saved)
        self.assertIn('generated_from_query: "What is the relationship between Patch Manager and Inspector?"', saved)
        self.assertIn('generation_method: "manual_paste"', saved)
        self.assertIn('  - "aws-patch-manager-basics"', saved)
        self.assertIn('  - "aws-patching-strategy"', saved)

    def test_frontmatter_injection_when_missing(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-aws-patching-strategy.md"),
                text="Plain synthesized markdown without frontmatter.",
                output_type="report",
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertTrue(saved.startswith("---\n"))
        self.assertIn('output_type: "report"', saved)
        self.assertIn("Plain synthesized markdown without frontmatter.", saved)

    def test_citation_junk_is_removed(self) -> None:
        sanitized = sanitize_markdown_body(
            "# Summary\n\nUseful synthesis text. [oaicite:12] :contentReference[oaicite:3]{index=3}\n"
        )

        self.assertIn("Useful synthesis text.", sanitized)
        self.assertNotIn("[oaicite:", sanitized)
        self.assertNotIn(":contentReference[", sanitized)

    def test_shell_snippet_junk_is_removed_or_neutralized(self) -> None:
        sanitized = sanitize_markdown_body(
            "# Summary\n\n$(node --version)\n`$(pwd)`\nThis overview remains.\n"
        )

        self.assertIn("This overview remains.", sanitized)
        self.assertNotIn("$(node --version)", sanitized)
        self.assertNotIn("$(pwd)", sanitized)

    def test_github_blob_path_junk_is_removed_or_neutralized(self) -> None:
        sanitized = sanitize_markdown_body(
            "# Summary\n\nkarpathy/autoresearch/blob/master/progress.png\nClean note text stays.\n"
        )

        self.assertIn("Clean note text stays.", sanitized)
        self.assertNotIn("blob/master", sanitized)
        self.assertNotIn("progress.png", sanitized)

    def test_valid_wikilinks_are_preserved(self) -> None:
        sanitized = sanitize_markdown_body(
            "# Source Notes\n\n- [[aws-patch-manager-basics]]\n- [[aws-inspector-overview]]\n"
        )

        self.assertIn("[[aws-patch-manager-basics]]", sanitized)
        self.assertIn("[[aws-inspector-overview]]", sanitized)

    def test_malformed_suspicious_lines_do_not_become_graph_noise(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-aws-patching-strategy.md"),
                text=(
                    "# Summary\n\n"
                    '!"$domain" =~ ^\n'
                    "[[progress.png]]\n"
                    "github/repo/blob/main/file.sh\n"
                    "Useful security guidance remains.\n"
                ),
                root=self.root,
            )
        )

        saved = output_path.read_text(encoding="utf-8")
        self.assertIn("Useful security guidance remains.", saved)
        self.assertNotIn('!"$domain" =~ ^', saved)
        self.assertNotIn("[[progress.png]]", saved)
        self.assertNotIn("github/repo/blob/main/file.sh", saved)

    def test_generation_method_becomes_manual_paste(self) -> None:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=Path("metadata/prompts/compile-aws-patching-strategy.md"),
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

    def test_no_overwrite_by_default(self) -> None:
        request = ApplySynthesisRequest(
            prompt_pack=Path("metadata/prompts/compile-aws-patching-strategy.md"),
            text="# Summary\n\nInitial synthesis.",
            root=self.root,
        )

        first_output = apply_synthesis(request)
        self.assertTrue(first_output.exists())

        with self.assertRaises(FileExistsError):
            apply_synthesis(request)


if __name__ == "__main__":
    unittest.main()

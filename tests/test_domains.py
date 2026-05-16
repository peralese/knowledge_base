from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.domains import (
    create_domain,
    load_domains,
    metadata_file,
    slugify_domain,
)
from scripts.ingest import IngestRequest, ingest_source
from scripts.query_engine import load_context, save_answer
from scripts.stage_to_inbox import StageRequest, stage_clipboard


class DomainModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_slugify_domain(self) -> None:
        self.assertEqual(slugify_domain("Civil War History"), "civil-war-history")
        self.assertEqual(slugify_domain("  AI / Agents! "), "ai-agents")
        self.assertEqual(slugify_domain(""), "inbox")

    def test_create_domain_persists_config_and_directories(self) -> None:
        domain = create_domain("Civil War History", root=self.root)

        self.assertEqual(domain.slug, "civil-war-history")
        self.assertTrue((self.root / "metadata" / "domains.json").exists())
        self.assertTrue((self.root / "raw" / "domains" / domain.slug / "articles").exists())
        self.assertTrue((self.root / "compiled" / "domains" / domain.slug / "topics").exists())

        loaded = load_domains(self.root)
        self.assertIn("civil-war-history", [item.slug for item in loaded])


class DomainRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)
        create_domain("Civil War History", root=self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_stage_and_ingest_route_into_domain_paths(self) -> None:
        staged = stage_clipboard(
            StageRequest(
                adapter="clipboard",
                title="Antietam Note",
                text="Battle context.",
                domain="civil-war-history",
                root=self.root,
            )
        )
        self.assertEqual(
            staged.relative_to(self.root),
            Path("raw/domains/civil-war-history/inbox/clipboard/antietam-note.md"),
        )

        output = ingest_source(
            IngestRequest(
                title="Antietam Note",
                source_type="article",
                origin="clipboard",
                input_path=str(staged),
                domain="civil-war-history",
                root=self.root,
            )
        )

        self.assertEqual(
            output.relative_to(self.root),
            Path("raw/domains/civil-war-history/articles/antietam-note.md"),
        )
        manifest = json.loads(
            metadata_file(self.root, "civil-war-history", "source-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["sources"][0]["domain"], "civil-war-history")

    def test_query_context_defaults_to_selected_domain(self) -> None:
        topic_dir = self.root / "compiled" / "domains"
        (topic_dir / "ai" / "topics").mkdir(parents=True, exist_ok=True)
        (topic_dir / "civil-war-history" / "topics").mkdir(parents=True, exist_ok=True)
        (topic_dir / "ai" / "topics" / "agents.md").write_text(
            "---\ntitle: Agents\n---\n\nAI agent context.\n",
            encoding="utf-8",
        )
        (topic_dir / "civil-war-history" / "topics" / "antietam.md").write_text(
            "---\ntitle: Antietam\n---\n\nCivil War context.\n",
            encoding="utf-8",
        )

        context, paths = load_context(None, self.root, domain="civil-war-history")

        self.assertIn("Civil War context", context)
        self.assertNotIn("AI agent context", context)
        self.assertEqual(paths, ["compiled/domains/civil-war-history/topics/antietam.md"])

    def test_answers_are_saved_under_domain(self) -> None:
        path = save_answer(
            "What happened?",
            "Domain scoped answer.",
            [],
            None,
            self.root / "outputs",
            domain="civil-war-history",
        )

        self.assertEqual(path.parent.relative_to(self.root), Path("outputs/domains/civil-war-history/answers"))
        self.assertTrue(path.name.endswith("-what-happened.md"))


if __name__ == "__main__":
    unittest.main()

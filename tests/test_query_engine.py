from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.query_engine import (
    build_query_prompt,
    load_context,
    read_answer,
    save_answer,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class QueryEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write(
            self.root / "compiled" / "topics" / "openclaw-security.md",
            """---
title: OpenClaw Security
compiled_from:
  - hardening-openclaw-synthesis
---

OpenClaw topic body. See [[hardening-openclaw-synthesis]].
""",
        )
        _write(
            self.root / "compiled" / "source_summaries" / "hardening-openclaw-synthesis.md",
            """---
title: Hardening OpenClaw
approved: true
---

Use least privilege.
""",
        )
        _write(
            self.root / "compiled" / "topics" / "ollama.md",
            """---
title: Ollama
---

Ollama topic body.
""",
        )
        _write(
            self.root / "compiled" / "index.md",
            "- [[openclaw-security]] — OpenClaw Security\n- [[ollama]] — Ollama\n",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_topic_context_loads_topic_and_linked_source_summary(self) -> None:
        context, paths = load_context("openclaw-security", self.root)
        self.assertIn("OpenClaw topic body", context)
        self.assertIn("Use least privilege", context)
        self.assertIn("compiled/topics/openclaw-security.md", paths)
        self.assertIn("compiled/source_summaries/hardening-openclaw-synthesis.md", paths)

    def test_full_context_loads_topic_notes_only(self) -> None:
        context, paths = load_context(None, self.root)
        self.assertIn("OpenClaw topic body", context)
        self.assertIn("Ollama topic body", context)
        self.assertNotIn("Use least privilege", context)
        self.assertEqual(paths, [
            "compiled/topics/openclaw-security.md",
            "compiled/topics/ollama.md",
        ])

    def test_build_query_prompt_contains_required_parts(self) -> None:
        prompt = build_query_prompt("What is risky?", "Context text")
        self.assertIn("based only on the provided context", prompt)
        self.assertIn("Context text", prompt)
        self.assertIn("Question: What is risky?", prompt)

    def test_save_answer_creates_expected_frontmatter_and_read_back(self) -> None:
        path = save_answer(
            "What are the risks?",
            "The answer.",
            ["compiled/topics/openclaw-security.md"],
            "openclaw-security",
            self.root / "outputs",
        )
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn('question: "What are the risks?"', text)
        self.assertIn("topic: openclaw-security", text)
        self.assertIn("sources:\n  - compiled/topics/openclaw-security.md", text)
        data = read_answer(self.root / "outputs", path.name)
        self.assertEqual(data["question"], "What are the risks?")
        self.assertEqual(data["topic"], "openclaw-security")
        self.assertIn("The answer.", data["answer"])


if __name__ == "__main__":
    unittest.main()

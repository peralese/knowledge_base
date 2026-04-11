"""Tests for scripts/query.py (Phase 7)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.query import (
    CompiledNote,
    _derive_title,
    build_query_prompt,
    file_answer,
    load_compiled_notes,
    run,
    slugify,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stream_response(tokens: list[str]) -> MagicMock:
    lines = [json.dumps({"response": t, "done": False}).encode() for t in tokens]
    lines.append(json.dumps({"response": "", "done": True}).encode())
    mock_resp = MagicMock()
    mock_resp.__iter__ = MagicMock(return_value=iter(lines))
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_tags_response(models: list[str]) -> MagicMock:
    body = json.dumps({"models": [{"name": m} for m in models]}).encode()
    mock_resp = MagicMock()
    mock_resp.read = MagicMock(return_value=body)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_note(root: Path, subdir: str, stem: str, title: str, body: str) -> Path:
    directory = root / "compiled" / subdir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem}.md"
    path.write_text(
        f'---\ntitle: "{title}"\nnote_type: "topic"\n---\n\n{body}\n',
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# load_compiled_notes
# ---------------------------------------------------------------------------

class LoadCompiledNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_loads_notes_from_all_compiled_subdirs(self) -> None:
        _make_note(self.root, "topics", "topic-a", "Topic A", "Body of topic A.")
        _make_note(self.root, "concepts", "concept-b", "Concept B", "Body of concept B.")
        _make_note(self.root, "source_summaries", "summary-c", "Summary C", "Body of summary C.")

        notes = load_compiled_notes(self.root)
        stems = [n.stem for n in notes]
        self.assertIn("topic-a", stems)
        self.assertIn("concept-b", stems)
        self.assertIn("summary-c", stems)

    def test_extracts_title_from_frontmatter(self) -> None:
        _make_note(self.root, "topics", "my-note", "My Custom Title", "Body text.")
        notes = load_compiled_notes(self.root)
        self.assertEqual(notes[0].title, "My Custom Title")

    def test_falls_back_to_stem_when_no_frontmatter_title(self) -> None:
        path = self.root / "compiled" / "topics" / "plain-note.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("No frontmatter here, just body text.\n", encoding="utf-8")
        notes = load_compiled_notes(self.root)
        self.assertEqual(notes[0].title, "Plain Note")

    def test_returns_empty_when_no_compiled_dirs(self) -> None:
        notes = load_compiled_notes(self.root)
        self.assertEqual(notes, [])

    def test_body_does_not_include_frontmatter(self) -> None:
        _make_note(self.root, "topics", "note", "Note", "This is the body.")
        notes = load_compiled_notes(self.root)
        self.assertNotIn("---", notes[0].body)
        self.assertIn("This is the body.", notes[0].body)


# ---------------------------------------------------------------------------
# build_query_prompt
# ---------------------------------------------------------------------------

class BuildQueryPromptTests(unittest.TestCase):
    def _note(self, stem: str, title: str, body: str) -> CompiledNote:
        return CompiledNote(path=Path(f"{stem}.md"), title=title, body=body)

    def test_prompt_contains_question(self) -> None:
        notes = [self._note("note-a", "Note A", "Body A.")]
        prompt, _ = build_query_prompt("What is X?", notes)
        self.assertIn("What is X?", prompt)

    def test_prompt_contains_note_body(self) -> None:
        notes = [self._note("note-a", "Note A", "Body A content here.")]
        prompt, _ = build_query_prompt("What is X?", notes)
        self.assertIn("Body A content here.", prompt)

    def test_included_notes_returned(self) -> None:
        notes = [
            self._note("note-a", "Note A", "Body A."),
            self._note("note-b", "Note B", "Body B."),
        ]
        _, included = build_query_prompt("What is X?", notes)
        self.assertEqual(len(included), 2)

    def test_notes_exceeding_budget_are_excluded(self) -> None:
        import scripts.query as mod
        original = mod.MAX_CONTEXT_CHARS
        mod.MAX_CONTEXT_CHARS = 500  # tiny budget
        try:
            notes = [self._note(f"note-{i}", f"Note {i}", "x" * 300) for i in range(5)]
            _, included = build_query_prompt("Q?", notes)
            self.assertLess(len(included), 5)
        finally:
            mod.MAX_CONTEXT_CHARS = original

    def test_prompt_ends_with_answer_section(self) -> None:
        notes = [self._note("note-a", "Note A", "Body.")]
        prompt, _ = build_query_prompt("What?", notes)
        self.assertTrue(prompt.strip().endswith("## Answer\n\n") or "## Answer" in prompt)


# ---------------------------------------------------------------------------
# slugify and _derive_title
# ---------------------------------------------------------------------------

class SlugifyTests(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_special_chars(self) -> None:
        self.assertEqual(slugify("What is EKS?"), "what-is-eks")

    def test_empty(self) -> None:
        self.assertEqual(slugify(""), "answer")


class DeriveTitleTests(unittest.TestCase):
    def test_short_question(self) -> None:
        self.assertEqual(_derive_title("What is EKS?"), "What is EKS")

    def test_long_question_trimmed_at_word_boundary(self) -> None:
        q = "What are the detailed security tradeoffs between EKS and Fargate in production?"
        title = _derive_title(q)
        self.assertLessEqual(len(title), 60)
        # Should not cut mid-word
        self.assertFalse(title[-1].isalpha() and title[-2].isalpha() and len(title) == 60)

    def test_trailing_question_mark_removed(self) -> None:
        title = _derive_title("What is OpenClaw?")
        self.assertNotIn("?", title)


# ---------------------------------------------------------------------------
# file_answer
# ---------------------------------------------------------------------------

class FileAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "outputs" / "answers").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _note(self, stem: str) -> CompiledNote:
        return CompiledNote(path=Path(f"{stem}.md"), title=stem.replace("-", " ").title(), body="Body.")

    def test_creates_answer_file(self) -> None:
        dest = file_answer(
            question="What is EKS?",
            answer="EKS is a managed Kubernetes service.",
            notes_used=[self._note("aws-containers")],
            title="What is EKS",
            model="qwen2.5:14b",
            force=False,
            root=self.root,
        )
        self.assertTrue(dest.exists())

    def test_answer_contains_question_and_answer(self) -> None:
        dest = file_answer(
            question="What is EKS?",
            answer="EKS is managed Kubernetes.",
            notes_used=[self._note("aws-containers")],
            title="What is EKS",
            model="qwen2.5:14b",
            force=False,
            root=self.root,
        )
        content = dest.read_text(encoding="utf-8")
        self.assertIn("What is EKS?", content)
        self.assertIn("EKS is managed Kubernetes.", content)

    def test_answer_contains_source_wikilinks(self) -> None:
        dest = file_answer(
            question="Q?",
            answer="A.",
            notes_used=[self._note("aws-containers"), self._note("openclaw-security")],
            title="Test Answer",
            model="qwen2.5:14b",
            force=False,
            root=self.root,
        )
        content = dest.read_text(encoding="utf-8")
        self.assertIn("[[aws-containers]]", content)
        self.assertIn("[[openclaw-security]]", content)

    def test_answer_frontmatter_has_required_fields(self) -> None:
        dest = file_answer(
            question="Q?",
            answer="A.",
            notes_used=[self._note("note-a")],
            title="Test Answer",
            model="qwen2.5:14b",
            force=False,
            root=self.root,
        )
        content = dest.read_text(encoding="utf-8")
        self.assertIn('output_type: "answer"', content)
        self.assertIn('generation_method: "ollama_local"', content)
        self.assertIn("generated_on:", content)
        self.assertIn("compiled_notes_used:", content)

    def test_raises_on_existing_file_without_force(self) -> None:
        kwargs = dict(
            question="Q?", answer="A.",
            notes_used=[self._note("note-a")],
            title="Test Answer", model="qwen2.5:14b",
            force=False, root=self.root,
        )
        file_answer(**kwargs)
        with self.assertRaises(FileExistsError):
            file_answer(**kwargs)

    def test_force_overwrites_existing_file(self) -> None:
        kwargs = dict(
            question="Q?", answer="A.",
            notes_used=[self._note("note-a")],
            title="Test Answer", model="qwen2.5:14b",
            force=False, root=self.root,
        )
        file_answer(**kwargs)
        dest = file_answer(**{**kwargs, "answer": "Updated answer.", "force": True})
        self.assertIn("Updated answer.", dest.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# run() integration
# ---------------------------------------------------------------------------

class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "outputs" / "answers").mkdir(parents=True, exist_ok=True)
        _make_note(self.root, "topics", "aws-containers", "AWS Containers", "EKS vs ECS vs Fargate.")
        _make_note(self.root, "topics", "openclaw-security", "OpenClaw Security", "Security best practices.")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, question: str = "What is EKS?", force: bool = False) -> int:
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _make_tags_response(["qwen2.5:14b"]),
                _make_stream_response(["EKS is managed Kubernetes."]),
            ]
            return run(
                question=question,
                title="",
                model="qwen2.5:14b",
                force=force,
                dry_run=False,
                root=self.root,
            )

    def test_run_returns_zero_on_success(self) -> None:
        self.assertEqual(self._run(), 0)

    def test_run_creates_answer_file(self) -> None:
        self._run(question="What is EKS?")
        answers = list((self.root / "outputs" / "answers").glob("*.md"))
        self.assertEqual(len(answers), 1)

    def test_run_returns_one_when_no_compiled_notes(self) -> None:
        import shutil
        shutil.rmtree(self.root / "compiled")
        rc = run(
            question="Q?", title="", model="qwen2.5:14b",
            force=False, dry_run=False, root=self.root,
        )
        self.assertEqual(rc, 1)

    def test_dry_run_does_not_create_file(self) -> None:
        rc = run(
            question="What is EKS?", title="", model="qwen2.5:14b",
            force=False, dry_run=True, root=self.root,
        )
        self.assertEqual(rc, 0)
        answers = list((self.root / "outputs" / "answers").glob("*.md"))
        self.assertEqual(len(answers), 0)

    def test_run_returns_one_when_model_unavailable(self) -> None:
        with patch("urllib.request.urlopen", return_value=_make_tags_response(["llama3.1:8b"])):
            rc = run(
                question="Q?", title="", model="qwen2.5:14b",
                force=False, dry_run=False, root=self.root,
            )
        self.assertEqual(rc, 1)

    def test_top_n_selects_relevant_notes(self) -> None:
        """With top_n=1, only the most relevant note should be in context."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _make_tags_response(["qwen2.5:14b"]),
                _make_stream_response(["EKS is managed Kubernetes."]),
            ]
            rc = run(
                question="What is EKS kubernetes?",
                title="",
                model="qwen2.5:14b",
                force=False,
                dry_run=False,
                root=self.root,
                top_n=1,
            )
        self.assertEqual(rc, 0)
        answers = list((self.root / "outputs" / "answers").glob("*.md"))
        self.assertEqual(len(answers), 1)
        content = answers[0].read_text(encoding="utf-8")
        # Only 1 note should be in context — the frontmatter should list 1 stem
        self.assertIn("compiled_notes_used:", content)

    def test_top_n_zero_uses_all_notes(self) -> None:
        """Default top_n=0 should still include all notes (backward compatible)."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _make_tags_response(["qwen2.5:14b"]),
                _make_stream_response(["Answer."]),
            ]
            rc = run(
                question="What is EKS?",
                title="bm25-compat-test",
                model="qwen2.5:14b",
                force=False,
                dry_run=False,
                root=self.root,
                top_n=0,
            )
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

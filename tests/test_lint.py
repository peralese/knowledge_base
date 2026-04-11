"""Tests for scripts/lint.py (Phase 9)."""
from __future__ import annotations

import io
import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.lint import (
    LintIssue,
    build_report,
    check_dangling_wikilinks,
    check_orphaned_raw_notes,
    file_report,
    run,
    _parse_compiled_from,
    _strip_frontmatter,
    _all_known_stems,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _compiled_note(root: Path, subdir: str, stem: str, compiled_from: list[str], body: str = "Body.") -> Path:
    refs = "\n".join(f'  - "{s}"' for s in compiled_from)
    content = (
        f'---\ntitle: "{stem.replace("-", " ").title()}"\n'
        f"note_type: \"topic\"\n"
        f"compiled_from: \n{refs}\n"
        f"---\n\n{body}\n"
    )
    return _write(root, f"compiled/{subdir}/{stem}.md", content)


# ---------------------------------------------------------------------------
# _strip_frontmatter
# ---------------------------------------------------------------------------

class StripFrontmatterTests(unittest.TestCase):
    def test_strips_frontmatter(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\nBody.\n"
        self.assertEqual(_strip_frontmatter(text), "Body.")

    def test_no_frontmatter_returns_text(self) -> None:
        self.assertEqual(_strip_frontmatter("Just body."), "Just body.")


# ---------------------------------------------------------------------------
# _parse_compiled_from
# ---------------------------------------------------------------------------

class ParseCompiledFromTests(unittest.TestCase):
    def test_parses_single_ref(self) -> None:
        text = '---\ncompiled_from: \n  - "my-article"\n---\n\nBody.\n'
        self.assertEqual(_parse_compiled_from(text), ["my-article"])

    def test_parses_multiple_refs(self) -> None:
        text = '---\ncompiled_from: \n  - "article-a"\n  - "article-b"\n---\n\nBody.\n'
        self.assertEqual(_parse_compiled_from(text), ["article-a", "article-b"])

    def test_parses_refs_without_quotes(self) -> None:
        text = "---\ncompiled_from: \n  - my-article\n---\n\nBody.\n"
        self.assertEqual(_parse_compiled_from(text), ["my-article"])

    def test_returns_empty_when_no_compiled_from(self) -> None:
        text = "---\ntitle: \"T\"\n---\n\nBody.\n"
        self.assertEqual(_parse_compiled_from(text), [])

    def test_returns_empty_when_no_frontmatter(self) -> None:
        self.assertEqual(_parse_compiled_from("Just body."), [])

    def test_stops_at_next_key(self) -> None:
        text = '---\ncompiled_from: \n  - "article-a"\ntags: \n  - "tag"\n---\n\nBody.\n'
        self.assertEqual(_parse_compiled_from(text), ["article-a"])


# ---------------------------------------------------------------------------
# _all_known_stems
# ---------------------------------------------------------------------------

class AllKnownStemsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_includes_compiled_stems(self) -> None:
        _write(self.root, "compiled/topics/my-topic.md", "Body.")
        stems = _all_known_stems(self.root)
        self.assertIn("my-topic", stems)

    def test_includes_raw_stems(self) -> None:
        _write(self.root, "raw/articles/my-article.md", "Body.")
        stems = _all_known_stems(self.root)
        self.assertIn("my-article", stems)

    def test_empty_when_no_dirs(self) -> None:
        self.assertEqual(_all_known_stems(self.root), set())


# ---------------------------------------------------------------------------
# check_dangling_wikilinks
# ---------------------------------------------------------------------------

class CheckDanglingWikilinksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_no_issues_when_wikilinks_valid(self) -> None:
        _write(self.root, "compiled/topics/note-a.md", "Body with [[note-b]].")
        _write(self.root, "compiled/topics/note-b.md", "Body.")
        self.assertEqual(check_dangling_wikilinks(self.root), [])

    def test_detects_missing_wikilink_target(self) -> None:
        _write(self.root, "compiled/topics/note-a.md", "Body with [[missing-note]].")
        issues = check_dangling_wikilinks(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("missing-note", issues[0].message)

    def test_wikilink_to_raw_note_is_valid(self) -> None:
        _write(self.root, "compiled/topics/note-a.md", "Body with [[raw-article]].")
        _write(self.root, "raw/articles/raw-article.md", "Raw body.")
        self.assertEqual(check_dangling_wikilinks(self.root), [])

    def test_detail_contains_source_path(self) -> None:
        _write(self.root, "compiled/topics/note-a.md", "Body with [[ghost]].")
        issues = check_dangling_wikilinks(self.root)
        self.assertIn("compiled/topics/note-a.md", issues[0].detail)

    def test_deduplicate_same_missing_link(self) -> None:
        _write(self.root, "compiled/topics/note-a.md", "[[ghost]] and [[ghost]] again.")
        issues = check_dangling_wikilinks(self.root)
        self.assertEqual(len(issues), 1)

    def test_skips_index_md(self) -> None:
        _write(self.root, "compiled/index.md", "Body with [[ghost]].")
        self.assertEqual(check_dangling_wikilinks(self.root), [])

    def test_no_issues_when_compiled_dir_missing(self) -> None:
        self.assertEqual(check_dangling_wikilinks(self.root), [])

    def test_wikilinks_with_pipe_aliases_checked_by_slug(self) -> None:
        # [[slug|Display Name]] — only the slug part should be checked
        _write(self.root, "compiled/topics/note-a.md", "[[real-note|Real Note]].")
        _write(self.root, "compiled/topics/real-note.md", "Body.")
        self.assertEqual(check_dangling_wikilinks(self.root), [])

    def test_multiple_missing_links_in_one_note(self) -> None:
        _write(self.root, "compiled/topics/note-a.md", "[[ghost-1]] and [[ghost-2]].")
        issues = check_dangling_wikilinks(self.root)
        self.assertEqual(len(issues), 2)

    def test_check_field_is_wikilinks(self) -> None:
        _write(self.root, "compiled/topics/note-a.md", "[[ghost]].")
        issues = check_dangling_wikilinks(self.root)
        self.assertEqual(issues[0].check, "wikilinks")


# ---------------------------------------------------------------------------
# check_orphaned_raw_notes
# ---------------------------------------------------------------------------

class CheckOrphanedRawNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_no_issues_when_all_raw_referenced(self) -> None:
        _write(self.root, "raw/articles/my-article.md", "Raw.")
        _compiled_note(self.root, "topics", "my-topic", ["my-article"])
        self.assertEqual(check_orphaned_raw_notes(self.root), [])

    def test_detects_unreferenced_raw_note(self) -> None:
        _write(self.root, "raw/articles/orphan.md", "Raw.")
        issues = check_orphaned_raw_notes(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertIn("orphan", issues[0].message)

    def test_checks_all_raw_subdirs(self) -> None:
        _write(self.root, "raw/articles/article.md", "Raw.")
        _write(self.root, "raw/notes/note.md", "Raw.")
        _write(self.root, "raw/pdfs/pdf-note.md", "Raw.")
        issues = check_orphaned_raw_notes(self.root)
        self.assertEqual(len(issues), 3)

    def test_no_issues_when_no_raw_notes(self) -> None:
        _compiled_note(self.root, "topics", "my-topic", [])
        self.assertEqual(check_orphaned_raw_notes(self.root), [])

    def test_check_field_is_orphans(self) -> None:
        _write(self.root, "raw/articles/orphan.md", "Raw.")
        issues = check_orphaned_raw_notes(self.root)
        self.assertEqual(issues[0].check, "orphans")

    def test_multiple_compiled_froms_can_cover_same_raw(self) -> None:
        _write(self.root, "raw/articles/shared.md", "Raw.")
        _compiled_note(self.root, "topics", "topic-a", ["shared"])
        _compiled_note(self.root, "topics", "topic-b", ["shared"])
        self.assertEqual(check_orphaned_raw_notes(self.root), [])

    def test_raw_note_referenced_by_concept_is_not_orphan(self) -> None:
        _write(self.root, "raw/articles/article.md", "Raw.")
        _compiled_note(self.root, "concepts", "my-concept", ["article"])
        self.assertEqual(check_orphaned_raw_notes(self.root), [])


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

class BuildReportTests(unittest.TestCase):
    def _issue(self, check: str, severity: str, msg: str, detail: str = "") -> LintIssue:
        return LintIssue(check=check, severity=severity, message=msg, detail=detail)

    def test_contains_frontmatter(self) -> None:
        text = build_report([], ["wikilinks"], "2026-04-11")
        self.assertIn("---", text)
        self.assertIn('output_type: "lint_report"', text)

    def test_frontmatter_has_generated_on(self) -> None:
        text = build_report([], ["wikilinks"], "2026-04-11")
        self.assertIn('generated_on: "2026-04-11"', text)

    def test_frontmatter_error_count(self) -> None:
        issues = [self._issue("wikilinks", "error", "msg")]
        text = build_report(issues, ["wikilinks"], "2026-04-11")
        self.assertIn("errors: 1", text)

    def test_frontmatter_warning_count(self) -> None:
        issues = [self._issue("orphans", "warning", "msg")]
        text = build_report(issues, ["orphans"], "2026-04-11")
        self.assertIn("warnings: 1", text)

    def test_errors_section_present(self) -> None:
        issues = [self._issue("wikilinks", "error", "Missing [[x]]")]
        text = build_report(issues, ["wikilinks"], "2026-04-11")
        self.assertIn("## Errors", text)
        self.assertIn("Missing [[x]]", text)

    def test_warnings_section_present(self) -> None:
        issues = [self._issue("orphans", "warning", "Orphaned note")]
        text = build_report(issues, ["orphans"], "2026-04-11")
        self.assertIn("## Warnings", text)
        self.assertIn("Orphaned note", text)

    def test_none_shown_when_no_errors(self) -> None:
        text = build_report([], ["wikilinks"], "2026-04-11")
        self.assertIn("_(none)_", text)

    def test_checks_run_in_frontmatter(self) -> None:
        text = build_report([], ["wikilinks", "orphans"], "2026-04-11")
        self.assertIn('"wikilinks"', text)
        self.assertIn('"orphans"', text)

    def test_detail_appears_in_report(self) -> None:
        issues = [self._issue("wikilinks", "error", "Missing [[x]]", detail="compiled/topics/note.md")]
        text = build_report(issues, ["wikilinks"], "2026-04-11")
        self.assertIn("compiled/topics/note.md", text)

    def test_total_issues_count(self) -> None:
        issues = [
            self._issue("wikilinks", "error", "e1"),
            self._issue("orphans", "warning", "w1"),
        ]
        text = build_report(issues, ["wikilinks", "orphans"], "2026-04-11")
        self.assertIn("total_issues: 2", text)


# ---------------------------------------------------------------------------
# file_report
# ---------------------------------------------------------------------------

class FileReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_creates_report_file(self) -> None:
        file_report("content", self.root, "2026-04-11", force=False)
        self.assertTrue((self.root / "outputs" / "reports" / "lint-2026-04-11.md").exists())

    def test_raises_on_existing_without_force(self) -> None:
        file_report("content", self.root, "2026-04-11", force=False)
        with self.assertRaises(FileExistsError):
            file_report("content2", self.root, "2026-04-11", force=False)

    def test_force_overwrites(self) -> None:
        file_report("content", self.root, "2026-04-11", force=False)
        file_report("updated", self.root, "2026-04-11", force=True)
        text = (self.root / "outputs" / "reports" / "lint-2026-04-11.md").read_text(encoding="utf-8")
        self.assertEqual(text, "updated")

    def test_creates_parent_dirs(self) -> None:
        dest = file_report("content", self.root, "2026-04-11", force=False)
        self.assertTrue(dest.parent.exists())


# ---------------------------------------------------------------------------
# run() integration
# ---------------------------------------------------------------------------

class RunIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write(self.root, "raw/articles/my-article.md", "Raw body.")
        _compiled_note(self.root, "topics", "my-topic", ["my-article"], "Body with [[my-article]].")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_returns_zero_on_clean_wiki(self) -> None:
        rc = run(self.root, checks=[], use_llm=False, model="x",
                 report=False, force=False, dry_run=False)
        self.assertEqual(rc, 0)

    def test_returns_zero_with_issues(self) -> None:
        # Issues don't cause non-zero exit — they are informational
        _write(self.root, "compiled/topics/bad-links.md", "[[ghost]].")
        rc = run(self.root, checks=["wikilinks"], use_llm=False, model="x",
                 report=False, force=False, dry_run=False)
        self.assertEqual(rc, 0)

    def test_dry_run_does_not_create_report(self) -> None:
        run(self.root, checks=[], use_llm=False, model="x",
            report=True, force=False, dry_run=True)
        reports = list((self.root / "outputs").rglob("*.md")) if (self.root / "outputs").exists() else []
        self.assertEqual(reports, [])

    def test_report_flag_creates_file(self) -> None:
        run(self.root, checks=[], use_llm=False, model="x",
            report=True, force=False, dry_run=False)
        reports = list((self.root / "outputs" / "reports").glob("lint-*.md"))
        self.assertEqual(len(reports), 1)

    def test_llm_check_returns_one_when_model_unavailable(self) -> None:
        with patch("urllib.request.urlopen") as mock_urlopen:
            data = json.dumps({"models": [{"name": "other-model"}]}).encode()
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = lambda s, *a: False
            mock_urlopen.return_value.read = lambda: data
            rc = run(self.root, checks=[], use_llm=True, model="qwen2.5:14b",
                     report=False, force=False, dry_run=False)
        self.assertEqual(rc, 1)

    def test_specific_check_only_runs_that_check(self) -> None:
        # Add an orphan — if orphans check runs it would show up
        _write(self.root, "raw/articles/orphan.md", "Raw.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(self.root, checks=["wikilinks"], use_llm=False, model="x",
                report=False, force=False, dry_run=False)
        output = buf.getvalue()
        self.assertIn("wikilinks", output)
        self.assertNotIn("orphans", output)

    def test_default_checks_are_pure_only(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(self.root, checks=[], use_llm=False, model="x",
                report=False, force=False, dry_run=False)
        output = buf.getvalue()
        self.assertIn("wikilinks", output)
        self.assertIn("orphans", output)
        self.assertNotIn("coverage", output)


if __name__ == "__main__":
    unittest.main()

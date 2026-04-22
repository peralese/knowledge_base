"""Tests for scripts/lint.py (Phase 6)."""
from __future__ import annotations

import io
import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.lint import (
    LintIssue,
    _all_known_stems,
    _build_concept_stub,
    _parse_compiled_from,
    _parse_json_array,
    _parse_title,
    _strip_frontmatter,
    build_report,
    check_contradictions,
    check_dangling_wikilinks,
    check_missing_concepts,
    check_orphan_summaries,
    check_orphaned_raw_notes,
    check_unapproved,
    file_report,
    run,
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


# ---------------------------------------------------------------------------
# Helpers for new tests
# ---------------------------------------------------------------------------

def _write_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _topic_note_text(compiled_from: list[str], title: str = "Test Topic") -> str:
    items = "\n".join(f'  - "{s}"' for s in compiled_from)
    return (
        "---\n"
        f'title: "{title}"\n'
        'note_type: "topic"\n'
        "compiled_from:\n"
        f"{items}\n"
        "---\n\n"
        "# Summary\n\nTopic body.\n"
    )


def _source_summary_text(body: str = "Source body content.") -> str:
    return (
        "---\n"
        'title: "Source Summary"\n'
        'note_type: "source_summary"\n'
        "compiled_from:\n"
        '  - "raw-article"\n'
        "---\n\n"
        f"{body}\n"
    )


def _queue_entry_dict(
    source_id: str = "SRC-20260417-0001",
    confidence_band: str = "high",
    review_action: str | None = "approved",
    title: str = "Test Article",
) -> dict:
    entry: dict = {
        "source_id": source_id,
        "title": title,
        "confidence_band": confidence_band,
        "review_status": "synthesized",
    }
    if review_action is not None:
        entry["review_action"] = review_action
    return entry


# ---------------------------------------------------------------------------
# _parse_json_array
# ---------------------------------------------------------------------------

class ParseJsonArrayTests(unittest.TestCase):
    def test_valid_string_array(self) -> None:
        self.assertEqual(_parse_json_array('["a", "b"]'), ["a", "b"])

    def test_array_embedded_in_prose(self) -> None:
        self.assertEqual(_parse_json_array('Result: ["foo", "bar"] done.'), ["foo", "bar"])

    def test_empty_array(self) -> None:
        self.assertEqual(_parse_json_array("[]"), [])

    def test_malformed_json_returns_empty(self) -> None:
        self.assertEqual(_parse_json_array("[not valid json"), [])

    def test_no_array_returns_empty(self) -> None:
        self.assertEqual(_parse_json_array("no array here"), [])

    def test_object_array(self) -> None:
        result = _parse_json_array('[{"a": 1}, {"b": 2}]')
        self.assertEqual(result, [{"a": 1}, {"b": 2}])


# ---------------------------------------------------------------------------
# _parse_title
# ---------------------------------------------------------------------------

class ParseTitleTests(unittest.TestCase):
    def test_quoted_title(self) -> None:
        self.assertEqual(_parse_title('---\ntitle: "My Topic"\n---\n\nbody'), "My Topic")

    def test_unquoted_title(self) -> None:
        self.assertEqual(_parse_title("---\ntitle: My Topic\n---\n\nbody"), "My Topic")

    def test_no_frontmatter_returns_none(self) -> None:
        self.assertIsNone(_parse_title("no frontmatter here"))

    def test_no_title_field_returns_none(self) -> None:
        self.assertIsNone(_parse_title("---\nnote_type: topic\n---\n\nbody"))


# ---------------------------------------------------------------------------
# _build_concept_stub
# ---------------------------------------------------------------------------

class BuildConceptStubTests(unittest.TestCase):
    def test_slug_converted_to_title(self) -> None:
        stub = _build_concept_stub("vulnerability-scoring", "2026-04-17")
        self.assertIn('title: "Vulnerability Scoring"', stub)
        self.assertIn("# Vulnerability Scoring", stub)

    def test_required_frontmatter_fields(self) -> None:
        stub = _build_concept_stub("patch-cadence", "2026-04-17")
        self.assertIn("note_type: concept", stub)
        self.assertIn('generation_method: "stub"', stub)
        self.assertIn('date_compiled: "2026-04-17"', stub)
        self.assertIn("slug: patch-cadence", stub)
        self.assertIn("sources: []", stub)

    def test_body_references_lint_fix(self) -> None:
        stub = _build_concept_stub("zero-trust", "2026-04-17")
        self.assertIn("lint --fix", stub)


# ---------------------------------------------------------------------------
# check_orphan_summaries
# ---------------------------------------------------------------------------

class CheckOrphanSummariesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_linked_summary_no_issue(self) -> None:
        _write_file(
            self.root / "compiled" / "topics" / "my-topic.md",
            _topic_note_text(["article-one-synthesis"]),
        )
        _write_file(
            self.root / "compiled" / "source_summaries" / "article-one-synthesis.md",
            _source_summary_text(),
        )
        self.assertEqual(check_orphan_summaries(self.root), [])

    def test_unlinked_summary_flagged(self) -> None:
        _write_file(
            self.root / "compiled" / "topics" / "my-topic.md",
            _topic_note_text(["other-synthesis"]),
        )
        _write_file(
            self.root / "compiled" / "source_summaries" / "article-one-synthesis.md",
            _source_summary_text(),
        )
        issues = check_orphan_summaries(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertIn("article-one-synthesis", issues[0].message)

    def test_no_topic_notes_all_flagged(self) -> None:
        _write_file(
            self.root / "compiled" / "source_summaries" / "article-one-synthesis.md",
            _source_summary_text(),
        )
        _write_file(
            self.root / "compiled" / "source_summaries" / "article-two-synthesis.md",
            _source_summary_text(),
        )
        self.assertEqual(len(check_orphan_summaries(self.root)), 2)

    def test_empty_summaries_dir_no_issues(self) -> None:
        (self.root / "compiled" / "source_summaries").mkdir(parents=True)
        self.assertEqual(check_orphan_summaries(self.root), [])

    def test_no_summaries_dir_no_issues(self) -> None:
        self.assertEqual(check_orphan_summaries(self.root), [])

    def test_check_field_is_orphan_summaries(self) -> None:
        _write_file(
            self.root / "compiled" / "source_summaries" / "orphan.md",
            _source_summary_text(),
        )
        issues = check_orphan_summaries(self.root)
        self.assertEqual(issues[0].check, "orphan_summaries")


# ---------------------------------------------------------------------------
# check_unapproved
# ---------------------------------------------------------------------------

class CheckUnapprovedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_queue(self, entries: list[dict]) -> None:
        (self.root / "metadata" / "review-queue.json").write_text(
            json.dumps(entries), encoding="utf-8"
        )

    def test_high_confidence_approved_no_issue(self) -> None:
        self._write_queue([_queue_entry_dict(confidence_band="high", review_action="approved")])
        self.assertEqual(check_unapproved(self.root), [])

    def test_medium_confidence_no_action_flagged(self) -> None:
        self._write_queue([_queue_entry_dict(
            source_id="SRC-001", confidence_band="medium", review_action=None
        )])
        issues = check_unapproved(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertIn("SRC-001", issues[0].message)
        self.assertIn("medium", issues[0].message)

    def test_low_confidence_no_action_flagged(self) -> None:
        self._write_queue([_queue_entry_dict(confidence_band="low", review_action=None)])
        issues = check_unapproved(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("low", issues[0].message)

    def test_low_confidence_manually_approved_no_issue(self) -> None:
        self._write_queue([_queue_entry_dict(confidence_band="low", review_action="approved")])
        self.assertEqual(check_unapproved(self.root), [])

    def test_missing_queue_file_no_issues(self) -> None:
        self.assertEqual(check_unapproved(self.root), [])

    def test_malformed_queue_no_crash(self) -> None:
        (self.root / "metadata" / "review-queue.json").write_text("not json", encoding="utf-8")
        self.assertEqual(check_unapproved(self.root), [])

    def test_only_unapproved_flagged_in_mixed_queue(self) -> None:
        self._write_queue([
            _queue_entry_dict(source_id="SRC-001", confidence_band="high", review_action="approved"),
            _queue_entry_dict(source_id="SRC-002", confidence_band="medium", review_action=None),
            _queue_entry_dict(source_id="SRC-003", confidence_band="low", review_action="rejected"),
            _queue_entry_dict(source_id="SRC-004", confidence_band="low", review_action=None),
        ])
        issues = check_unapproved(self.root)
        self.assertEqual(len(issues), 2)
        ids = {i.message.split("`")[1] for i in issues}
        self.assertEqual(ids, {"SRC-002", "SRC-004"})


# ---------------------------------------------------------------------------
# check_contradictions
# ---------------------------------------------------------------------------

class CheckContradictionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_topic(self, slug: str, sources: list[str]) -> None:
        _write_file(
            self.root / "compiled" / "topics" / f"{slug}.md",
            _topic_note_text(sources, title=slug.replace("-", " ").title()),
        )

    def _make_summary(self, stem: str, body: str = "Summary content.") -> None:
        _write_file(
            self.root / "compiled" / "source_summaries" / f"{stem}.md",
            _source_summary_text(body),
        )

    @patch("scripts.lint.call_ollama")
    def test_topic_with_one_source_skipped(self, mock_ollama: MagicMock) -> None:
        self._make_topic("my-topic", ["source-one"])
        self._make_summary("source-one")
        issues = check_contradictions(self.root, "test-model")
        mock_ollama.assert_not_called()
        self.assertEqual(issues, [])

    @patch("scripts.lint.call_ollama")
    def test_llm_returns_empty_no_issues(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = "[]"
        self._make_topic("my-topic", ["source-one", "source-two"])
        self._make_summary("source-one")
        self._make_summary("source-two")
        self.assertEqual(check_contradictions(self.root, "test-model"), [])

    @patch("scripts.lint.call_ollama")
    def test_llm_returns_contradiction(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = json.dumps([
            {"claim_a": "A is true", "claim_b": "A is false",
             "source_a": "source-one", "source_b": "source-two"},
        ])
        self._make_topic("my-topic", ["source-one", "source-two"])
        self._make_summary("source-one")
        self._make_summary("source-two")
        issues = check_contradictions(self.root, "test-model")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertIn("A is true", issues[0].message)
        self.assertIn("A is false", issues[0].message)
        self.assertIn("my-topic", issues[0].detail)

    @patch("scripts.lint.call_ollama")
    def test_malformed_json_no_crash(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = "not json at all"
        self._make_topic("my-topic", ["source-one", "source-two"])
        self._make_summary("source-one")
        self._make_summary("source-two")
        self.assertEqual(check_contradictions(self.root, "test-model"), [])

    @patch("scripts.lint.call_ollama")
    def test_topic_with_no_compiled_from_skipped(self, mock_ollama: MagicMock) -> None:
        _write_file(
            self.root / "compiled" / "topics" / "empty.md",
            '---\ntitle: "Empty"\nnote_type: "topic"\n---\n\nbody',
        )
        check_contradictions(self.root, "test-model")
        mock_ollama.assert_not_called()

    @patch("scripts.lint.call_ollama")
    def test_no_topics_dir_no_issues(self, mock_ollama: MagicMock) -> None:
        self.assertEqual(check_contradictions(self.root, "test-model"), [])

    @patch("scripts.lint.call_ollama")
    def test_multiple_contradictions(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = json.dumps([
            {"claim_a": "X is red", "claim_b": "X is blue", "source_a": "s1", "source_b": "s2"},
            {"claim_a": "Y is fast", "claim_b": "Y is slow", "source_a": "s1", "source_b": "s2"},
        ])
        self._make_topic("my-topic", ["s1", "s2"])
        self._make_summary("s1")
        self._make_summary("s2")
        self.assertEqual(len(check_contradictions(self.root, "test-model")), 2)


# ---------------------------------------------------------------------------
# check_missing_concepts
# ---------------------------------------------------------------------------

class CheckMissingConceptsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_index(self, content: str = "# Topics\n\n- [[openclaw-security]]\n") -> None:
        _write_file(self.root / "compiled" / "index.md", content)

    @patch("scripts.lint.call_ollama")
    def test_no_index_returns_info_issue(self, mock_ollama: MagicMock) -> None:
        issues = check_missing_concepts(self.root, "test-model")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "info")
        self.assertIn("index_notes.py", issues[0].message)
        mock_ollama.assert_not_called()

    @patch("scripts.lint.call_ollama")
    def test_llm_returns_slugs_one_issue_each(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = '["vulnerability-scoring", "patch-cadence"]'
        self._write_index()
        issues = check_missing_concepts(self.root, "test-model")
        self.assertEqual(len(issues), 2)
        messages = [i.message for i in issues]
        self.assertTrue(any("vulnerability-scoring" in m for m in messages))
        self.assertTrue(any("patch-cadence" in m for m in messages))
        for issue in issues:
            self.assertEqual(issue.severity, "info")

    @patch("scripts.lint.call_ollama")
    def test_llm_returns_empty_no_issues(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = "[]"
        self._write_index()
        self.assertEqual(check_missing_concepts(self.root, "test-model"), [])

    @patch("scripts.lint.call_ollama")
    def test_malformed_json_no_crash(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = "here are: foo, bar"
        self._write_index()
        self.assertEqual(check_missing_concepts(self.root, "test-model"), [])

    @patch("scripts.lint.call_ollama")
    def test_fix_creates_stub(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = '["zero-trust"]'
        self._write_index()
        check_missing_concepts(self.root, "test-model", fix=True)
        stub = self.root / "compiled" / "concepts" / "zero-trust.md"
        self.assertTrue(stub.exists())
        content = stub.read_text(encoding="utf-8")
        self.assertIn('title: "Zero Trust"', content)
        self.assertIn("note_type: concept", content)
        self.assertIn('generation_method: "stub"', content)

    @patch("scripts.lint.call_ollama")
    def test_fix_does_not_overwrite_existing(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = '["zero-trust"]'
        self._write_index()
        existing = self.root / "compiled" / "concepts" / "zero-trust.md"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("existing content", encoding="utf-8")
        check_missing_concepts(self.root, "test-model", fix=True)
        self.assertEqual(existing.read_text(encoding="utf-8"), "existing content")

    @patch("scripts.lint.call_ollama")
    def test_no_fix_flag_no_stubs(self, mock_ollama: MagicMock) -> None:
        mock_ollama.return_value = '["zero-trust"]'
        self._write_index()
        check_missing_concepts(self.root, "test-model", fix=False)
        self.assertFalse((self.root / "compiled" / "concepts" / "zero-trust.md").exists())


if __name__ == "__main__":
    unittest.main()

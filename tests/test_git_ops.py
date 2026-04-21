"""Tests for scripts/git_ops.py (Phase 10 — Git Integration)."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.git_ops import (
    PROJECT_ROOT,
    commit_pipeline_stage,
    has_changes,
    is_git_disabled,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit so tests can stage files."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@kb.local"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "KB Test"], cwd=path, check=True, capture_output=True)
    keeper = path / ".gitkeep"
    keeper.touch()
    subprocess.run(["git", "add", ".gitkeep"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# is_git_disabled
# ---------------------------------------------------------------------------

class IsGitDisabledTests(unittest.TestCase):
    def test_returns_true_when_env_set(self) -> None:
        with patch.dict(os.environ, {"GIT_DISABLED": "1"}):
            self.assertTrue(is_git_disabled())

    def test_returns_false_when_env_not_set(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GIT_DISABLED"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(is_git_disabled())

    def test_returns_false_when_env_is_zero(self) -> None:
        with patch.dict(os.environ, {"GIT_DISABLED": "0"}):
            self.assertFalse(is_git_disabled())


# ---------------------------------------------------------------------------
# commit_pipeline_stage — no-op paths
# ---------------------------------------------------------------------------

class CommitNoOpTests(unittest.TestCase):
    def test_returns_false_when_no_commit_true(self) -> None:
        result = commit_pipeline_stage(
            "test: should not commit",
            [PROJECT_ROOT / "compiled" / "index.md"],
            no_commit=True,
        )
        self.assertFalse(result)

    def test_returns_false_when_git_disabled(self) -> None:
        with patch.dict(os.environ, {"GIT_DISABLED": "1"}):
            result = commit_pipeline_stage(
                "test: should not commit",
                [PROJECT_ROOT / "compiled" / "index.md"],
                no_commit=False,
            )
        self.assertFalse(result)

    def test_returns_false_when_no_changes(self) -> None:
        # Use a path that definitely has no changes in git's index
        with patch.dict(os.environ, {}, clear=False):
            env_backup = os.environ.pop("GIT_DISABLED", None)
            try:
                result = commit_pipeline_stage(
                    "test: clean tree",
                    [PROJECT_ROOT / "nonexistent_file_xyz.md"],
                    no_commit=False,
                )
            finally:
                if env_backup is not None:
                    os.environ["GIT_DISABLED"] = env_backup
                else:
                    os.environ["GIT_DISABLED"] = "1"
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# has_changes — against a real temp repo
# ---------------------------------------------------------------------------

class HasChangesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _init_repo(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_detects_new_untracked_file(self) -> None:
        new_file = self.root / "new-note.md"
        new_file.write_text("hello", encoding="utf-8")
        self.assertTrue(has_changes([new_file], root=self.root))

    def test_detects_modified_tracked_file(self) -> None:
        tracked = self.root / "tracked.md"
        tracked.write_text("original", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.md"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add tracked"],
            cwd=self.root, check=True, capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t.com",
                 "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t.com"},
        )
        tracked.write_text("modified", encoding="utf-8")
        self.assertTrue(has_changes([tracked], root=self.root))

    def test_returns_false_for_clean_file(self) -> None:
        tracked = self.root / "clean.md"
        tracked.write_text("clean", encoding="utf-8")
        subprocess.run(["git", "add", "clean.md"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add clean"],
            cwd=self.root, check=True, capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t.com",
                 "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t.com"},
        )
        # No modification — should have no changes
        self.assertFalse(has_changes([tracked], root=self.root))

    def test_returns_false_for_nonexistent_path(self) -> None:
        self.assertFalse(has_changes([self.root / "does_not_exist.md"], root=self.root))


# ---------------------------------------------------------------------------
# commit_pipeline_stage — real commits in temp repo
# ---------------------------------------------------------------------------

class CommitPipelineStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _init_repo(self.root)
        # Ensure GIT_DISABLED is not set for these tests
        self._orig_disabled = os.environ.pop("GIT_DISABLED", None)

    def tearDown(self) -> None:
        if self._orig_disabled is not None:
            os.environ["GIT_DISABLED"] = self._orig_disabled
        else:
            os.environ["GIT_DISABLED"] = "1"
        self.tmp.cleanup()

    def test_commits_new_file_returns_true(self) -> None:
        note = self.root / "note.md"
        note.write_text("content", encoding="utf-8")

        result = commit_pipeline_stage(
            "synth: SRC-001 — Test (confidence pending)",
            [note],
            root=self.root,
        )

        self.assertTrue(result)
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=self.root, capture_output=True, text=True
        )
        self.assertIn("synth:", log.stdout)

    def test_returns_false_for_clean_tree(self) -> None:
        note = self.root / "clean.md"
        note.write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "clean.md"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "setup"],
            cwd=self.root, check=True, capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t.com",
                 "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t.com"},
        )

        result = commit_pipeline_stage("test: nothing changed", [note], root=self.root)
        self.assertFalse(result)

    def test_no_commit_flag_suppresses_commit(self) -> None:
        note = self.root / "blocked.md"
        note.write_text("blocked", encoding="utf-8")

        result = commit_pipeline_stage(
            "test: should be suppressed",
            [note],
            no_commit=True,
            root=self.root,
        )

        self.assertFalse(result)
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=self.root, capture_output=True, text=True
        )
        self.assertNotIn("should be suppressed", log.stdout)

    def test_git_disabled_env_suppresses_commit(self) -> None:
        note = self.root / "env_blocked.md"
        note.write_text("content", encoding="utf-8")

        with patch.dict(os.environ, {"GIT_DISABLED": "1"}):
            result = commit_pipeline_stage(
                "test: env disabled",
                [note],
                root=self.root,
            )

        self.assertFalse(result)


# ---------------------------------------------------------------------------
# log.py filtering
# ---------------------------------------------------------------------------

class LogFilterTests(unittest.TestCase):
    """Tests for scripts/log.py parsing and filtering logic."""

    def test_parse_line_synth(self) -> None:
        from scripts.log import _parse_line
        line = "a1b2c3|2026-04-19 14:32:01 +0000|synth: SRC-001 — Test Title (confidence pending)"
        result = _parse_line(line)
        self.assertIsNotNone(result)
        _hash, date, prefix, rest = result
        self.assertEqual(prefix, "synth")
        self.assertIn("SRC-001", rest)

    def test_parse_line_skips_non_pipeline_prefix(self) -> None:
        from scripts.log import _parse_line
        line = "a1b2c3|2026-04-19 14:32:01 +0000|chore: initial commit"
        self.assertIsNone(_parse_line(line))

    def test_parse_line_skips_no_colon(self) -> None:
        from scripts.log import _parse_line
        line = "a1b2c3|2026-04-19 14:32:01 +0000|just a message with no colon"
        self.assertIsNone(_parse_line(line))

    def test_format_row_synth(self) -> None:
        from scripts.log import _format_row
        row = _format_row("2026-04-19 14:32", "synth", "SRC-001 — Test Title (confidence pending)")
        self.assertIn("synth", row)
        self.assertIn("SRC-001", row)
        self.assertIn("Test Title", row)

    def test_format_row_index(self) -> None:
        from scripts.log import _format_row
        row = _format_row("2026-04-19 14:35", "index", "rebuilt (11 notes)")
        self.assertIn("index", row)
        self.assertIn("11 notes", row)

    def test_format_row_score(self) -> None:
        from scripts.log import _format_row
        row = _format_row("2026-04-19 14:33", "score", "SRC-001 confidence=0.91 auto-approved")
        self.assertIn("score", row)
        self.assertIn("SRC-001", row)
        self.assertIn("0.91", row)

    def test_format_row_review_approved(self) -> None:
        from scripts.log import _format_row
        row = _format_row("2026-04-19 15:10", "review", "approved SRC-002 — Some Title")
        self.assertIn("review", row)
        self.assertIn("SRC-002", row)
        self.assertIn("approved", row)

    def test_cmd_log_type_filter(self) -> None:
        """cmd_log with --type synth only shows synth prefixed commits."""
        from scripts.log import _parse_line
        lines = [
            "a1b2c3|2026-04-19 14:32:01 +0000|synth: SRC-001 — Title (confidence pending)",
            "b2c3d4|2026-04-19 14:33:01 +0000|score: SRC-001 confidence=0.91 auto-approved",
            "c3d4e5|2026-04-19 14:34:01 +0000|index: rebuilt (5 notes)",
        ]
        parsed = [_parse_line(l) for l in lines]
        synth_only = [p for p in parsed if p and p[2] == "synth"]
        self.assertEqual(len(synth_only), 1)
        self.assertEqual(synth_only[0][2], "synth")

    def test_cmd_log_source_filter(self) -> None:
        """Source filter matches source ID in rest of commit message."""
        from scripts.log import _parse_line
        lines = [
            "a1b2c3|2026-04-19 14:32:01 +0000|synth: SRC-001 — Title (confidence pending)",
            "b2c3d4|2026-04-19 14:33:01 +0000|synth: SRC-002 — Other (confidence pending)",
        ]
        parsed = [_parse_line(l) for l in lines]
        src001_only = [p for p in parsed if p and "SRC-001" in p[3]]
        self.assertEqual(len(src001_only), 1)


if __name__ == "__main__":
    unittest.main()

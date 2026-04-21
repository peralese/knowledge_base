"""
git_ops.py — shared git commit helper for pipeline scripts.

All pipeline scripts call commit_pipeline_stage() after successful writes.
Auto-commit is a no-op if:
  - GIT_DISABLED=1 environment variable is set
  - no_commit=True was passed to commit_pipeline_stage()
  - No files have changed (clean working tree for the relevant paths)
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Union

PROJECT_ROOT = Path(__file__).parent.parent
GIT_AUTHOR_NAME = "KB Pipeline"
GIT_AUTHOR_EMAIL = "kb-pipeline@localhost"


def _git(*args, cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def is_git_disabled() -> bool:
    return os.environ.get("GIT_DISABLED", "").strip() == "1"


def has_changes(paths: list[Union[str, Path]], root: Path = PROJECT_ROOT) -> bool:
    """Return True if any of the given paths have unstaged or staged changes."""
    result = _git("status", "--porcelain", "--", *[str(p) for p in paths], cwd=root)
    return bool(result.stdout.strip())


def commit_pipeline_stage(
    message: str,
    paths: list[Union[str, Path]],
    no_commit: bool = False,
    root: Path = PROJECT_ROOT,
) -> bool:
    """Stage and commit the given paths with the given message.

    Returns True if a commit was made, False if skipped.
    Raises RuntimeError if git operations fail.
    """
    if no_commit or is_git_disabled():
        return False

    if not has_changes(paths, root=root):
        return False

    str_paths = [str(p) for p in paths]

    add_result = _git("add", "--", *str_paths, cwd=root)
    if add_result.returncode != 0:
        raise RuntimeError(f"git add failed: {add_result.stderr}")

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = GIT_AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = GIT_AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = GIT_AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = GIT_AUTHOR_EMAIL

    commit_result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    if commit_result.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit_result.stderr}")

    return True

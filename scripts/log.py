"""Phase 10 Operation Log: human-friendly view of the pipeline's git history.

Parses git log commit messages written by the pipeline scripts and formats them
as a clean table. This replaces a separate log.md file — git already has all
the information.

Usage:
    # Show last 20 pipeline commits
    python3 scripts/log.py

    # Show commits since a date
    python3 scripts/log.py --since "2026-04-14"

    # Show commits for a specific source ID
    python3 scripts/log.py --source SRC-20260419-0001

    # Show commits for a specific topic
    python3 scripts/log.py --topic openclaw-security

    # Show only approvals
    python3 scripts/log.py --type review

    # Show only synthesis commits
    python3 scripts/log.py --type synth
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PREFIXES = {"synth", "score", "review", "topic", "index"}


# ---------------------------------------------------------------------------
# Git log reader
# ---------------------------------------------------------------------------

def _git_log(since: str | None = None, root: Path = ROOT) -> list[str]:
    """Return raw git log lines as 'hash|datetime|subject'."""
    args = ["git", "log", "--pretty=format:%h|%ci|%s"]
    if since:
        args.extend(["--since", since])
    result = subprocess.run(args, cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.strip().splitlines() if line]


def _parse_line(line: str) -> tuple[str, str, str, str] | None:
    """Parse a git log line into (hash, date_str, prefix, rest) or None."""
    parts = line.split("|", 2)
    if len(parts) < 3:
        return None
    hash_, datetime_str, subject = parts

    # "2026-04-19 14:32:01 +0000" → "2026-04-19 14:32"
    date = datetime_str[:16].replace("T", " ")

    colon_idx = subject.find(":")
    if colon_idx == -1:
        return None
    prefix = subject[:colon_idx].strip()
    if prefix not in PIPELINE_PREFIXES:
        return None

    rest = subject[colon_idx + 1:].strip()
    return hash_, date, prefix, rest


# ---------------------------------------------------------------------------
# Row formatter
# ---------------------------------------------------------------------------

def _format_row(date: str, type_: str, rest: str) -> str:
    """Format one log row for human display."""
    if type_ == "synth":
        m = re.match(r"(SRC-[\d-]+)\s+[—-]+\s+(.*?)\s*\(confidence pending\)", rest)
        if m:
            sid, title = m.group(1), m.group(2)[:40]
            return f"{date}  {type_:<8} {sid:<22} {title}"

    elif type_ == "score":
        m = re.match(r"(SRC-[\d-]+)\s+(.*)", rest)
        if m:
            sid, detail = m.group(1), m.group(2)
            return f"{date}  {type_:<8} {sid:<22} {detail}"

    elif type_ == "review":
        m = re.match(r"(approved|rejected)\s+(SRC-[\d-]+)(.*)", rest)
        if m:
            action, sid = m.group(1), m.group(2)
            return f"{date}  {type_:<8} {sid:<22} {action}"

    elif type_ == "topic":
        m = re.match(r"updated\s+([\w-]+)\s+\(\+(SRC-[\d-]+)\)", rest)
        if m:
            slug, sid = m.group(1), m.group(2)
            return f"{date}  {type_:<8} {slug:<22} +{sid}"

    elif type_ == "index":
        return f"{date}  {type_:<8} {'':22} {rest}"

    return f"{date}  {type_:<8} {rest}"


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

def cmd_log(
    since: str | None = None,
    source: str | None = None,
    topic: str | None = None,
    type_: str | None = None,
    n: int = 20,
    root: Path = ROOT,
) -> None:
    lines = _git_log(since=since, root=root)

    rows: list[tuple[str, str, str]] = []
    for line in lines:
        parsed = _parse_line(line)
        if parsed is None:
            continue
        _hash, date, prefix, rest = parsed

        if type_ and prefix != type_:
            continue
        if source and source not in rest:
            continue
        if topic and topic not in rest:
            continue

        rows.append((date, prefix, rest))
        if len(rows) >= n:
            break

    if not rows:
        print("No matching pipeline commits found.")
        return

    for date, prefix, rest in rows:
        print(_format_row(date, prefix, rest))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 10 Log: human-friendly view of the pipeline's git history.\n"
            "Reads commit messages written by synth/score/review/topic/index steps."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--since",
        help="Show commits since date (e.g. '2026-04-14').",
    )
    parser.add_argument(
        "--source",
        help="Show commits for a specific source ID (e.g. SRC-20260419-0001).",
    )
    parser.add_argument(
        "--topic",
        help="Show commits for a specific topic slug (e.g. openclaw-security).",
    )
    parser.add_argument(
        "--type",
        dest="type_",
        choices=list(PIPELINE_PREFIXES),
        help="Show only commits of a specific pipeline step.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=20,
        help="Maximum number of commits to show. Default: 20.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd_log(
        since=args.since,
        source=args.source,
        topic=args.topic,
        type_=args.type_,
        n=args.n,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

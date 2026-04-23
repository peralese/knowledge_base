"""Phase 2B-1 — Query Feedback Loop.

Mark saved query answers as good or bad from the CLI. Feedback is stored as
frontmatter fields co-located with each answer file.

Usage:
    python3 scripts/feedback.py list                              # list answers with status
    python3 scripts/feedback.py good <answer-id>                  # mark as good
    python3 scripts/feedback.py bad <answer-id> [--note "reason"] # mark as bad
    python3 scripts/feedback.py show <answer-id>                  # show answer + feedback
    python3 scripts/feedback.py stats                             # aggregate stats
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSWERS_DIR = ROOT / "outputs" / "answers"


# ---------------------------------------------------------------------------
# Frontmatter read / write
# ---------------------------------------------------------------------------

def split_answer_file(path: Path) -> tuple[str, str]:
    """Return (frontmatter_text, body_text) for an answer file.

    frontmatter_text is the raw text between the opening and closing '---'
    delimiters (not including the delimiters themselves).
    body_text is everything after the closing delimiter.
    """
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return "", normalized
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return "", normalized
    fm = normalized[4:end]
    body = normalized[end + 5:]  # skip the \n---\n sequence
    return fm, body


def join_answer_file(fm_text: str, body: str) -> str:
    """Reconstruct an answer file from frontmatter text and body."""
    return f"---\n{fm_text}\n---\n{body}"


def patch_fm_field(fm_text: str, key: str, value: str | None) -> str:
    """Replace or append a scalar field in frontmatter text (idempotent).

    If the field already exists, its line is replaced. If not, it is appended.
    Passing value=None writes '<key>: null'.
    """
    if value is None:
        replacement = f"{key}: null"
    else:
        safe_val = value.replace('"', "'")
        replacement = f'{key}: "{safe_val}"'

    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    if pattern.search(fm_text):
        return pattern.sub(replacement, fm_text)
    return fm_text.rstrip("\n") + f"\n{replacement}"


def read_fm_field(fm_text: str, key: str) -> str:
    """Read a scalar field value from frontmatter text. Returns '' if absent or null."""
    for line in fm_text.splitlines():
        m = re.match(rf"^{re.escape(key)}:\s*(.+)$", line)
        if m:
            val = m.group(1).strip().strip('"').strip("'")
            return "" if val == "null" else val
    return ""


def answer_question(fm_text: str, fallback: str) -> str:
    return read_fm_field(fm_text, "question") or read_fm_field(fm_text, "generated_from_query") or fallback


def answer_date(fm_text: str) -> str:
    return read_fm_field(fm_text, "date") or read_fm_field(fm_text, "generated_on")


# ---------------------------------------------------------------------------
# Answer discovery
# ---------------------------------------------------------------------------

def resolve_answer_path(answer_id: str) -> Path:
    """Resolve an answer_id (stem or filename with .md) to a Path."""
    stem = answer_id.removesuffix(".md")
    path = ANSWERS_DIR / f"{stem}.md"
    if not path.exists():
        raise FileNotFoundError(f"Answer not found: {stem}")
    return path


def list_answers() -> list[Path]:
    """Return all answer .md files, newest first."""
    if not ANSWERS_DIR.exists():
        return []
    return sorted(ANSWERS_DIR.glob("*.md"), reverse=True)


# ---------------------------------------------------------------------------
# Write feedback to an answer file
# ---------------------------------------------------------------------------

def write_feedback(path: Path, rating: str, note: str = "") -> None:
    """Write feedback to an answer file's frontmatter (idempotent overwrite)."""
    if rating not in ("good", "bad"):
        raise ValueError(f"rating must be 'good' or 'bad', got: {rating!r}")

    fm, body = split_answer_file(path)
    fm = patch_fm_field(fm, "feedback", rating)
    fm = patch_fm_field(fm, "feedback_at", _now_iso())

    if rating == "good":
        # Clear any prior note
        fm = patch_fm_field(fm, "feedback_note", None)
    elif note:
        fm = patch_fm_field(fm, "feedback_note", note)
    else:
        fm = patch_fm_field(fm, "feedback_note", None)

    path.write_text(join_answer_file(fm, body), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_list(_args: argparse.Namespace) -> int:
    paths = list_answers()
    if not paths:
        print("No saved answers found.")
        return 0

    print(f"{'Answer ID':<42} {'Date':<12} {'Rating':<8} Question")
    print("-" * 130)
    for path in paths:
        fm, _ = split_answer_file(path)
        date = answer_date(fm)
        rating = read_fm_field(fm, "feedback") or "—"
        question = answer_question(fm, path.stem)
        question_display = question[:57] + "…" if len(question) > 60 else question
        stem = path.stem
        id_display = stem[:39] + "…" if len(stem) > 42 else stem
        print(f"{id_display:<42} {date:<12} {rating:<8} {question_display}")
    return 0


def cmd_good(args: argparse.Namespace) -> int:
    try:
        path = resolve_answer_path(args.answer_id)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    write_feedback(path, "good")
    print(f"Marked good: {path.name}")
    return 0


def cmd_bad(args: argparse.Namespace) -> int:
    try:
        path = resolve_answer_path(args.answer_id)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    write_feedback(path, "bad", note=args.note or "")
    print(f"Marked bad: {path.name}" + (f"  (note: {args.note})" if args.note else ""))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    try:
        path = resolve_answer_path(args.answer_id)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    fm, body = split_answer_file(path)
    question = answer_question(fm, path.stem)
    date = answer_date(fm)
    rating = read_fm_field(fm, "feedback") or "(unrated)"
    feedback_at = read_fm_field(fm, "feedback_at")
    feedback_note = read_fm_field(fm, "feedback_note")

    print(f"Answer  : {path.name}")
    print(f"Question: {question}")
    print(f"Date    : {date}")
    at_str = f"  (at {feedback_at})" if feedback_at else ""
    print(f"Feedback: {rating}{at_str}")
    if feedback_note:
        print(f"Note    : {feedback_note}")
    print()
    print(body.strip())
    return 0


def cmd_stats(_args: argparse.Namespace) -> int:
    from datetime import date as date_cls  # noqa: PLC0415

    paths = list_answers()
    total = len(paths)
    if total == 0:
        print("No saved answers found.")
        return 0

    good_list: list[tuple[str, str, str]] = []  # (stem, question, note)
    bad_list: list[tuple[str, str, str]] = []
    unrated: list[tuple[str, str, str]] = []

    for path in paths:
        fm, _ = split_answer_file(path)
        rating = read_fm_field(fm, "feedback")
        question = answer_question(fm, path.stem)
        note = read_fm_field(fm, "feedback_note")
        entry = (path.stem, question, note)
        if rating == "good":
            good_list.append(entry)
        elif rating == "bad":
            bad_list.append(entry)
        else:
            unrated.append(entry)

    rated = len(good_list) + len(bad_list)
    today = date_cls.today().isoformat()

    print(f"Feedback Summary — {today}")
    print("=" * 30)
    print(f"Total answers    : {total}")
    rated_pct = f"{rated / total * 100:.1f}%" if total else "0.0%"
    print(f"Rated            : {rated} ({rated_pct})")
    if rated:
        good_pct = f"{len(good_list) / rated * 100:.1f}%"
        bad_pct = f"{len(bad_list) / rated * 100:.1f}%"
        print(f"  Good           : {len(good_list)}  ({good_pct} of rated)")
        print(f"  Bad            : {len(bad_list)}  ({bad_pct} of rated)")
    else:
        print(f"  Good           : 0")
        print(f"  Bad            : 0")
    print(f"Unrated          : {len(unrated)}")

    if bad_list:
        print()
        print("Recent bad answers (up to 5):")
        for stem, question, note in bad_list[:5]:
            q_short = question[:60] + "…" if len(question) > 60 else question
            note_str = f'— "{note}"' if note else "— no note"
            print(f'  {stem}  "{q_short}"  {note_str}')

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 2B-1: Mark query answers as good or bad."
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List recent answers with feedback status.")
    sub.add_parser("stats", help="Show feedback statistics summary.")

    good_p = sub.add_parser("good", help="Mark an answer as good.")
    good_p.add_argument("answer_id", help="Answer filename stem or filename.md")

    bad_p = sub.add_parser("bad", help="Mark an answer as bad.")
    bad_p.add_argument("answer_id", help="Answer filename stem or filename.md")
    bad_p.add_argument("--note", default="", help="Optional reason for bad rating.")

    show_p = sub.add_parser("show", help="Show full answer with feedback status.")
    show_p.add_argument("answer_id", help="Answer filename stem or filename.md")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "list": cmd_list,
        "good": cmd_good,
        "bad": cmd_bad,
        "show": cmd_show,
        "stats": cmd_stats,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

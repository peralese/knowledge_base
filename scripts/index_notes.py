"""Phase 8 Index Maintenance: generate a global index of all compiled notes.

Reads every compiled note and produces compiled/index.md — a single markdown
file with one-line summaries grouped by category (topics, concepts,
source_summaries). The index serves two purposes:

  1. Human browsability: quickly see what's in the wiki.
  2. LLM context primer: query.py prepends the index as a "Wiki Map" so the
     model knows the full wiki structure even when --top-n limits which full
     notes are loaded.

Usage:
    # Regenerate compiled/index.md
    python3 scripts/index_notes.py

    # Preview to stdout without writing
    python3 scripts/index_notes.py --dry-run

    # Structured JSON output (for programmatic use)
    python3 scripts/index_notes.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

INDEX_PATH = ROOT / "compiled" / "index.md"

CATEGORY_ORDER = ["topics", "concepts", "source_summaries"]

CATEGORY_HEADINGS = {
    "topics":           "Topics",
    "concepts":         "Concepts",
    "source_summaries": "Source Summaries",
}

SUMMARY_MAX_LEN = 120


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NoteEntry:
    slug: str       # file stem, e.g. "aws-containers"
    title: str      # from frontmatter title: or derived from stem
    summary: str    # 120-char one-liner
    category: str   # "topics" | "concepts" | "source_summaries"


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse scalar frontmatter keys from a compiled note."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return {}
    result: dict[str, str] = {}
    for line in parts[0].splitlines():
        m = re.match(r'^(\w[\w_-]*):\s*"?([^"]*)"?\s*$', line.strip())
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def _strip_frontmatter(text: str) -> str:
    """Return body text with YAML frontmatter removed."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return normalized.strip()
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return normalized.strip()
    return parts[1].strip()


# ---------------------------------------------------------------------------
# Summary extraction
# ---------------------------------------------------------------------------

_LIST_PREFIX = re.compile(r"^[-*+] |^\d+\.\s")
_BOLD_ITALIC = re.compile(r"\*{1,3}|_{1,3}")


_YAML_KV = re.compile(r"^\w[\w_-]*:\s")  # matches "key: value" frontmatter lines


def extract_summary(text: str) -> str:
    """Extract a one-line summary from a compiled note's text.

    Priority:
      1. Frontmatter ``summary:`` field
      2. First non-blank, non-heading, non-list-item, non-frontmatter line in the body
      3. Empty string if nothing usable is found

    The result is truncated to SUMMARY_MAX_LEN characters at a word boundary.
    """
    fm = _parse_frontmatter(text)
    if fm.get("summary"):
        return _truncate(fm["summary"])

    body = _strip_frontmatter(text)
    in_embedded_fm = False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip frontmatter delimiter lines (--- blocks) and their contents.
        # Some LLM outputs embed a second frontmatter block in the body.
        if stripped == "---":
            in_embedded_fm = not in_embedded_fm
            continue
        if in_embedded_fm:
            continue
        if stripped.startswith("#"):
            continue
        if _LIST_PREFIX.match(stripped):
            continue
        # Skip bare YAML key: value lines that leaked outside frontmatter
        if _YAML_KV.match(stripped):
            continue
        # Strip bold/italic markers
        clean = _BOLD_ITALIC.sub("", stripped).strip()
        if clean:
            return _truncate(clean)

    return ""


def _truncate(text: str) -> str:
    """Truncate to SUMMARY_MAX_LEN chars at a word boundary, appending …."""
    if len(text) <= SUMMARY_MAX_LEN:
        return text
    cut = text[:SUMMARY_MAX_LEN]
    last_space = cut.rfind(" ")
    shortened = cut[:last_space] if last_space > SUMMARY_MAX_LEN // 2 else cut
    return shortened.rstrip(".,;:") + "…"


# ---------------------------------------------------------------------------
# Note loading
# ---------------------------------------------------------------------------

def _load_note_entries(root: Path) -> dict[str, list[NoteEntry]]:
    """Load all compiled notes and return them grouped by category."""
    groups: dict[str, list[NoteEntry]] = {cat: [] for cat in CATEGORY_ORDER}

    for cat in CATEGORY_ORDER:
        directory = root / "compiled" / cat
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.stem == "index":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            fm = _parse_frontmatter(text)
            title = fm.get("title") or path.stem.replace("-", " ").title()
            summary = extract_summary(text)
            groups[cat].append(NoteEntry(
                slug=path.stem,
                title=title,
                summary=summary,
                category=cat,
            ))

    return groups


# ---------------------------------------------------------------------------
# Index rendering
# ---------------------------------------------------------------------------

def build_index_text(groups: dict[str, list[NoteEntry]], today: str) -> str:
    """Render the full compiled/index.md content."""
    total = sum(len(v) for v in groups.values())

    frontmatter = (
        "---\n"
        'title: "Wiki Index"\n'
        'note_type: "index"\n'
        f'generated_on: "{today}"\n'
        f"note_count: {total}\n"
        "---"
    )

    header = (
        f"{frontmatter}\n\n"
        "# Wiki Index\n\n"
        f"_Generated on {today} — {total} note{'s' if total != 1 else ''}_\n"
    )

    sections: list[str] = []
    for cat in CATEGORY_ORDER:
        entries = groups.get(cat, [])
        if not entries:
            continue
        heading = CATEGORY_HEADINGS[cat]
        lines = [f"## {heading}\n"]
        for entry in entries:
            sep = " — " if entry.summary else ""
            lines.append(f"- [[{entry.slug}]]{sep}{entry.summary}")
        sections.append("\n".join(lines))

    return header + "\n" + "\n\n".join(sections) + ("\n" if sections else "")


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run(root: Path, dry_run: bool = False, as_json: bool = False) -> int:
    compiled_dir = root / "compiled"
    if not compiled_dir.exists():
        print("Error: compiled/ directory not found. Run compile_notes.py first.", file=sys.stderr)
        return 1

    groups = _load_note_entries(root)
    today = date.today().isoformat()

    if as_json:
        output = {cat: [asdict(e) for e in entries] for cat, entries in groups.items()}
        print(json.dumps(output, indent=2))
        return 0

    text = build_index_text(groups, today)

    if dry_run:
        print(text)
        return 0

    dest = root / "compiled" / "index.md"
    dest.write_text(text, encoding="utf-8")
    total = sum(len(v) for v in groups.values())
    print(f"Index written : compiled/index.md ({total} notes)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 8 Index Maintenance: generate compiled/index.md."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the index to stdout without writing the file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output structured JSON to stdout instead of writing the index file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(ROOT, dry_run=args.dry_run, as_json=args.as_json)


if __name__ == "__main__":
    sys.exit(main())

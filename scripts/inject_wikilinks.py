"""inject_wikilinks.py — 2A-3 Wikilink Injection

Back-annotates topic notes and approved raw source notes with [[concept]] and
[[entity]] links wherever a known concept/entity name appears. Converts flat
text into a traversable graph.

Injection rules:
  - Only inject for concepts/entities that exist as actual notes
  - Match canonical note name (filename stem, hyphens/underscores → spaces)
  - Also match the hyphenated slug form (e.g. "zero-trust" in text)
  - First occurrence per note only — never link every mention
  - Never inject inside existing [[...]] links, frontmatter, code blocks,
    inline code spans, or headings
  - Annotate topic notes and approved raw articles; NOT concept/entity notes

Usage:
    python3 scripts/inject_wikilinks.py                      # annotate all
    python3 scripts/inject_wikilinks.py --dry-run            # preview only
    python3 scripts/inject_wikilinks.py --note path/to/note  # single note
    python3 scripts/inject_wikilinks.py --no-commit          # skip git commit
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).parent))
from git_ops import commit_pipeline_stage  # noqa: E402


# ---------------------------------------------------------------------------
# Known targets: build name → slug mapping from concept/entity directories
# ---------------------------------------------------------------------------

def _slug_to_display(slug: str) -> str:
    """Convert a file stem to a display name for matching (hyphens/underscores → spaces)."""
    return slug.replace("-", " ").replace("_", " ").lower()


def load_known_targets(root: Path) -> dict[str, str]:
    """Return {match_name_lower: canonical_slug} for all concept and entity notes.

    Each concept/entity contributes two match keys:
      - display name (hyphens → spaces): "zero trust" → "zero-trust"
      - slug form (as-is): "zero-trust" → "zero-trust"
    Longer names are preferred (handled by sort order in injection).
    """
    targets: dict[str, str] = {}
    for directory in [root / "compiled" / "concepts", root / "compiled" / "entities"]:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            slug = path.stem
            display = _slug_to_display(slug)
            targets[display] = slug
            # Also register the raw slug form if different
            if slug.lower() != display:
                targets[slug.lower()] = slug
    return targets


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_with_delimiters, body). frontmatter='' if none found."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return "", normalized
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return "", normalized
    return normalized[: end + 5], normalized[end + 5:]


def _is_approved(text: str) -> bool:
    fm, _ = _split_frontmatter(text)
    return "approved: true" in fm or "approved:true" in fm


# ---------------------------------------------------------------------------
# Body annotation: zone marking and injection
# ---------------------------------------------------------------------------

def _mark_no_inject_zones(body: str) -> list[tuple[int, int]]:
    """Return list of (start, end) char ranges where injection is forbidden.

    Forbidden zones:
      - Existing [[...]] links (to avoid double-wrapping)
      - Code blocks (``` ... ```)
      - Inline code spans (`...`)
      - Headings (lines starting with #)
    """
    zones: list[tuple[int, int]] = []

    # Existing wikilinks [[...]]
    for m in re.finditer(r"\[\[.*?\]\]", body, re.DOTALL):
        zones.append((m.start(), m.end()))

    # Fenced code blocks
    for m in re.finditer(r"```.*?```", body, re.DOTALL):
        zones.append((m.start(), m.end()))

    # Inline code spans
    for m in re.finditer(r"`[^`]+`", body):
        zones.append((m.start(), m.end()))

    # Headings: full line starting with #
    for m in re.finditer(r"^#+[^\n]*", body, re.MULTILINE):
        zones.append((m.start(), m.end()))

    return zones


def _in_zone(pos: int, end: int, zones: list[tuple[int, int]]) -> bool:
    """Return True if [pos, end) overlaps any forbidden zone."""
    for zs, ze in zones:
        if pos < ze and end > zs:
            return True
    return False


def _build_match_pattern(names: list[str]) -> re.Pattern:
    """Build a combined regex that matches any of the given names as whole words.

    Names are sorted longest-first so longer matches win over shorter prefixes.
    """
    sorted_names = sorted(names, key=len, reverse=True)
    alts = [re.escape(n) for n in sorted_names]
    return re.compile(r"(?<!\w)(" + "|".join(alts) + r")(?!\w)", re.IGNORECASE)


def inject_wikilinks_into_body(
    body: str,
    targets: dict[str, str],  # {match_name_lower: canonical_slug}
) -> tuple[str, list[tuple[str, int, str]]]:
    """Inject [[slug]] links into body text for first occurrence of each target.

    Returns (modified_body, injections) where each injection is
    (matched_text, line_number, wiki_slug).
    Respects no-inject zones and injects only the first occurrence per concept.
    """
    if not targets:
        return body, []

    zones = _mark_no_inject_zones(body)
    pattern = _build_match_pattern(list(targets.keys()))

    injected_slugs: set[str] = set()
    # Collect (start, end, slug, matched_text, line_num) forward pass
    pending: list[tuple[int, int, str, str, int]] = []

    for m in pattern.finditer(body):
        matched_lower = m.group(1).lower()
        slug = targets.get(matched_lower)
        if slug is None:
            continue
        if slug in injected_slugs:
            continue
        if _in_zone(m.start(), m.end(), zones):
            continue

        line_num = body[: m.start()].count("\n") + 1
        injected_slugs.add(slug)
        pending.append((m.start(), m.end(), slug, m.group(1), line_num))
        # Mark the matched span as a zone so later matches don't overlap
        zones.append((m.start(), m.end()))

    if not pending:
        return body, []

    # Apply replacements right-to-left so positions stay valid
    result = body
    injections: list[tuple[str, int, str]] = []
    for start, end, slug, matched_text, line_num in reversed(pending):
        result = result[:start] + "[[" + slug + "]]" + result[end:]
        injections.append((matched_text, line_num, slug))

    injections.reverse()  # restore forward order for reporting
    return result, injections


# ---------------------------------------------------------------------------
# Note-level processing
# ---------------------------------------------------------------------------

def _should_annotate(path: Path, root: Path) -> bool:
    """Return True if this note is eligible for wikilink injection."""
    rel = path.relative_to(root)
    parts = rel.parts
    # Annotate: compiled/topics/
    if parts[:2] == ("compiled", "topics"):
        return True
    # Annotate: raw/articles/ and raw/notes/ if approved
    if parts[0] == "raw" and parts[1] in ("articles", "notes"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return _is_approved(text)
        except OSError:
            return False
    return False


def annotate_note(
    path: Path,
    targets: dict[str, str],
    dry_run: bool,
    root: Path,
) -> list[tuple[str, int, str]]:
    """Inject wikilinks into a single note. Returns list of injections made."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _split_frontmatter(text)

    new_body, injections = inject_wikilinks_into_body(body, targets)

    if not injections:
        return []

    if not dry_run:
        path.write_text(fm + new_body, encoding="utf-8")

    return injections


def _collect_eligible_notes(root: Path) -> list[Path]:
    eligible: list[Path] = []
    for directory in [
        root / "compiled" / "topics",
        root / "raw" / "articles",
        root / "raw" / "notes",
    ]:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            eligible.append(path)
    return eligible


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run(
    root: Path,
    dry_run: bool,
    note_path: Path | None,
    no_commit: bool,
) -> int:
    targets = load_known_targets(root)
    if not targets:
        print("No concept or entity notes found — run concept_aggregator.py first.")
        return 0

    print(f"Known targets: {len(targets)} concept/entity names")

    if note_path is not None:
        notes = [note_path]
    else:
        notes = [p for p in _collect_eligible_notes(root) if _should_annotate(p, root)]

    print(f"Notes to annotate: {len(notes)}")

    total_injections = 0
    modified_notes: list[Path] = []
    concepts_linked: set[str] = set()

    for path in notes:
        injections = annotate_note(path, targets, dry_run=dry_run, root=root)
        if injections:
            rel = path.relative_to(root)
            print(f"\n{rel}")
            for matched_text, line_num, slug in injections:
                print(f'  → "{matched_text}" found at line {line_num} → [[{slug}]]')
            if not dry_run:
                modified_notes.append(path)
            total_injections += len(injections)
            concepts_linked.update(slug for _, _, slug in injections)

    if not dry_run:
        injection_noun = "injection" if total_injections == 1 else "injections"
        note_noun = "note" if len(modified_notes) == 1 else "notes"
        print(
            f"\nTotal: {total_injections} {injection_noun} across "
            f"{len(modified_notes)} {note_noun}, "
            f"{len(concepts_linked)} unique concepts/entities linked"
        )

        if dry_run:
            pass
        else:
            suffix = " (dry run)" if dry_run else ""
            print(f"  {total_injections} injections proposed" if dry_run else "")

    if not dry_run and modified_notes:
        msg = "feat(wikilinks): inject wikilinks across topic and source notes [2A-3]"
        try:
            committed = commit_pipeline_stage(msg, modified_notes, no_commit=no_commit, root=root)
            if committed:
                print(f"Committed {len(modified_notes)} modified notes.")
        except RuntimeError as exc:
            print(f"Warning: git commit failed: {exc}", file=sys.stderr)

    if dry_run:
        injection_noun = "injection" if total_injections == 1 else "injections"
        print(f"\nDry run: {total_injections} {injection_noun} proposed across {len(notes)} notes.")

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2A-3 Wikilink Injection: back-annotate notes with [[concept]] links."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed injections; do not modify files.",
    )
    parser.add_argument(
        "--note",
        type=Path,
        metavar="PATH",
        help="Annotate a single note file.",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Skip git auto-commits.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        root=ROOT,
        dry_run=args.dry_run,
        note_path=args.note,
        no_commit=args.no_commit,
    )


if __name__ == "__main__":
    sys.exit(main())

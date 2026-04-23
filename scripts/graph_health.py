"""graph_health.py — 2A-1 Graph Health Baseline

Measures the health of the compiled knowledge graph with no LLM calls.

Metrics computed:
  - note counts by type (topics, concepts, entities, source_summaries)
  - wikilink density — avg [[...]] links per note, by type
  - stub ratio — % of concept notes with no meaningful body content
  - orphan count — notes not referenced by any wikilink in any other note
  - orphan list — top 20 most-orphaned concept/entity notes by name
  - source coverage — % of approved source summaries in at least one topic
  - average approved sources per topic note

Usage:
    python3 scripts/graph_health.py              # full report + JSON snapshot
    python3 scripts/graph_health.py --json-only  # JSON only, suppress stdout
    python3 scripts/graph_health.py --compare    # diff vs most recent snapshot
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]+)?\]\]")
# A stub has zero meaningful body lines (only headings and placeholders).
# Threshold of 1 means any single line of real definition text is sufficient.
# The previous value of 3 incorrectly flagged notes whose definition is a
# single paragraph (which write_definition renders as one unwrapped line).
STUB_THRESHOLD = 1  # fewer than this many meaningful body lines → stub


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _strip_frontmatter(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return normalized.strip()
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return normalized.strip()
    return parts[1].strip()


def _parse_frontmatter_field(text: str, field: str) -> str:
    """Return the raw string value of a scalar frontmatter field, or ''."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return ""
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return ""
    for line in normalized[4:end].splitlines():
        m = re.match(rf"^{re.escape(field)}:\s*(.+)$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return ""


def _parse_yaml_bool(text: str, field: str) -> bool:
    val = _parse_frontmatter_field(text, field).lower()
    return val in {"true", "yes", "1"}


def _parse_compiled_from(text: str) -> list[str]:
    """Extract the compiled_from list from a note's frontmatter."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return []
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return []
    refs: list[str] = []
    in_list = False
    for line in normalized[4:end].splitlines():
        if re.match(r"^compiled_from:\s*$", line):
            in_list = True
            continue
        if in_list:
            m = re.match(r'^\s+-\s+"?([^"]+)"?\s*$', line)
            if m:
                refs.append(m.group(1).strip())
            elif line.strip() and not line.startswith(" "):
                break
    return refs


# ---------------------------------------------------------------------------
# Stub detection
# ---------------------------------------------------------------------------

def _meaningful_body_lines(body: str) -> list[str]:
    """Return lines from body that carry actual content (not headings/blanks/placeholders).

    Excluded:
      - empty / whitespace-only lines
      - headings (start with #)
      - italic placeholder lines (_..._)
      - horizontal rules (---)
      - wikilink list entries (- [[...]]) — these are "Mentioned In" cross-references,
        not definition content; concept_aggregator writes them before define_concepts
        writes the actual definition
    """
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("_") and stripped.endswith("_"):
            continue
        if stripped == "---":
            continue
        # Wikilink cross-reference list items are metadata, not definition prose
        if stripped.startswith("- [["):
            continue
        lines.append(stripped)
    return lines


def is_stub(text: str) -> bool:
    """Return True if a concept/entity note is a stub.

    A note is a stub if generation_method is 'stub' OR it has fewer than
    STUB_THRESHOLD meaningful body lines.
    """
    gen_method = _parse_frontmatter_field(text, "generation_method")
    if gen_method == "stub":
        return True
    body = _strip_frontmatter(text)
    return len(_meaningful_body_lines(body)) < STUB_THRESHOLD


# ---------------------------------------------------------------------------
# Wikilink helpers
# ---------------------------------------------------------------------------

def _extract_wikilinks(body: str) -> list[str]:
    """Return all [[target]] stems found in body text."""
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(body)]


def _count_wikilinks(text: str) -> int:
    body = _strip_frontmatter(text)
    return len(_extract_wikilinks(body))


# ---------------------------------------------------------------------------
# Note collection helpers
# ---------------------------------------------------------------------------

def _read_notes(directory: Path) -> dict[str, str]:
    """Read all .md files in directory; return {stem: content}."""
    if not directory.exists():
        return {}
    return {
        p.stem: p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(directory.glob("*.md"))
    }


def _all_wikilink_targets(all_notes: dict[str, dict[str, str]]) -> dict[str, set[str]]:
    """Return {stem: set_of_stems_that_link_to_it} across all note collections.

    all_notes is a dict of collection_name → {stem: content}.
    """
    # Build map: target_stem → set of notes that link to it
    incoming: dict[str, set[str]] = {}
    for _coll_name, notes in all_notes.items():
        for stem, text in notes.items():
            body = _strip_frontmatter(text)
            for target in _extract_wikilinks(body):
                # Normalize target to stem form (may include path separators)
                target_stem = target.strip()
                incoming.setdefault(target_stem, set()).add(stem)
    return incoming


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

def compute_metrics(root: Path) -> dict:
    topics = _read_notes(root / "compiled" / "topics")
    concepts = _read_notes(root / "compiled" / "concepts")
    entities = _read_notes(root / "compiled" / "entities")
    summaries = _read_notes(root / "compiled" / "source_summaries")

    # --- note counts ---
    counts = {
        "topics": len(topics),
        "concepts": len(concepts),
        "entities": len(entities),
        "source_summaries": len(summaries),
    }

    # --- wikilink density by type ---
    def _avg_links(notes: dict[str, str]) -> float:
        if not notes:
            return 0.0
        total = sum(_count_wikilinks(t) for t in notes.values())
        return round(total / len(notes), 2)

    wikilink_density = {
        "topics": _avg_links(topics),
        "concepts": _avg_links(concepts),
        "entities": _avg_links(entities),
        "source_summaries": _avg_links(summaries),
    }

    # --- stub ratio ---
    total_concepts = len(concepts)
    stub_count = sum(1 for t in concepts.values() if is_stub(t))
    stub_ratio = round(stub_count / total_concepts * 100, 1) if total_concepts else None

    # --- orphan detection ---
    # Build the full incoming-links map across all note types
    all_collections: dict[str, dict[str, str]] = {
        "topics": topics,
        "concepts": concepts,
        "entities": entities,
        "source_summaries": summaries,
    }
    # Also scan raw articles for wikilink targets
    raw_articles = _read_notes(root / "raw" / "articles")
    all_collections["raw_articles"] = raw_articles

    incoming = _all_wikilink_targets(all_collections)

    # Orphans: concept/entity notes with no incoming wikilinks from any other note
    def _is_orphan(stem: str) -> bool:
        targets = incoming.get(stem, set())
        # Remove self-links
        return len(targets - {stem}) == 0

    orphaned_concepts = [s for s in concepts if _is_orphan(s)]
    orphaned_entities = [s for s in entities if _is_orphan(s)]
    orphan_count = len(orphaned_concepts) + len(orphaned_entities)

    # Top-20 orphaned concepts (alpha sort for determinism; all are equally "orphaned")
    top_orphans = sorted(orphaned_concepts + orphaned_entities)[:20]

    # --- source coverage ---
    approved_summaries = [
        stem for stem, text in summaries.items() if _parse_yaml_bool(text, "approved")
    ]
    total_approved = len(approved_summaries)

    # Which approved summaries appear in at least one topic's compiled_from?
    referenced_in_topics: set[str] = set()
    for text in topics.values():
        for stem in _parse_compiled_from(text):
            referenced_in_topics.add(stem)

    covered = sum(1 for s in approved_summaries if s in referenced_in_topics)
    source_coverage = round(covered / total_approved * 100, 1) if total_approved else None

    # Average approved sources per topic
    topic_source_counts = [
        len([s for s in _parse_compiled_from(t) if s in set(approved_summaries)])
        for t in topics.values()
    ]
    avg_approved_per_topic = (
        round(sum(topic_source_counts) / len(topic_source_counts), 2)
        if topic_source_counts else 0.0
    )

    return {
        "date": date.today().isoformat(),
        "note_counts": counts,
        "wikilink_density": wikilink_density,
        "stub_ratio_pct": stub_ratio,
        "stub_count": stub_count,
        "total_concept_notes": total_concepts,
        "orphan_count": orphan_count,
        "orphaned_concepts": len(orphaned_concepts),
        "orphaned_entities": len(orphaned_entities),
        "top_orphans": top_orphans,
        "source_coverage_pct": source_coverage,
        "covered_approved_sources": covered,
        "total_approved_sources": total_approved,
        "avg_approved_sources_per_topic": avg_approved_per_topic,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def format_report(m: dict) -> str:
    nc = m["note_counts"]
    wd = m["wikilink_density"]
    lines = [
        f"Graph Health Report — {m['date']}",
        "=" * 50,
        "",
        "Note Counts",
        "-" * 30,
        f"  Topics          : {nc['topics']}",
        f"  Concepts        : {nc['concepts']}",
        f"  Entities        : {nc['entities']}",
        f"  Source summaries: {nc['source_summaries']}",
        "",
        "Wikilink Density (avg [[...]] per note)",
        "-" * 30,
        f"  Topics          : {wd['topics']:.2f}",
        f"  Concepts        : {wd['concepts']:.2f}",
        f"  Entities        : {wd['entities']:.2f}",
        f"  Source summaries: {wd['source_summaries']:.2f}",
        "",
        "Concept Stubs",
        "-" * 30,
        f"  Total concepts  : {m['total_concept_notes']}",
        f"  Stubs           : {m['stub_count']}",
        f"  Stub ratio      : {_pct(m['stub_ratio_pct'])}",
        "",
        "Orphans (no incoming wikilinks)",
        "-" * 30,
        f"  Orphaned concepts : {m['orphaned_concepts']}",
        f"  Orphaned entities : {m['orphaned_entities']}",
        f"  Total orphans     : {m['orphan_count']}",
    ]
    if m["top_orphans"]:
        lines.append("  Top orphans (up to 20):")
        for name in m["top_orphans"]:
            lines.append(f"    - {name}")
    else:
        lines.append("  (none)")
    lines += [
        "",
        "Source Coverage",
        "-" * 30,
        f"  Approved sources: {m['total_approved_sources']}",
        f"  Covered by topics: {m['covered_approved_sources']}",
        f"  Coverage        : {_pct(m['source_coverage_pct'])}",
        f"  Avg approved sources/topic: {m['avg_approved_sources_per_topic']:.2f}",
        "",
    ]
    return "\n".join(lines)


def format_diff(before: dict, after: dict) -> str:
    def _delta(key: str, fmt: str = ".2f") -> str:
        a = before.get(key)
        b = after.get(key)
        if a is None or b is None:
            return "N/A → N/A"
        delta = b - a
        sign = "+" if delta >= 0 else ""
        return f"{a:{fmt}} → {b:{fmt}} ({sign}{delta:{fmt}})"

    def _pct_delta(key: str) -> str:
        a = before.get(key)
        b = after.get(key)
        if a is None and b is None:
            return "N/A → N/A"
        if a is None:
            a = 0.0
        if b is None:
            b = 0.0
        delta = b - a
        sign = "+" if delta >= 0 else ""
        return f"{a:.1f}% → {b:.1f}% ({sign}{delta:.1f}pp)"

    def _int_delta(key: str) -> str:
        a = before.get(key, 0)
        b = after.get(key, 0)
        delta = b - a
        sign = "+" if delta >= 0 else ""
        return f"{a} → {b} ({sign}{delta})"

    lines = [
        f"Graph Health Comparison",
        f"  Before: {before.get('date', '?')}",
        f"  After : {after.get('date', '?')}",
        "=" * 50,
        "",
        "Note Counts",
        f"  Topics          : {_int_delta('note_counts_topics')}",
        f"  Concepts        : {_int_delta('note_counts_concepts')}",
        f"  Entities        : {_int_delta('note_counts_entities')}",
        f"  Source summaries: {_int_delta('note_counts_source_summaries')}",
        "",
        "Wikilink Density",
        f"  Topics          : {_delta('wikilink_density_topics')}",
        f"  Concepts        : {_delta('wikilink_density_concepts')}",
        f"  Entities        : {_delta('wikilink_density_entities')}",
        "",
        "Stubs",
        f"  Stub ratio      : {_pct_delta('stub_ratio_pct')}",
        f"  Stub count      : {_int_delta('stub_count')}",
        "",
        "Orphans",
        f"  Total orphans   : {_int_delta('orphan_count')}",
        "",
        "Source Coverage",
        f"  Coverage        : {_pct_delta('source_coverage_pct')}",
        f"  Avg sources/topic: {_delta('avg_approved_sources_per_topic')}",
        "",
    ]
    return "\n".join(lines)


def _flatten(m: dict) -> dict:
    """Flatten nested metrics dict for diff comparison."""
    flat: dict = {}
    for k, v in m.items():
        if isinstance(v, dict):
            for subk, subv in v.items():
                flat[f"{k}_{subk}"] = subv
        elif k != "top_orphans":
            flat[k] = v
    return flat


# ---------------------------------------------------------------------------
# JSON snapshot I/O
# ---------------------------------------------------------------------------

SNAPSHOTS_DIR = ROOT / "outputs" / "graph_health"


def save_snapshot(metrics: dict) -> Path:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SNAPSHOTS_DIR / f"{metrics['date']}.json"
    dest.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return dest


def load_most_recent_snapshot(exclude_date: str | None = None) -> dict | None:
    if not SNAPSHOTS_DIR.exists():
        return None
    candidates = sorted(SNAPSHOTS_DIR.glob("*.json"), reverse=True)
    for path in candidates:
        if exclude_date and path.stem == exclude_date:
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(root: Path, json_only: bool, compare: bool) -> int:
    metrics = compute_metrics(root)

    if compare:
        prior = load_most_recent_snapshot(exclude_date=metrics["date"])
        if prior is None:
            print("No prior snapshot found for comparison.", file=sys.stderr)
            return 1
        before_flat = _flatten(prior)
        after_flat = _flatten(metrics)
        print(format_diff(before_flat, after_flat))
        # Still save today's snapshot
        snap_path = save_snapshot(metrics)
        print(f"Snapshot saved: {snap_path.relative_to(root)}")
        return 0

    snap_path = save_snapshot(metrics)

    if not json_only:
        print(format_report(metrics))
        print(f"Snapshot saved: {snap_path.relative_to(root)}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2A-1 Graph Health Baseline: static analysis of the knowledge graph."
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Suppress stdout report; write JSON snapshot only.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Diff today vs most recent prior snapshot.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(root=ROOT, json_only=args.json_only, compare=args.compare)


if __name__ == "__main__":
    sys.exit(main())

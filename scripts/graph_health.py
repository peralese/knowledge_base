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
from datetime import date, datetime
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

    now = datetime.now()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.strftime("%Y-%m-%d-%H%M%S"),
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


def format_diff(before: dict, after: dict, snap_a: str = "", snap_b: str = "") -> str:
    """Render a before/after diff table with ✓ (improvement), ✗ (regression), — (no change)."""

    COL_METRIC = 30
    COL_VAL = 10

    def _header() -> list[str]:
        lines = [
            "Graph Health Comparison",
            f"  Snapshot A : {snap_a or before.get('timestamp', before.get('date', '?')) + '.json'}",
            f"  Snapshot B : {snap_b or after.get('timestamp', after.get('date', '?')) + '.json'} (current)",
            "",
            f"  {'Metric':<{COL_METRIC}} {'Before':<{COL_VAL}} {'After':<{COL_VAL}} Delta",
            "  " + "-" * 55,
        ]
        return lines

    def _row(
        label: str,
        a_val: float | int | None,
        b_val: float | int | None,
        fmt: str = "int",       # "int" | "float2" | "pct"
        improvement: str = "down",  # "down" | "up" | "none"
    ) -> str:
        if a_val is None and b_val is None:
            a_str = b_str = "N/A"
            delta_str = "—"
        elif a_val is None or b_val is None:
            a_str = "N/A" if a_val is None else _fmt(a_val, fmt)
            b_str = "N/A" if b_val is None else _fmt(b_val, fmt)
            delta_str = "—"
        else:
            a_str = _fmt(a_val, fmt)
            b_str = _fmt(b_val, fmt)
            delta = b_val - a_val
            if abs(delta) < 1e-9:
                delta_str = "—"
            else:
                sign = "+" if delta > 0 else ""
                d_str = _fmt(delta, fmt, signed=True)
                if improvement == "none" or abs(delta) < 1e-9:
                    marker = "—"
                elif (improvement == "down" and delta < 0) or (improvement == "up" and delta > 0):
                    marker = "✓"
                else:
                    marker = "✗"
                delta_str = f"{sign}{d_str} {marker}" if delta != 0 else "—"
        return f"  {label:<{COL_METRIC}} {a_str:<{COL_VAL}} {b_str:<{COL_VAL}} {delta_str}"

    def _fmt(v: float | int, fmt: str, signed: bool = False) -> str:
        if fmt == "pct":
            return f"{v:.1f}%"
        if fmt == "float2":
            return f"{v:.2f}"
        return str(int(round(v)))

    nc_a = before.get("note_counts", {})
    nc_b = after.get("note_counts", {})
    wd_a = before.get("wikilink_density", {})
    wd_b = after.get("wikilink_density", {})

    rows = _header() + [
        _row("Topics", nc_a.get("topics"), nc_b.get("topics"), improvement="none"),
        _row("Concepts", nc_a.get("concepts"), nc_b.get("concepts"), improvement="none"),
        _row("Entities", nc_a.get("entities"), nc_b.get("entities"), improvement="none"),
        _row("Source summaries", nc_a.get("source_summaries"), nc_b.get("source_summaries"), improvement="none"),
        "  " + "-" * 55,
        _row("Stubs", before.get("stub_count"), after.get("stub_count"), improvement="down"),
        _row("Stub ratio", before.get("stub_ratio_pct"), after.get("stub_ratio_pct"), fmt="pct", improvement="down"),
        _row("Orphaned concepts", before.get("orphaned_concepts"), after.get("orphaned_concepts"), improvement="down"),
        _row("Orphaned entities", before.get("orphaned_entities"), after.get("orphaned_entities"), improvement="down"),
        "  " + "-" * 55,
        _row("Wikilink density (topics)", wd_a.get("topics"), wd_b.get("topics"), fmt="float2", improvement="up"),
        _row("Wikilink density (concepts)", wd_a.get("concepts"), wd_b.get("concepts"), fmt="float2", improvement="up"),
        _row("Wikilink density (entities)", wd_a.get("entities"), wd_b.get("entities"), fmt="float2", improvement="up"),
        "  " + "-" * 55,
        _row("Approved sources", before.get("total_approved_sources"), after.get("total_approved_sources"), improvement="none"),
        _row("Source coverage", before.get("source_coverage_pct"), after.get("source_coverage_pct"), fmt="pct", improvement="up"),
        _row("Avg sources/topic", before.get("avg_approved_sources_per_topic"), after.get("avg_approved_sources_per_topic"), fmt="float2", improvement="up"),
        "",
    ]
    return "\n".join(rows)


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

# Filename pattern: YYYY-MM-DD-HHMMSS.json
# Lexicographic sort on this format is chronological.
_SNAPSHOT_GLOB = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].json"


def save_snapshot(metrics: dict) -> Path:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = metrics.get("timestamp", metrics["date"] + "-000000")
    dest = SNAPSHOTS_DIR / f"{ts}.json"
    dest.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return dest


def load_prior_snapshot(current_timestamp: str) -> tuple[dict, str] | None:
    """Return (snapshot_data, filename_stem) of the most recent snapshot
    whose timestamp is strictly earlier than current_timestamp, or None.

    Snapshots with the legacy YYYY-MM-DD.json format are treated as having
    timestamp YYYY-MM-DD-000000 for ordering purposes.
    """
    if not SNAPSHOTS_DIR.exists():
        return None

    def _stem_to_ts(stem: str) -> str:
        # Normalize legacy date-only stems to timestamped form
        if len(stem) == 10:  # YYYY-MM-DD
            return stem + "-000000"
        return stem

    candidates: list[tuple[str, Path]] = []
    for path in SNAPSHOTS_DIR.glob("*.json"):
        ts = _stem_to_ts(path.stem)
        if ts < current_timestamp:
            candidates.append((ts, path))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, best_path = candidates[0]
    try:
        data = json.loads(best_path.read_text(encoding="utf-8"))
        return data, best_path.stem
    except (json.JSONDecodeError, OSError):
        return None


def load_most_recent_snapshot(exclude_timestamp: str | None = None) -> dict | None:
    """Return the most recent snapshot, optionally excluding a specific timestamp stem."""
    if not SNAPSHOTS_DIR.exists():
        return None
    candidates = sorted(SNAPSHOTS_DIR.glob("*.json"), reverse=True)
    for path in candidates:
        if exclude_timestamp and path.stem == exclude_timestamp:
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
    current_ts = metrics["timestamp"]

    # Always save the new snapshot first so it anchors future comparisons
    snap_path = save_snapshot(metrics)

    if compare:
        result = load_prior_snapshot(current_ts)
        if result is None:
            print(
                "No prior snapshot to compare against — this is the first recorded baseline.\n"
                f"Snapshot saved: {snap_path.relative_to(root)}"
            )
            return 0
        prior, prior_stem = result
        print(format_diff(prior, metrics, snap_a=prior_stem + ".json", snap_b=snap_path.name))
        print(f"\nSnapshot saved: {snap_path.relative_to(root)}")
        return 0

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

"""Phase 5 Topic Aggregation: classify source summaries into canonical topic notes.

After a source summary is synthesized, this script checks the article title and body
against the topic registry (alias/keyword matching). On a match it creates or updates
the canonical topic note in compiled/topics/, merging insights from the new source into
the growing topic synthesis.

Usage:
    # Aggregate one item by source_id
    python3 scripts/topic_aggregator.py --source-id SRC-20260415-0001

    # Aggregate all synthesized items that match a topic
    python3 scripts/topic_aggregator.py --all

    # List topic notes and their contributing source summaries
    python3 scripts/topic_aggregator.py --list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPIC_REGISTRY_PATH = ROOT / "metadata" / "topic-registry.json"
REVIEW_QUEUE_PATH = ROOT / "metadata" / "review-queue.json"
TOPICS_DIR = ROOT / "compiled" / "topics"
SOURCE_SUMMARIES_DIR = ROOT / "compiled" / "source_summaries"
DEFAULT_MODEL = "qwen2.5:14b"

# Import llm_driver at module level so tests can patch call_ollama on this module.
sys.path.insert(0, str(Path(__file__).parent))
from git_ops import commit_pipeline_stage  # noqa: E402, PLC0415
from llm_driver import _check_model_available, call_ollama  # noqa: E402, PLC0415


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AggregateRequest:
    topic_slug: str
    new_source_summary_path: Path
    new_source_id: str
    model: str = DEFAULT_MODEL
    force: bool = False
    root: Path = field(default_factory=lambda: ROOT)
    no_commit: bool = False


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_topic_registry(root: Path = ROOT) -> dict[str, object]:
    """Load topic-registry.json as a raw dict."""
    path = root / "metadata" / "topic-registry.json"
    if not path.exists():
        return {"topics": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"topics": []}


def _normalize_text(text: str) -> str:
    """Lowercase, replace non-alphanumeric chars with spaces, collapse runs of spaces."""
    normalized = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    return " ".join(normalized.split())


def classify_to_topic(title: str, body: str, registry: dict[str, object]) -> str | None:
    """Match article title + body against topic registry aliases.

    Returns the matching topic slug, or None if no match found.
    Checks the article title and the first 2000 chars of body (case-insensitive).
    Punctuation is normalized to spaces so "OpenClaw: Security" matches "openclaw security".
    """
    text = _normalize_text(title + " " + body[:2000])
    for topic in registry.get("topics", []):
        slug = str(topic.get("slug", ""))
        # Check slug itself (hyphens replaced with spaces)
        if _normalize_text(slug.replace("-", " ")) in text:
            return slug
        # Check each alias
        for alias in topic.get("aliases", []):
            if _normalize_text(str(alias).strip()) in text:
                return slug
    return None


def _title_for_slug(slug: str, registry: dict[str, object]) -> str:
    """Return the canonical title for a topic slug, or a title-cased fallback."""
    for topic in registry.get("topics", []):
        if topic.get("slug") == slug:
            return str(topic.get("title", slug))
    return slug.replace("-", " ").title()


def _registry_slugs(registry: dict[str, object]) -> set[str]:
    return {str(topic.get("slug", "")) for topic in registry.get("topics", []) if topic.get("slug")}


def _parse_frontmatter_list(text: str, key: str) -> list[str]:
    """Extract a simple YAML list from markdown frontmatter."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        return []
    lines = fm_match.group(1).splitlines()
    values: list[str] = []
    in_key = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if in_key:
            if stripped.startswith("- "):
                values.append(stripped[2:].strip().strip('"').strip("'"))
                continue
            if raw_line and not raw_line.startswith((" ", "\t")):
                break
        if stripped == f"{key}: []":
            return []
        if stripped == f"{key}:":
            in_key = True
            continue
        if stripped.startswith(f"{key}:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            return [value] if value and value != "[]" else []
    return [value for value in values if value]


def explicit_topic_for_source(item: dict[str, object], raw_note_body: str, registry: dict[str, object]) -> str | None:
    """Return a user-selected topic slug when present and valid."""
    valid_slugs = _registry_slugs(registry)
    candidates: list[str] = []
    queue_topic = str(item.get("topic_slug", "")).strip()
    if queue_topic:
        candidates.append(queue_topic)
    candidates.extend(_parse_frontmatter_list(raw_note_body, "topics"))

    for candidate in candidates:
        if candidate in valid_slugs:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Topic note I/O
# ---------------------------------------------------------------------------

def load_topic_note(topic_slug: str, root: Path = ROOT) -> str | None:
    """Return the full text of an existing topic note, or None if it doesn't exist."""
    path = root / "compiled" / "topics" / f"{topic_slug}.md"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _parse_compiled_from(existing_md: str) -> list[str]:
    """Extract the compiled_from list from existing topic note frontmatter."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", existing_md, re.DOTALL)
    if not fm_match:
        return []
    fm_text = fm_match.group(1)
    cf_match = re.search(r"^compiled_from:\s*\n((?:[ \t]+-[ \t]+.+\n)*)", fm_text, re.MULTILINE)
    if not cf_match:
        return []
    stems = []
    for line in cf_match.group(1).splitlines():
        stem = line.strip().lstrip("-").strip().strip('"').strip("'")
        if stem:
            stems.append(stem)
    return stems


def _parse_date_compiled(existing_md: str) -> str:
    """Extract the date_compiled value from existing topic note frontmatter."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", existing_md, re.DOTALL)
    if not fm_match:
        return datetime.now().date().isoformat()
    dc_match = re.search(r'^date_compiled:\s*"?([^"\n]+)"?', fm_match.group(1), re.MULTILINE)
    return dc_match.group(1).strip() if dc_match else datetime.now().date().isoformat()


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter if the LLM echoed it back."""
    stripped = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL).strip()
    return stripped


def _strip_fence(text: str) -> str:
    """Strip leading/trailing ```markdown or ``` fences if present."""
    text = re.sub(r"^```(?:markdown)?\s*\n", "", text.strip())
    text = re.sub(r"\n```\s*$", "", text.strip())
    return text.strip()


def _ensure_source_notes_section(body: str, compiled_from: list[str]) -> str:
    """Replace or append correct # Source Notes and # Lineage sections."""
    body = re.sub(r"\n# Source Notes\b.*?(?=\n# |\Z)", "", body, flags=re.DOTALL).strip()
    body = re.sub(r"\n# Lineage\b.*?(?=\n# |\Z)", "", body, flags=re.DOTALL).strip()

    source_links = "\n".join(f"- [[{stem}]]" for stem in compiled_from)
    body += f"\n\n# Source Notes\n\n{source_links}\n\n# Lineage\n\n{source_links}\n"
    return body


def _build_topic_note(
    *,
    existing_md: str | None,
    topic_slug: str,
    topic_title: str,
    new_source_stem: str,
    llm_body: str,
    generation_method: str,
) -> str:
    """Assemble the full topic note markdown (frontmatter + body)."""
    today = datetime.now().date().isoformat()

    # Build compiled_from: start from existing, add new stem
    if existing_md:
        compiled_from = _parse_compiled_from(existing_md)
        date_compiled = _parse_date_compiled(existing_md)
    else:
        compiled_from = []
        date_compiled = today

    if new_source_stem and new_source_stem not in compiled_from:
        compiled_from.append(new_source_stem)

    # Build YAML frontmatter
    cf_lines = "\n".join(f'  - "{stem}"' for stem in compiled_from)
    frontmatter = (
        f'---\n'
        f'title: "{topic_title}"\n'
        f'note_type: "topic"\n'
        f'compiled_from: \n'
        f'{cf_lines}\n'
        f'date_compiled: "{date_compiled}"\n'
        f'date_updated: "{today}"\n'
        f'topics:\n'
        f'  - "{topic_title}"\n'
        f'tags:\n'
        f'  - "topic"\n'
        f'  - "{topic_slug}"\n'
        f'confidence: "medium"\n'
        f'generation_method: "{generation_method}"\n'
        f'approved: true\n'
        f'---'
    )

    # Clean LLM body and ensure correct sections
    body = _strip_fence(_strip_frontmatter(llm_body))
    body = _ensure_source_notes_section(body, compiled_from)

    return f"{frontmatter}\n\n{body.strip()}\n"


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

_NEW_TOPIC_TEMPLATE = """\
You are synthesizing a topic note for "{topic_title}".

Write a comprehensive topic note that captures the key insights, best practices, and \
concepts from the source summary below. This note will grow over time as more sources \
are added on this topic.

Return ONLY the markdown body — no YAML frontmatter, no code fences. Use exactly these \
sections in this order:

# Summary
# Key Insights
# Related Concepts

Source summary to synthesize:
---
{source_summary}
---
"""

_UPDATE_TOPIC_TEMPLATE = """\
You are updating the topic note for "{topic_title}" with a new source summary.

Rules:
- Preserve ALL existing insights from the current topic note.
- Incorporate new insights from the new source summary.
- Merge or consolidate any duplicate points — do not repeat them.
- Keep the note concise and well-structured.

Return ONLY the updated markdown body — no YAML frontmatter, no code fences. Use exactly \
these sections in this order:

# Summary
# Key Insights
# Related Concepts

Current topic note body:
---
{existing_body}
---

New source summary to incorporate:
---
{source_summary}
---
"""


def build_aggregate_prompt(
    topic_title: str,
    existing_note: str | None,
    new_source_summary: str,
) -> str:
    """Return the LLM prompt for topic aggregation (new or update)."""
    if existing_note is None:
        return _NEW_TOPIC_TEMPLATE.format(
            topic_title=topic_title,
            source_summary=new_source_summary,
        )
    # Strip frontmatter from existing note before including in prompt
    existing_body = _strip_frontmatter(existing_note)
    return _UPDATE_TOPIC_TEMPLATE.format(
        topic_title=topic_title,
        existing_body=existing_body,
        source_summary=new_source_summary,
    )


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------

def aggregate_topic(request: AggregateRequest) -> Path:
    """Create or update the topic note for request.topic_slug.

    Reads the new source summary, builds a prompt, calls Ollama, and writes
    compiled/topics/{slug}.md.  Falls back to a scaffold if Ollama is unavailable.
    Returns the path of the written topic note.
    """
    from urllib.error import URLError  # noqa: PLC0415

    registry = load_topic_registry(request.root)
    topic_title = _title_for_slug(request.topic_slug, registry)
    existing_md = load_topic_note(request.topic_slug, request.root)
    new_source_summary = request.new_source_summary_path.read_text(encoding="utf-8")
    new_source_stem = request.new_source_summary_path.stem

    output_path = request.root / "compiled" / "topics" / f"{request.topic_slug}.md"

    if output_path.exists() and not request.force and existing_md is None:
        # Should not happen but guard against it
        existing_md = output_path.read_text(encoding="utf-8")

    prompt = build_aggregate_prompt(topic_title, existing_md, new_source_summary)
    generation_method = "ollama_local"

    try:
        _check_model_available(request.model)
        llm_body = call_ollama(prompt, request.model)
    except (ConnectionError, ValueError, URLError, OSError):
        # Scaffold fallback: write a minimal topic note body
        generation_method = "scaffold"
        source_link = f"[[{new_source_stem}]]"
        llm_body = (
            f"# Summary\n\n"
            f"Topic note for {topic_title}. See source summaries for details.\n\n"
            f"# Key Insights\n\n"
            f"- See {source_link} for insights.\n\n"
            f"# Related Concepts\n\n"
            f"- {topic_title}\n"
        )

    note_text = _build_topic_note(
        existing_md=existing_md,
        topic_slug=request.topic_slug,
        topic_title=topic_title,
        new_source_stem=new_source_stem,
        llm_body=llm_body,
        generation_method=generation_method,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(note_text, encoding="utf-8")
    commit_pipeline_stage(
        message=f"topic: updated {request.topic_slug} (+{request.new_source_id})",
        paths=[output_path],
        no_commit=request.no_commit,
    )
    return output_path


def aggregate_for_source(
    item: dict[str, object],
    source_summary_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    root: Path = ROOT,
    no_commit: bool = False,
) -> Path | None:
    """Classify a source article and aggregate into the matching topic note.

    Called from synthesize.py after synthesis + scoring. Non-blocking by design —
    the caller wraps this in a try/except.
    Returns the written topic note path, or None if skipped.
    """
    title = str(item.get("title", ""))
    raw_note_path = root / str(item.get("source_note_path", ""))

    body = ""
    if raw_note_path.exists():
        body = raw_note_path.read_text(encoding="utf-8", errors="replace")

    registry = load_topic_registry(root)
    topic_slug = explicit_topic_for_source(item, body, registry) or classify_to_topic(title, body, registry)

    if topic_slug is None:
        print("  Topic       : no registry match — skipping aggregation")
        return None

    source_id = str(item.get("source_id", ""))
    print(f"  Topic       : {topic_slug}")

    result_path = aggregate_topic(AggregateRequest(
        topic_slug=topic_slug,
        new_source_summary_path=source_summary_path,
        new_source_id=source_id,
        model=model,
        root=root,
        no_commit=no_commit,
    ))
    print(f"  Topic note  : {result_path.relative_to(root)}")
    return result_path


# ---------------------------------------------------------------------------
# Queue helpers (for CLI commands)
# ---------------------------------------------------------------------------

def _load_queue(root: Path = ROOT) -> list[dict[str, object]]:
    path = root / "metadata" / "review-queue.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _find_source_summary(item: dict[str, object], root: Path) -> Path | None:
    """Derive the compiled source summary path from a queue entry."""
    note_path_str = str(item.get("source_note_path", ""))
    if not note_path_str:
        return None
    slug = Path(note_path_str).stem
    candidate = root / "compiled" / "source_summaries" / f"{slug}-synthesis.md"
    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_aggregate_one(source_id: str, *, model: str, root: Path, no_commit: bool = False) -> int:
    queue = _load_queue(root)
    item = next((e for e in queue if e.get("source_id") == source_id), None)
    if item is None:
        print(f"Error: '{source_id}' not found in review queue.", file=sys.stderr)
        return 1

    summary_path = _find_source_summary(item, root)
    if summary_path is None:
        print(f"Error: source summary not found for '{source_id}'.", file=sys.stderr)
        return 1

    print(f"Aggregating: {item.get('title', source_id)}  ({source_id})")
    aggregate_for_source(item, summary_path, model=model, root=root, no_commit=no_commit)
    return 0


def cmd_aggregate_all(*, model: str, root: Path, no_commit: bool = False) -> int:
    queue = _load_queue(root)
    registry = load_topic_registry(root)
    candidates = [e for e in queue if e.get("review_status") in {"synthesized", "approved"}]

    if not candidates:
        print("No synthesized items to aggregate.")
        return 0

    print(f"Checking {len(candidates)} item(s) for topic matches...\n")
    matched = 0
    for item in candidates:
        title = str(item.get("title", ""))
        raw_note_path = root / str(item.get("source_note_path", ""))
        body = raw_note_path.read_text(encoding="utf-8", errors="replace") if raw_note_path.exists() else ""
        topic_slug = explicit_topic_for_source(item, body, registry) or classify_to_topic(title, body, registry)
        if topic_slug is None:
            continue

        summary_path = _find_source_summary(item, root)
        if summary_path is None:
            print(f"  Skipping {item.get('source_id')}: source summary not found.")
            continue

        source_id = str(item.get("source_id", ""))
        print(f"Aggregating: {title}  ({source_id}) → {topic_slug}")
        try:
            result_path = aggregate_topic(AggregateRequest(
                topic_slug=topic_slug,
                new_source_summary_path=summary_path,
                new_source_id=source_id,
                model=model,
                root=root,
                no_commit=no_commit,
            ))
            print(f"  Topic note  : {result_path.relative_to(root)}")
        except Exception as exc:  # noqa: BLE001
            print(f"  Error: {exc}")
        matched += 1
        print()

    if matched == 0:
        print("No items matched any topic in the registry.")
    else:
        print(f"Done: {matched} item(s) aggregated.")
    return 0


def cmd_list(root: Path) -> int:
    topics_dir = root / "compiled" / "topics"
    if not topics_dir.exists() or not any(topics_dir.glob("*.md")):
        print("No topic notes found.")
        return 0

    print(f"\n{'Topic':<30} {'Sources'}")
    print("-" * 60)
    for path in sorted(topics_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        compiled_from = _parse_compiled_from(text)
        count = len(compiled_from)
        print(f"{path.stem:<30} {count} source(s)")
        for stem in compiled_from:
            print(f"  - {stem}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 5 Topic Aggregation: classify source summaries into canonical topic notes.\n"
            "Matches articles against topic-registry.json (alias/keyword) and creates or\n"
            "updates compiled/topics/{slug}.md with merged insights."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--source-id",
        metavar="SRC_ID",
        help="Aggregate one item by source_id (e.g. SRC-20260415-0001).",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Aggregate all synthesized items that match a topic.",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List topic notes and their contributing source summaries.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        dest="no_commit",
        help="Skip git auto-commit after aggregation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        return cmd_list(ROOT)

    if args.all:
        return cmd_aggregate_all(model=args.model, root=ROOT, no_commit=args.no_commit)

    if args.source_id:
        return cmd_aggregate_one(args.source_id, model=args.model, root=ROOT, no_commit=args.no_commit)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Phase 13 Concept & Entity Aggregation: extract concepts and entities from approved source summaries.

For each approved source summary, calls the LLM to extract:
  - Concepts: abstract ideas, techniques, methodologies, frameworks
  - Entities: named tools, companies, people, specific products

Creates/updates notes in compiled/concepts/ and compiled/entities/ and maintains
metadata/concept-registry.json and metadata/entity-registry.json.

Usage:
    # Extract from one source summary (by stem, e.g. "my-article-synthesis")
    python3 scripts/concept_aggregator.py --source my-article-synthesis

    # Process all approved source summaries not yet extracted
    python3 scripts/concept_aggregator.py --all

    # Preview without writing files
    python3 scripts/concept_aggregator.py --all --dry-run

    # Skip git auto-commits
    python3 scripts/concept_aggregator.py --all --no-commit
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"

CONCEPTS_DIR = ROOT / "compiled" / "concepts"
ENTITIES_DIR = ROOT / "compiled" / "entities"
CONCEPT_REGISTRY_PATH = ROOT / "metadata" / "concept-registry.json"
ENTITY_REGISTRY_PATH = ROOT / "metadata" / "entity-registry.json"
SOURCE_SUMMARIES_DIR = ROOT / "compiled" / "source_summaries"

VALID_ENTITY_TYPES = {"tool", "company", "person", "framework", "product"}

sys.path.insert(0, str(Path(__file__).parent))
from git_ops import commit_pipeline_stage  # noqa: E402
from llm_driver import _check_model_available, call_ollama  # noqa: E402


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry(path: Path) -> dict:
    if not path.exists():
        key = "concepts" if "concept" in path.name else "entities"
        return {key: []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    key = "concepts" if "concept" in path.name else "entities"
    return {key: []}


def save_registry(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _update_registry_entry(
    registry: dict, key: str, slug: str, title: str, source_stem: str, today: str,
    extra: dict | None = None,
) -> dict:
    entries = registry.setdefault(key, [])
    for entry in entries:
        if entry.get("slug") == slug:
            sources = entry.setdefault("sources", [])
            if source_stem not in sources:
                sources.append(source_stem)
            entry["date_updated"] = today
            return registry
    new_entry: dict = {
        "slug": slug,
        "title": title,
        "sources": [source_stem],
        "date_first_seen": today,
        "date_updated": today,
    }
    if extra:
        new_entry.update(extra)
    entries.append(new_entry)
    return registry


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str) -> tuple[dict, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized.strip()
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return {}, normalized.strip()
    fm_text = normalized[4:end]
    body = normalized[end + 5:].strip()
    data: dict = {}
    current_key = ""
    for raw_line in fm_text.splitlines():
        stripped = raw_line.strip()
        if current_key and stripped.startswith("- "):
            value = stripped[2:].strip().strip('"').strip("'")
            values = data.setdefault(current_key, [])
            if isinstance(values, list):
                values.append(value)
            continue
        current_key = ""
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", stripped)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            data[key] = []
            current_key = key
        elif value.startswith("[") and value.endswith("]"):
            data[key] = [
                item.strip().strip('"').strip("'")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        else:
            data[key] = value.strip('"').strip("'")
    return data, body


def _yaml_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def _parse_sources_from_note(text: str) -> list[str]:
    fm, _ = _split_frontmatter(text)
    sources = fm.get("sources", [])
    if isinstance(sources, list):
        return [str(s) for s in sources]
    if isinstance(sources, str) and sources:
        return [sources]
    return []


def _parse_date_compiled_from_note(text: str, fallback: str) -> str:
    fm, _ = _split_frontmatter(text)
    return str(fm.get("date_compiled") or fallback)


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

def build_extraction_prompt(source_summary: str) -> str:
    return f"""You are extracting structured knowledge from a source summary note.

From the source summary below, extract:
1. CONCEPTS: abstract ideas, techniques, methodologies, or frameworks
   (examples: zero-trust, retrieval-augmented-generation, bm25-scoring)
2. ENTITIES: named tools, products, companies, people, or specific frameworks
   (examples: ollama, anthropic, llamaindex, karpathy)

Return ONLY a JSON object with this exact structure — no explanation, no code fences:
{{
  "concepts": [
    {{"slug": "zero-trust", "title": "Zero Trust", "context": "one sentence describing how this source discusses the concept"}},
    ...
  ],
  "entities": [
    {{"slug": "ollama", "title": "Ollama", "entity_type": "tool", "context": "one sentence describing how this source uses or references it"}},
    ...
  ]
}}

Rules:
- slugs must be lowercase, hyphenated (e.g. "zero-trust", not "Zero Trust")
- entity_type must be one of: tool, company, person, framework, product
- context must be specific to this source, not a generic definition
- Return {{"concepts": [], "entities": []}} if nothing meaningful is found
- Maximum 10 concepts and 10 entities

Source summary:
---
{source_summary}
---"""


def _parse_extraction_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"concepts": [], "entities": []}
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return {"concepts": [], "entities": []}
    if not isinstance(data, dict):
        return {"concepts": [], "entities": []}
    concepts = data.get("concepts", [])
    entities = data.get("entities", [])
    if not isinstance(concepts, list):
        concepts = []
    if not isinstance(entities, list):
        entities = []
    return {"concepts": concepts, "entities": entities}


# ---------------------------------------------------------------------------
# Note builders
# ---------------------------------------------------------------------------

def _render_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _append_mentioned_in(body: str, source_stem: str, context: str) -> str:
    entry = f"- [[{source_stem}]] — {context}"
    section_re = re.compile(r"(## Mentioned In\s*\n)(.*?)(?=\n## |\Z)", re.DOTALL)
    m = section_re.search(body)
    if m:
        existing = m.group(2).rstrip("\n")
        if source_stem in existing:
            return body
        new_section = m.group(1) + (existing + "\n" if existing else "") + entry + "\n"
        return body[: m.start()] + new_section + body[m.end():]
    return body + f"\n## Mentioned In\n\n{entry}\n"


def build_concept_note(
    *,
    existing_text: str | None,
    slug: str,
    title: str,
    source_stem: str,
    context: str,
    generation_method: str,
    today: str,
) -> str:
    if existing_text is not None:
        fm, body = _split_frontmatter(existing_text)
        sources = list(fm.get("sources", []) or [])
        if isinstance(sources, str):
            sources = [sources]
        already_present = source_stem in sources
        if not already_present:
            sources.append(source_stem)
        date_compiled = str(fm.get("date_compiled") or today)
        fm["sources"] = sources
        fm["date_updated"] = today
        new_body = _append_mentioned_in(body, source_stem, context) if not already_present else body
        return f"{_render_frontmatter(fm)}\n\n{new_body.strip()}\n"

    fm = {
        "title": f'"{title}"',
        "note_type": "concept",
        "slug": slug,
        "date_compiled": today,
        "date_updated": today,
        "sources": [source_stem],
        "approved": "true",
        "generation_method": f'"{generation_method}"',
    }
    body = (
        f"# {title}\n\n"
        "_Definition not yet written. Update this stub with content from the sources below._\n\n"
        f"## Mentioned In\n\n"
        f"- [[{source_stem}]] — {context}\n\n"
        "## Related Concepts\n"
    )
    return f"{_render_frontmatter(fm)}\n\n{body}"


def build_entity_note(
    *,
    existing_text: str | None,
    slug: str,
    title: str,
    entity_type: str,
    source_stem: str,
    context: str,
    generation_method: str,
    today: str,
) -> str:
    entity_type = entity_type if entity_type in VALID_ENTITY_TYPES else "tool"

    if existing_text is not None:
        fm, body = _split_frontmatter(existing_text)
        sources = list(fm.get("sources", []) or [])
        if isinstance(sources, str):
            sources = [sources]
        already_present = source_stem in sources
        if not already_present:
            sources.append(source_stem)
        fm["sources"] = sources
        fm["date_updated"] = today
        new_body = _append_mentioned_in(body, source_stem, context) if not already_present else body
        return f"{_render_frontmatter(fm)}\n\n{new_body.strip()}\n"

    fm = {
        "title": f'"{title}"',
        "note_type": "entity",
        "entity_type": entity_type,
        "slug": slug,
        "date_compiled": today,
        "date_updated": today,
        "sources": [source_stem],
        "approved": "true",
        "generation_method": f'"{generation_method}"',
    }
    body = (
        f"# {title}\n\n"
        "_Description not yet written. Update this stub with content from the sources below._\n\n"
        f"## Mentioned In\n\n"
        f"- [[{source_stem}]] — {context}\n"
    )
    return f"{_render_frontmatter(fm)}\n\n{body}"


# ---------------------------------------------------------------------------
# Core extraction orchestration
# ---------------------------------------------------------------------------

def extract_concepts_and_entities(
    source_summary_text: str,
    source_stem: str,
    *,
    model: str = DEFAULT_MODEL,
    root: Path = ROOT,
    dry_run: bool = False,
    no_commit: bool = False,
) -> dict:
    """Extract concepts and entities from one source summary. Returns paths written."""
    concepts_dir = root / "compiled" / "concepts"
    entities_dir = root / "compiled" / "entities"
    concept_registry_path = root / "metadata" / "concept-registry.json"
    entity_registry_path = root / "metadata" / "entity-registry.json"

    today = date.today().isoformat()
    generation_method = "ollama_local"

    # LLM call (with scaffold fallback)
    extraction = {"concepts": [], "entities": []}
    try:
        _check_model_available(model)
        raw = call_ollama(build_extraction_prompt(source_summary_text), model)
        extraction = _parse_extraction_json(raw)
    except (ConnectionError, ValueError, URLError, OSError):
        generation_method = "scaffold"

    concepts = extraction.get("concepts", []) or []
    entities = extraction.get("entities", []) or []

    if not concepts and not entities:
        return {"concepts_written": [], "entities_written": []}

    if dry_run:
        return {"concepts_written": [], "entities_written": [], "dry_run": True, "extraction": extraction}

    concept_registry = load_registry(concept_registry_path)
    entity_registry = load_registry(entity_registry_path)

    concepts_written: list[Path] = []
    entities_written: list[Path] = []

    for item in concepts:
        if not isinstance(item, dict):
            continue
        raw_slug = str(item.get("slug") or item.get("title") or "")
        title = str(item.get("title") or raw_slug.replace("-", " ").title())
        context = str(item.get("context") or "mentioned in this source")
        if not raw_slug:
            continue
        slug = _slugify(raw_slug)
        if not slug:
            continue

        note_path = concepts_dir / f"{slug}.md"
        existing_text = note_path.read_text(encoding="utf-8", errors="replace") if note_path.exists() else None

        if existing_text is not None:
            existing_sources = _parse_sources_from_note(existing_text)
            if source_stem in existing_sources:
                continue

        note_text = build_concept_note(
            existing_text=existing_text,
            slug=slug,
            title=title,
            source_stem=source_stem,
            context=context,
            generation_method=generation_method,
            today=today,
        )
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(note_text, encoding="utf-8")
        concepts_written.append(note_path)
        _update_registry_entry(concept_registry, "concepts", slug, title, source_stem, today)

    for item in entities:
        if not isinstance(item, dict):
            continue
        raw_slug = str(item.get("slug") or item.get("title") or "")
        title = str(item.get("title") or raw_slug.replace("-", " ").title())
        context = str(item.get("context") or "mentioned in this source")
        entity_type = str(item.get("entity_type") or "tool")
        if not raw_slug:
            continue
        slug = _slugify(raw_slug)
        if not slug:
            continue

        note_path = entities_dir / f"{slug}.md"
        existing_text = note_path.read_text(encoding="utf-8", errors="replace") if note_path.exists() else None

        if existing_text is not None:
            existing_sources = _parse_sources_from_note(existing_text)
            if source_stem in existing_sources:
                continue

        note_text = build_entity_note(
            existing_text=existing_text,
            slug=slug,
            title=title,
            entity_type=entity_type,
            source_stem=source_stem,
            context=context,
            generation_method=generation_method,
            today=today,
        )
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(note_text, encoding="utf-8")
        entities_written.append(note_path)
        _update_registry_entry(
            entity_registry, "entities", slug, title, source_stem, today,
            extra={"entity_type": entity_type},
        )

    all_written = concepts_written + entities_written
    if all_written:
        save_registry(concept_registry, concept_registry_path)
        save_registry(entity_registry, entity_registry_path)
        commit_pipeline_stage(
            message=f"concepts: {source_stem} ({len(concepts_written)} concepts, {len(entities_written)} entities)",
            paths=all_written + [concept_registry_path, entity_registry_path],
            no_commit=no_commit,
            root=root,
        )

    return {"concepts_written": concepts_written, "entities_written": entities_written}


def extract_for_source(
    item: dict,
    source_summary_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    root: Path = ROOT,
    no_commit: bool = False,
) -> dict:
    """Thin wrapper used by pipeline_run.py and synthesize.py."""
    text = source_summary_path.read_text(encoding="utf-8", errors="replace")
    fm, _ = _split_frontmatter(text)
    if not _yaml_bool(fm.get("approved", False)):
        return {"concepts_written": [], "entities_written": [], "skipped": "not approved"}
    _, body = _split_frontmatter(text)
    return extract_concepts_and_entities(
        body,
        source_summary_path.stem,
        model=model,
        root=root,
        no_commit=no_commit,
    )


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_extract_one(
    source: str, *, model: str, root: Path, dry_run: bool, no_commit: bool
) -> int:
    summaries_dir = root / "compiled" / "source_summaries"
    candidates = [
        summaries_dir / source,
        summaries_dir / f"{source}.md",
    ]
    path = next((c for c in candidates if c.exists()), None)
    if path is None:
        print(f"Error: source summary not found for '{source}'", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _split_frontmatter(text)
    if not _yaml_bool(fm.get("approved", False)):
        print(f"Skipping '{source}' — not approved.")
        return 0

    result = extract_concepts_and_entities(
        body, path.stem, model=model, root=root, dry_run=dry_run, no_commit=no_commit
    )
    if dry_run:
        extraction = result.get("extraction", {})
        print(f"[dry-run] {source}")
        print(f"  concepts : {[c.get('slug') for c in extraction.get('concepts', [])]}")
        print(f"  entities : {[e.get('slug') for e in extraction.get('entities', [])]}")
    else:
        nc = len(result.get("concepts_written", []))
        ne = len(result.get("entities_written", []))
        print(f"{source}: {nc} concept(s), {ne} entity/entities written")
    return 0


def _all_approved_summaries(root: Path) -> list[Path]:
    summaries_dir = root / "compiled" / "source_summaries"
    if not summaries_dir.exists():
        return []
    results = []
    for path in sorted(summaries_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = _split_frontmatter(text)
        if _yaml_bool(fm.get("approved", False)):
            results.append(path)
    return results


def _already_extracted(source_stem: str, root: Path) -> bool:
    """Return True if this source_stem appears in any concept or entity registry entry."""
    for reg_path, key in [
        (root / "metadata" / "concept-registry.json", "concepts"),
        (root / "metadata" / "entity-registry.json", "entities"),
    ]:
        reg = load_registry(reg_path)
        for entry in reg.get(key, []):
            if source_stem in entry.get("sources", []):
                return True
    return False


def cmd_extract_all(
    *, model: str, root: Path, dry_run: bool, no_commit: bool
) -> int:
    paths = _all_approved_summaries(root)
    if not paths:
        print("No approved source summaries found.")
        return 0

    processed = 0
    for path in paths:
        if not dry_run and _already_extracted(path.stem, root):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        _, body = _split_frontmatter(text)
        result = extract_concepts_and_entities(
            body, path.stem, model=model, root=root, dry_run=dry_run, no_commit=no_commit
        )
        if dry_run:
            extraction = result.get("extraction", {})
            nc = len(extraction.get("concepts", []))
            ne = len(extraction.get("entities", []))
            print(f"[dry-run] {path.stem}: {nc} concept(s), {ne} entity/entities")
        else:
            nc = len(result.get("concepts_written", []))
            ne = len(result.get("entities_written", []))
            print(f"{path.stem}: {nc} concept(s), {ne} entity/entities written")
        processed += 1

    if not dry_run:
        print(f"\nDone: {processed} source(s) processed.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract concepts and entities from approved source summaries."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", metavar="SLUG", help="Source summary stem to process.")
    group.add_argument("--all", action="store_true", help="Process all approved source summaries.")
    parser.add_argument("--dry-run", action="store_true", help="Print extraction without writing files.")
    parser.add_argument("--no-commit", action="store_true", dest="no_commit", help="Skip git auto-commit.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model. Default: {DEFAULT_MODEL}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.all:
        return cmd_extract_all(model=args.model, root=ROOT, dry_run=args.dry_run, no_commit=args.no_commit)
    return cmd_extract_one(args.source, model=args.model, root=ROOT, dry_run=args.dry_run, no_commit=args.no_commit)


if __name__ == "__main__":
    sys.exit(main())

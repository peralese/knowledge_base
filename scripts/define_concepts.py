"""define_concepts.py — 2A-2 Concept Definitions

Identifies stub concept notes and writes 2–4 sentence definitions grounded
in approved source content that mentions each concept.

Quality controls:
  - Skips concepts with fewer than 2 source excerpts found
  - Skips if Ollama returns fewer than 1 or more than 8 sentences
  - Preserves all existing frontmatter exactly; only adds generated fields
  - Commits in batches of 25 notes

Usage:
    python3 scripts/define_concepts.py                   # process all stubs
    python3 scripts/define_concepts.py --dry-run         # preview, no file changes
    python3 scripts/define_concepts.py --concept "name"  # single concept by name/slug
    python3 scripts/define_concepts.py --limit 10        # process N stubs (testing)
    python3 scripts/define_concepts.py --no-commit       # skip git commit
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"
BATCH_COMMIT_SIZE = 25
MIN_SOURCE_EXCERPTS = 2
MIN_SENTENCES = 1
MAX_SENTENCES = 8
EXCERPT_CONTEXT_CHARS = 500

sys.path.insert(0, str(Path(__file__).parent))
from git_ops import commit_pipeline_stage  # noqa: E402
from graph_health import is_stub, _strip_frontmatter  # noqa: E402
from llm_driver import _check_model_available, call_ollama  # noqa: E402


# ---------------------------------------------------------------------------
# Frontmatter manipulation
# ---------------------------------------------------------------------------

def _split_frontmatter_raw(text: str) -> tuple[str, str]:
    """Return (frontmatter_block_with_delimiters, body). If no frontmatter, ('', text)."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return "", normalized
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return "", normalized
    fm = normalized[: end + 5]  # includes trailing \n---\n
    body = normalized[end + 5:]
    return fm, body


def _inject_frontmatter_fields(text: str, fields: dict) -> str:
    """Add key: value lines to an existing frontmatter block (before closing ---)."""
    fm, body = _split_frontmatter_raw(text)
    if not fm:
        return text
    # Insert before the closing ---
    closing = "\n---\n"
    insert_pos = fm.rfind(closing)
    if insert_pos == -1:
        return text
    additions: list[str] = []
    for key, value in fields.items():
        if isinstance(value, list):
            if value:
                additions.append(f"{key}:")
                for item in value:
                    additions.append(f"  - {item}")
        elif isinstance(value, str) and value.strip():
            additions.append(f'{key}: "{value.strip()}"')
    if not additions:
        return text
    new_fm = fm[:insert_pos] + "\n" + "\n".join(additions) + closing
    return new_fm + body


# ---------------------------------------------------------------------------
# Source search
# ---------------------------------------------------------------------------

def _whole_word_pattern(name: str) -> re.Pattern:
    escaped = re.escape(name)
    return re.compile(r"(?<!\w)" + escaped + r"(?!\w)", re.IGNORECASE)


def _find_source_excerpts(
    concept_name: str,
    sources: dict[str, str],  # stem → content
    max_excerpts: int = 5,
    context_chars: int = EXCERPT_CONTEXT_CHARS,
) -> list[tuple[str, str]]:
    """Search source texts for the concept name; return (stem, excerpt) pairs.

    Searches for both the display name (spaces) and slug form (hyphens) so
    that a slug like 'zero-trust' matches both 'zero trust' and 'zero-trust'
    in source text.
    """
    # Build patterns for display name and hyphenated slug form
    slug_form = concept_name.replace(" ", "-")
    patterns = [_whole_word_pattern(concept_name)]
    if slug_form != concept_name:
        patterns.append(_whole_word_pattern(slug_form))

    excerpts: list[tuple[str, str]] = []
    for stem, text in sources.items():
        body = _strip_frontmatter(text)
        best_match = None
        for pattern in patterns:
            m = pattern.search(body)
            if m:
                best_match = m
                break
        if best_match is None:
            continue
        start = max(0, best_match.start() - context_chars // 2)
        end = min(len(body), best_match.end() + context_chars // 2)
        snippet = body[start:end].strip()
        excerpts.append((stem, snippet))
        if len(excerpts) >= max_excerpts:
            break
    return excerpts


def _load_approved_sources(root: Path) -> dict[str, str]:
    """Return {stem: content} for approved source summaries and raw articles."""
    sources: dict[str, str] = {}
    for directory in [
        root / "compiled" / "source_summaries",
        root / "raw" / "articles",
        root / "raw" / "notes",
    ]:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            # For source summaries, require approved; for raw, include all
            if "source_summaries" in str(directory):
                fm_block = text[:text.find("\n---\n", 4) + 5] if "\n---\n" in text else ""
                if "approved: true" not in fm_block and "approved:true" not in fm_block:
                    continue
            sources[path.stem] = text
    return sources


# ---------------------------------------------------------------------------
# Sentence counting
# ---------------------------------------------------------------------------

def _count_sentences(text: str) -> int:
    """Rough sentence count — splits on ., !, ? followed by whitespace or end."""
    stripped = text.strip()
    if not stripped:
        return 0
    sentences = re.split(r"(?<=[.!?])\s+", stripped)
    return len([s for s in sentences if s.strip()])


# ---------------------------------------------------------------------------
# Ollama prompt
# ---------------------------------------------------------------------------

def _build_definition_prompt(concept_name: str, excerpts: list[tuple[str, str]]) -> str:
    context_block = ""
    for stem, excerpt in excerpts:
        context_block += f"\n### From {stem}\n\n{excerpt}\n"
    return (
        f'Write a 2–4 sentence definition of "{concept_name}" '
        "grounded in the following source excerpts from an AI/ML knowledge base. "
        "Be specific, technical, and concise. "
        "Do not reference the sources by name — write as if explaining the concept directly. "
        "Output only the definition text, no headings or bullet points.\n\n"
        f"## Source Excerpts\n{context_block}\n\n"
        "## Definition\n\n"
    )


# ---------------------------------------------------------------------------
# Note writing
# ---------------------------------------------------------------------------

def _write_definition(path: Path, definition: str, source_stems: list[str]) -> None:
    """Write definition into the concept note body, injecting frontmatter fields."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, _ = _split_frontmatter_raw(text)

    new_fields: dict = {
        "generated_by": "ollama-concept-definition",
        "definition_sources": source_stems,
    }
    updated_text = _inject_frontmatter_fields(text, new_fields)

    # Replace or append body with definition
    updated_fm, _ = _split_frontmatter_raw(updated_text)
    body_section = f"\n{definition.strip()}\n\n## Mentioned In\n\n## Related Concepts\n"
    final = updated_fm + body_section

    path.write_text(final, encoding="utf-8")


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def _slug_to_name(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ")


def process_stubs(
    root: Path,
    model: str,
    dry_run: bool,
    concept_filter: str | None,
    limit: int | None,
    no_commit: bool,
) -> int:
    concepts_dir = root / "compiled" / "concepts"
    if not concepts_dir.exists():
        print("No compiled/concepts/ directory found — run concept_aggregator.py first.")
        return 0

    # Collect stubs
    all_stubs: list[Path] = []
    for path in sorted(concepts_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if is_stub(text):
            all_stubs.append(path)

    if concept_filter:
        slug = concept_filter.strip().lower().replace(" ", "-")
        all_stubs = [p for p in all_stubs if p.stem == slug or p.stem == concept_filter]
        if not all_stubs:
            # Try by display name match
            all_stubs = [
                p for p in (concepts_dir.glob("*.md"))
                if _slug_to_name(p.stem).lower() == concept_filter.lower()
            ]
        if not all_stubs:
            print(f"No stub concept found matching: {concept_filter!r}", file=sys.stderr)
            return 1

    if limit is not None:
        all_stubs = all_stubs[:limit]

    total = len(all_stubs)
    print(f"Stubs to process: {total}")

    if total == 0:
        print("No stubs found.")
        return 0

    # Load approved sources once
    sources = _load_approved_sources(root)
    print(f"Approved sources loaded: {len(sources)}")

    if not dry_run:
        try:
            _check_model_available(model)
        except (ConnectionError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    processed = 0
    skipped_few_sources = 0
    skipped_bad_output = 0
    committed_paths: list[Path] = []

    for i, path in enumerate(all_stubs, 1):
        concept_name = _slug_to_name(path.stem)
        excerpts = _find_source_excerpts(concept_name, sources)

        if dry_run:
            print(f"\n[{i}/{total}] {concept_name}")
            print(f"  Source excerpts found: {len(excerpts)}")
            if len(excerpts) < MIN_SOURCE_EXCERPTS:
                print(f"  SKIP — fewer than {MIN_SOURCE_EXCERPTS} excerpts")
            elif excerpts:
                preview = excerpts[0][1][:200].replace("\n", " ")
                print(f"  First excerpt ({excerpts[0][0]}): {preview}…")
            continue

        if len(excerpts) < MIN_SOURCE_EXCERPTS:
            print(f"[{i}/{total}] SKIP {concept_name!r} — only {len(excerpts)} source excerpt(s)")
            skipped_few_sources += 1
            continue

        print(f"[{i}/{total}] Defining: {concept_name!r} ({len(excerpts)} excerpts) …")
        prompt = _build_definition_prompt(concept_name, excerpts)

        try:
            raw_response = call_ollama(prompt, model)
        except URLError as exc:
            print(f"  ERROR: Ollama request failed: {exc}", file=sys.stderr)
            skipped_bad_output += 1
            continue

        definition = raw_response.strip()
        sentence_count = _count_sentences(definition)

        if sentence_count < MIN_SENTENCES or sentence_count > MAX_SENTENCES:
            print(
                f"  SKIP — response has {sentence_count} sentences "
                f"(expected {MIN_SENTENCES}–{MAX_SENTENCES})"
            )
            skipped_bad_output += 1
            continue

        source_stems = [stem for stem, _ in excerpts]
        _write_definition(path, definition, source_stems)
        committed_paths.append(path)
        processed += 1

        # Batch commit
        if len(committed_paths) >= BATCH_COMMIT_SIZE:
            _do_commit(committed_paths, processed, total, no_commit, root)
            committed_paths = []

    # Commit any remaining
    if committed_paths and not dry_run:
        _do_commit(committed_paths, processed, total, no_commit, root)

    if not dry_run:
        _print_summary(processed, total, skipped_few_sources, skipped_bad_output, root)

    return 0


def _do_commit(paths: list[Path], processed: int, total: int, no_commit: bool, root: Path) -> None:
    batch_num = (processed - 1) // BATCH_COMMIT_SIZE + 1
    msg = f"feat(concepts): define concept batch [2A-2] ({processed}/{total})"
    try:
        committed = commit_pipeline_stage(msg, paths, no_commit=no_commit, root=root)
        if committed:
            print(f"  Committed batch {batch_num} ({len(paths)} notes)")
    except RuntimeError as exc:
        print(f"  Warning: git commit failed: {exc}", file=sys.stderr)


def _print_summary(processed: int, total: int, skipped_few: int, skipped_bad: int, root: Path) -> None:
    print("\n" + "=" * 50)
    print(f"Processed : {processed}/{total}")
    print(f"Skipped (< {MIN_SOURCE_EXCERPTS} excerpts) : {skipped_few}")
    print(f"Skipped (bad output)           : {skipped_bad}")

    # Run graph_health and log new stub ratio
    try:
        from graph_health import compute_metrics  # noqa: PLC0415
        m = compute_metrics(root)
        ratio = m["stub_ratio_pct"]
        ratio_str = f"{ratio:.1f}%" if ratio is not None else "N/A"
        print(f"Stub ratio after run           : {ratio_str}")
    except Exception as exc:
        print(f"(Could not compute stub ratio: {exc})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2A-2 Concept Definitions: fill stub concept notes using Ollama."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be written; no file changes.",
    )
    parser.add_argument(
        "--concept",
        metavar="NAME",
        help="Process a single concept by name or slug.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process at most N stubs (useful for testing).",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Skip git auto-commits.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model to use. Default: {DEFAULT_MODEL}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return process_stubs(
        root=ROOT,
        model=args.model,
        dry_run=args.dry_run,
        concept_filter=args.concept,
        limit=args.limit,
        no_commit=args.no_commit,
    )


if __name__ == "__main__":
    sys.exit(main())

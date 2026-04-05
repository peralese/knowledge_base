from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CATEGORY_DESTINATIONS = {
    "source_summary": Path("compiled/source_summaries"),
    "concept": Path("compiled/concepts"),
    "topic": Path("compiled/topics"),
}

OUTPUT_DESTINATIONS = {
    "compiled": Path("compiled/topics"),
    "answer": Path("outputs/answers"),
    "report": Path("outputs/reports"),
}


@dataclass
class PromptPackMetadata:
    prompt_pack_path: Path
    requested_title: str
    note_category: str
    source_notes: list[str]


@dataclass
class ApplySynthesisRequest:
    prompt_pack: Path
    synthesized_file: Path | None = None
    text: str = ""
    output_type: str = "compiled"
    title_override: str = ""
    adapter: str = ""
    force: bool = False
    root: Path = ROOT


def slugify_title(title: str) -> str:
    """Convert a title into a lowercase, filesystem-safe slug."""
    slug = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled-note"


def normalize_text(content: str) -> str:
    """Normalize line endings while preserving the supplied markdown body."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def escape_yaml_string(value: str) -> str:
    """Escape a string for double-quoted YAML values."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def format_yaml_list(values: list[str]) -> str:
    """Render a YAML list in a stable multiline format."""
    if not values:
        return "[]"
    rendered = "\n".join(f'  - "{escape_yaml_string(value)}"' for value in values)
    return f"\n{rendered}"


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split markdown text into frontmatter and body."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return "", normalized.strip()

    parts = normalized.split("\n---\n", 1)
    if len(parts) != 2:
        return "", normalized.strip()

    frontmatter = parts[0][4:]
    body = parts[1].strip()
    return frontmatter.strip(), body


def parse_scalar(value: str) -> object:
    """Parse a simple YAML scalar used in this repository."""
    cleaned = value.strip()
    if not cleaned:
        return ""
    if cleaned == "[]":
        return []
    if cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return cleaned


def parse_frontmatter(frontmatter_text: str) -> dict[str, object]:
    """Parse the limited YAML frontmatter structure used by this repository."""
    if not frontmatter_text:
        return {}

    metadata: dict[str, object] = {}
    current_list_key: str | None = None

    for raw_line in frontmatter_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("- ") and current_list_key:
            value = stripped[2:].strip()
            parsed_value = parse_scalar(value)
            metadata.setdefault(current_list_key, [])
            assert isinstance(metadata[current_list_key], list)
            metadata[current_list_key].append(str(parsed_value))
            continue

        if ":" not in line:
            current_list_key = None
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "":
            metadata[key] = []
            current_list_key = key
            continue

        metadata[key] = parse_scalar(value)
        current_list_key = None

    return metadata


def read_synthesized_content(input_file: Path | None, text: str | None) -> str:
    """Read synthesized markdown from a file or direct CLI text."""
    if input_file and text:
        raise ValueError("Provide either --synthesized-file or --text, not both.")
    if not input_file and not text:
        raise ValueError("Provide one of --synthesized-file or --text.")

    if input_file:
        if not input_file.exists():
            raise FileNotFoundError(f"Synthesized file not found: {input_file}")
        if not input_file.is_file():
            raise ValueError(f"Synthesized path is not a file: {input_file}")
        return normalize_text(input_file.read_text(encoding="utf-8"))

    return normalize_text(text or "")


def dedupe_preserve_order(values: list[str]) -> list[str]:
    """Return unique values while preserving first-seen order."""
    seen: set[str] = set()
    ordered: list[str] = []

    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)

    return ordered


def extract_prompt_pack_metadata(prompt_pack_path: Path) -> PromptPackMetadata:
    """Extract the requested title, category, and source notes from a prompt-pack."""
    if not prompt_pack_path.exists():
        raise FileNotFoundError(f"Prompt-pack not found: {prompt_pack_path}")
    if not prompt_pack_path.is_file():
        raise ValueError(f"Prompt-pack path is not a file: {prompt_pack_path}")

    text = prompt_pack_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")

    title_match = re.search(r"^- Requested title:\s*(.+)$", text, re.MULTILINE)
    if not title_match:
        raise ValueError(f"Could not extract requested title from prompt-pack: {prompt_pack_path}")

    category_match = re.search(r"^- Note category:\s*(.+)$", text, re.MULTILINE)
    note_category = category_match.group(1).strip() if category_match else "topic"
    if note_category not in CATEGORY_DESTINATIONS:
        note_category = "topic"

    source_notes = dedupe_preserve_order(re.findall(r"\[\[([^\]]+)\]\]", text))

    return PromptPackMetadata(
        prompt_pack_path=prompt_pack_path,
        requested_title=title_match.group(1).strip(),
        note_category=note_category,
        source_notes=source_notes,
    )


def destination_dir_for_category(category: str) -> Path:
    """Map a compiled category to the correct compiled/ destination."""
    return CATEGORY_DESTINATIONS.get(category.strip().lower(), CATEGORY_DESTINATIONS["topic"])


def resolve_destination(
    root: Path,
    title: str,
    output_type: str,
    note_category: str,
) -> Path:
    """Resolve the final output path for the applied synthesis."""
    slug = slugify_title(title)

    if output_type == "compiled":
        return root / destination_dir_for_category(note_category) / f"{slug}.md"

    return root / OUTPUT_DESTINATIONS[output_type] / f"{slug}.md"


def extract_topics_from_body(body: str) -> list[str]:
    """Extract simple topic bullets from a synthesized body when present."""
    match = re.search(
        r"^# Related Concepts\s*(.*?)(?:^# |\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []

    topics = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            topics.append(stripped[2:].strip("` "))
    return dedupe_preserve_order(topics)


def extract_generated_query(body: str) -> str:
    """Extract the recorded prompt or query from an answer/report body when possible."""
    match = re.search(
        r"^# Prompt\s*(.*?)(?:^# |\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""

    query_lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    return " ".join(query_lines).strip()


def build_compiled_frontmatter(
    title: str,
    note_type: str,
    compiled_from: list[str],
    topics: list[str],
    tags: list[str],
    generation_method: str,
    today: str,
    existing_metadata: dict[str, object],
) -> str:
    """Build frontmatter for a compiled note while preserving existing values where reasonable."""
    resolved_title = str(existing_metadata.get("title", "")).strip() or title
    resolved_note_type = str(existing_metadata.get("note_type", "")).strip() or note_type
    resolved_compiled_from = compiled_from

    existing_topics = existing_metadata.get("topics", [])
    resolved_topics = list(existing_topics) if isinstance(existing_topics, list) and existing_topics else topics

    existing_tags = existing_metadata.get("tags", [])
    resolved_tags = list(existing_tags) if isinstance(existing_tags, list) and existing_tags else tags

    confidence = str(existing_metadata.get("confidence", "")).strip() or "medium"
    generation = str(existing_metadata.get("generation_method", "")).strip() or generation_method
    date_compiled = str(existing_metadata.get("date_compiled", "")).strip() or today

    return (
        "---\n"
        f'title: "{escape_yaml_string(resolved_title)}"\n'
        f'note_type: "{escape_yaml_string(resolved_note_type)}"\n'
        f"compiled_from: {format_yaml_list(resolved_compiled_from)}\n"
        f'date_compiled: "{escape_yaml_string(date_compiled)}"\n'
        f"topics: {format_yaml_list(resolved_topics)}\n"
        f"tags: {format_yaml_list(resolved_tags)}\n"
        f'confidence: "{escape_yaml_string(confidence)}"\n'
        f'generation_method: "{escape_yaml_string(generation)}"\n'
        "---"
    )


def build_output_frontmatter(
    title: str,
    output_type: str,
    generated_from_query: str,
    sources_used: list[str],
    compiled_notes_used: list[str],
    generation_method: str,
    today: str,
    existing_metadata: dict[str, object],
) -> str:
    """Build frontmatter for answer/report outputs while preserving existing values where reasonable."""
    resolved_title = str(existing_metadata.get("title", "")).strip() or title
    resolved_output_type = str(existing_metadata.get("output_type", "")).strip() or output_type
    resolved_query = str(existing_metadata.get("generated_from_query", "")).strip() or generated_from_query
    resolved_generated_on = str(existing_metadata.get("generated_on", "")).strip() or today
    resolved_generation = str(existing_metadata.get("generation_method", "")).strip() or generation_method

    existing_sources = existing_metadata.get("sources_used", [])
    resolved_sources = list(existing_sources) if isinstance(existing_sources, list) and existing_sources else sources_used

    existing_compiled_notes = existing_metadata.get("compiled_notes_used", [])
    if isinstance(existing_compiled_notes, list) and existing_compiled_notes:
        resolved_compiled_notes = list(existing_compiled_notes)
    else:
        resolved_compiled_notes = compiled_notes_used

    return (
        "---\n"
        f'title: "{escape_yaml_string(resolved_title)}"\n'
        f'output_type: "{escape_yaml_string(resolved_output_type)}"\n'
        f'generated_from_query: "{escape_yaml_string(resolved_query)}"\n'
        f'generated_on: "{escape_yaml_string(resolved_generated_on)}"\n'
        f"sources_used: {format_yaml_list(resolved_sources)}\n"
        f"compiled_notes_used: {format_yaml_list(resolved_compiled_notes)}\n"
        f'generation_method: "{escape_yaml_string(resolved_generation)}"\n'
        "---"
    )


def assemble_output_text(
    body: str,
    metadata: dict[str, object],
    prompt_pack_metadata: PromptPackMetadata,
    output_type: str,
    title: str,
    today: str,
) -> str:
    """Build the saved markdown text with required frontmatter and preserved body."""
    normalized_body = body.strip()
    source_notes = prompt_pack_metadata.source_notes

    if output_type == "compiled":
        topics = extract_topics_from_body(normalized_body)
        tags = dedupe_preserve_order(
            [prompt_pack_metadata.note_category]
            + topics
            + [name for name in source_notes if name]
        )
        frontmatter = build_compiled_frontmatter(
            title=title,
            note_type=prompt_pack_metadata.note_category,
            compiled_from=source_notes,
            topics=topics,
            tags=tags,
            generation_method="manual_paste",
            today=today,
            existing_metadata=metadata,
        )
    else:
        frontmatter = build_output_frontmatter(
            title=title,
            output_type=output_type,
            generated_from_query=extract_generated_query(normalized_body) or prompt_pack_metadata.requested_title,
            sources_used=source_notes,
            compiled_notes_used=[slugify_title(prompt_pack_metadata.requested_title)],
            generation_method="manual_paste",
            today=today,
            existing_metadata=metadata,
        )

    body_text = normalized_body or "[no synthesized body provided]"
    return f"{frontmatter}\n\n{body_text}\n"


def apply_synthesis(request: ApplySynthesisRequest) -> Path:
    """Apply synthesized markdown from a prompt-pack into a durable repository artifact."""
    if request.adapter:
        raise ValueError(
            f"--adapter is reserved for a future optional execution mode and is not implemented in Phase 4: {request.adapter}"
        )

    output_type = request.output_type.strip().lower() or "compiled"
    if output_type not in OUTPUT_DESTINATIONS:
        raise ValueError("Unsupported output type. Use compiled, answer, or report.")

    prompt_pack_path = request.root / request.prompt_pack if not request.prompt_pack.is_absolute() else request.prompt_pack
    prompt_pack_metadata = extract_prompt_pack_metadata(prompt_pack_path)
    synthesized_text = read_synthesized_content(
        request.root / request.synthesized_file if request.synthesized_file and not request.synthesized_file.is_absolute() else request.synthesized_file,
        request.text or None,
    )

    resolved_title = request.title_override.strip() or prompt_pack_metadata.requested_title
    destination = resolve_destination(
        root=request.root,
        title=resolved_title,
        output_type=output_type,
        note_category=prompt_pack_metadata.note_category,
    )

    if destination.exists() and not request.force:
        raise FileExistsError(f"Destination file already exists: {destination}. Use --force to overwrite.")

    existing_frontmatter, body = split_frontmatter(synthesized_text)
    metadata = parse_frontmatter(existing_frontmatter)
    output_text = assemble_output_text(
        body=body if existing_frontmatter else synthesized_text,
        metadata=metadata,
        prompt_pack_metadata=prompt_pack_metadata,
        output_type=output_type,
        title=resolved_title,
        today=date.today().isoformat(),
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output_text, encoding="utf-8")
    return destination


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Apply synthesized markdown from a prompt-pack into a compiled note or output artifact."
    )
    parser.add_argument("--prompt-pack", type=Path, required=True, help="Path to a Phase 3 prompt-pack markdown file.")
    parser.add_argument("--synthesized-file", type=Path, help="Path to synthesized markdown content.")
    parser.add_argument("--text", help="Synthesized markdown passed directly on the command line.")
    parser.add_argument(
        "--output-type",
        default="compiled",
        choices=["compiled", "answer", "report"],
        help="Artifact type to create. Defaults to compiled.",
    )
    parser.add_argument("--title", dest="title_override", default="", help="Optional title override.")
    parser.add_argument("--adapter", default="", help="Reserved placeholder for a future optional adapter mode.")
    parser.add_argument("--force", action="store_true", help="Overwrite the destination file if it already exists.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=args.prompt_pack,
                synthesized_file=args.synthesized_file,
                text=args.text or "",
                output_type=args.output_type,
                title_override=args.title_override,
                adapter=args.adapter,
                force=args.force,
            )
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created artifact: {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOPIC_REGISTRY_PATH = ROOT / "metadata" / "topic-registry.json"

CATEGORY_DESTINATIONS = {
    "source_summary": Path("compiled/source_summaries"),
    "concept": Path("compiled/concepts"),
    "topic": Path("compiled/topics"),
}


@dataclass
class SourceNote:
    path: Path
    title: str
    source_type: str
    origin: str
    summary: str
    topics: list[str]
    tags: list[str]
    metadata: dict[str, object]
    body: str

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def wikilink(self) -> str:
        return f"[[{self.stem}]]"


@dataclass
class CompileRequest:
    sources: list[Path]
    title: str
    category: str = "topic"
    mode: str = "scaffold"
    force: bool = False
    root: Path = ROOT


@dataclass
class CanonicalTopic:
    slug: str
    title: str
    aliases: list[str]


@dataclass
class CanonicalTopicResolution:
    slug: str
    title: str
    matched_registry: bool = False


def slugify_title(title: str) -> str:
    """Convert a title into a lowercase, filesystem-safe slug."""
    slug = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled-note"


def destination_dir_for_category(category: str) -> Path:
    """Map a compilation category to the correct compiled/ destination."""
    return CATEGORY_DESTINATIONS.get(category.strip().lower(), CATEGORY_DESTINATIONS["topic"])


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


def load_topic_registry(registry_path: Path = TOPIC_REGISTRY_PATH) -> list[CanonicalTopic]:
    """Load the optional topic registry."""
    if not registry_path.exists():
        return []

    with registry_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    topics = []
    for item in payload.get("topics", []):
        slug = str(item.get("slug", "")).strip()
        title = str(item.get("title", "")).strip()
        aliases = item.get("aliases", [])
        if not slug or not title:
            continue
        topics.append(
            CanonicalTopic(
                slug=slugify_title(slug),
                title=title,
                aliases=[str(alias).strip() for alias in aliases if str(alias).strip()],
            )
        )

    return topics


def resolve_canonical_topic(title: str, registry_path: Path = TOPIC_REGISTRY_PATH) -> CanonicalTopicResolution:
    """Resolve a canonical title and slug from the optional topic registry."""
    requested_title = " ".join(title.split()).strip()
    requested_slug = slugify_title(requested_title)
    registry = load_topic_registry(registry_path)

    for topic in registry:
        candidates = [topic.slug, slugify_title(topic.title)] + [slugify_title(alias) for alias in topic.aliases]
        if requested_slug in candidates:
            return CanonicalTopicResolution(
                slug=topic.slug,
                title=topic.title,
                matched_registry=True,
            )

    return CanonicalTopicResolution(
        slug=requested_slug,
        title=requested_title,
        matched_registry=False,
    )


def read_source_note(path: Path) -> SourceNote:
    """Read a raw markdown note and extract simple frontmatter plus body."""
    if not path.exists():
        raise FileNotFoundError(f"Source note not found: {path}")
    if not path.is_file():
        raise ValueError(f"Source path is not a file: {path}")

    text = path.read_text(encoding="utf-8")
    frontmatter_text, body = split_frontmatter(text)
    metadata = parse_frontmatter(frontmatter_text)

    topics = metadata.get("topics", [])
    tags = metadata.get("tags", [])

    return SourceNote(
        path=path,
        title=str(metadata.get("title", path.stem.replace("-", " ").title())),
        source_type=str(metadata.get("source_type", "")),
        origin=str(metadata.get("origin", "")),
        summary=str(metadata.get("summary", "")),
        topics=list(topics) if isinstance(topics, list) else [],
        tags=list(tags) if isinstance(tags, list) else [],
        metadata=metadata,
        body=body.strip(),
    )


def extract_excerpt(body: str, max_length: int = 280) -> str:
    """Extract a short, inspectable excerpt from the source body."""
    paragraphs = [paragraph.strip() for paragraph in body.split("\n\n") if paragraph.strip()]
    excerpt = paragraphs[0] if paragraphs else "[no source content available]"
    excerpt = re.sub(r"\s+", " ", excerpt).strip()

    if len(excerpt) <= max_length:
        return excerpt

    truncated = excerpt[: max_length - 3].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "..."


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


def build_compiled_frontmatter(
    title: str,
    category: str,
    compiled_from: list[str],
    topics: list[str],
    tags: list[str],
    generation_method: str,
    today: str,
) -> str:
    """Build YAML frontmatter for a compiled note."""
    return (
        "---\n"
        f'title: "{escape_yaml_string(title)}"\n'
        f'note_type: "{escape_yaml_string(category)}"\n'
        f"compiled_from: {format_yaml_list(compiled_from)}\n"
        f'date_compiled: "{today}"\n'
        f"topics: {format_yaml_list(topics)}\n"
        f"tags: {format_yaml_list(tags)}\n"
        'confidence: "medium"\n'
        f'generation_method: "{escape_yaml_string(generation_method)}"\n'
        "---"
    )


def build_scaffold_body(sources: list[SourceNote]) -> str:
    """Render the manual synthesis scaffold body."""
    source_links = "\n".join(f"- {source.wikilink}" for source in sources)
    highlight_sections = []

    for source in sources:
        highlight_sections.append(
            "\n".join(
                [
                    f"## {source.wikilink}",
                    f"- Title: {source.title}",
                    f"- Source Type: {source.source_type}",
                    f"- Origin: {source.origin}",
                    f"- Summary: {source.summary or '[add summary]'}",
                    f"- Key excerpt: {extract_excerpt(source.body)}",
                ]
            )
        )

    lineage_links = "\n".join(f"- {source.wikilink}" for source in sources)
    highlights_text = "\n\n".join(highlight_sections)

    return (
        "# Summary\n\n"
        "[placeholder text]\n\n"
        "# Key Insights\n\n"
        "- [placeholder]\n"
        "- [placeholder]\n\n"
        "# Related Concepts\n\n"
        "- \n\n"
        "# Source Notes\n\n"
        f"{source_links}\n\n"
        "# Source Highlights\n\n"
        f"{highlights_text}\n\n"
        "# Lineage\n\n"
        "This note was derived from:\n"
        f"{lineage_links}"
    )


def build_output_template(title: str, category: str, source_names: list[str]) -> str:
    """Render the desired compiled note shape inside a prompt-pack."""
    return (
        "---\n"
        f'title: "{escape_yaml_string(title)}"\n'
        f'note_type: "{escape_yaml_string(category)}"\n'
        f"compiled_from: {format_yaml_list(source_names)}\n"
        'date_compiled: "YYYY-MM-DD"\n'
        "topics: []\n"
        "tags: []\n"
        'confidence: "medium"\n'
        'generation_method: "prompt_pack"\n'
        "---\n\n"
        "# Summary\n\n"
        "[write a concise synthesis grounded in the sources]\n\n"
        "# Key Insights\n\n"
        "- [insight]\n"
        "- [insight]\n\n"
        "# Related Concepts\n\n"
        "- \n\n"
        "# Source Notes\n\n"
        + "\n".join(f"- [[{name}]]" for name in source_names)
        + "\n\n# Source Highlights\n\n"
        + "\n\n".join(
            f"## [[{name}]]\n- Title:\n- Source Type:\n- Origin:\n- Summary:\n- Key excerpt:"
            for name in source_names
        )
        + "\n\n# Lineage\n\nThis note was derived from:\n"
        + "\n".join(f"- [[{name}]]" for name in source_names)
    )


def build_prompt_pack(
    canonical: CanonicalTopicResolution,
    category: str,
    sources: list[SourceNote],
) -> str:
    """Create a markdown prompt-pack for later manual or local LLM use."""
    source_names = [source.stem for source in sources]
    sections = [
        "# Compilation Request",
        "",
        f"- Requested title: {canonical.title}",
        f"- Canonical title: {canonical.title}",
        f"- Canonical slug: {canonical.slug}",
        f"- Note category: {category}",
        "- Repository phase: Phase 3 compilation workflow",
        "- Required generation method value: prompt_pack",
        "",
        "# Canonical Identity Rules",
        "",
        f"- Use the exact canonical title provided: {canonical.title}",
        f"- Use the exact canonical topic slug provided: {canonical.slug}",
        "- Do not invent, modify, pluralize, misspell, or rename the topic.",
        "- Do not create alternative topic identities.",
        "",
        "# Instructions",
        "",
        "Use the provided source notes to synthesize one compiled markdown note in the exact repository format shown below.",
        "Preserve lineage explicitly by listing every source note in `compiled_from`, `# Source Notes`, and `# Lineage`.",
        "Do not invent unsupported claims. If the sources do not support a statement, omit it or mark it as uncertain in the note.",
        "Keep the result inspectable and grounded in the provided source material.",
        "Do not rewrite or mutate raw notes.",
        "",
        "# Desired Output Template",
        "",
        "```markdown",
        build_output_template(canonical.title, category, source_names),
        "```",
        "",
        "# Source Notes",
        "",
    ]

    for source in sources:
        sections.extend(
            [
                f"## {source.wikilink}",
                "",
                f"- Path: {source.path.as_posix()}",
                f"- Title: {source.title}",
                f"- Source Type: {source.source_type}",
                f"- Origin: {source.origin}",
                f"- Summary: {source.summary or '[none provided]'}",
                f"- Topics: {', '.join(source.topics) if source.topics else '[none]'}",
                f"- Tags: {', '.join(source.tags) if source.tags else '[none]'}",
                "",
                "### Body",
                "",
                "```markdown",
                source.body or "[no body content found]",
                "```",
                "",
            ]
        )

    return "\n".join(sections).rstrip() + "\n"


def build_scaffold_note(title: str, category: str, sources: list[SourceNote], today: str) -> str:
    """Assemble a compiled scaffold note."""
    compiled_from = [source.stem for source in sources]
    topics = dedupe_preserve_order([topic for source in sources for topic in source.topics])
    tags = dedupe_preserve_order([category] + [tag for source in sources for tag in source.tags])
    frontmatter = build_compiled_frontmatter(
        title=title,
        category=category,
        compiled_from=compiled_from,
        topics=topics,
        tags=tags,
        generation_method="manual_scaffold",
        today=today,
    )
    body = build_scaffold_body(sources)
    return f"{frontmatter}\n\n{body}\n"


def resolve_output_paths(request: CompileRequest, canonical: CanonicalTopicResolution) -> dict[str, Path]:
    """Compute destination files for the selected mode."""
    outputs: dict[str, Path] = {}

    if request.mode in {"scaffold", "both"}:
        outputs["scaffold"] = request.root / destination_dir_for_category(request.category) / f"{canonical.slug}.md"
    if request.mode in {"prompt-pack", "both"}:
        outputs["prompt-pack"] = request.root / "metadata" / "prompts" / f"compile-{canonical.slug}.md"

    return outputs


def ensure_writable_outputs(output_paths: dict[str, Path], force: bool) -> None:
    """Fail early when a destination already exists and overwrite is not allowed."""
    for output_path in output_paths.values():
        if output_path.exists() and not force:
            raise FileExistsError(
                f"Destination file already exists: {output_path}. Use --force to overwrite."
            )


def compile_notes(request: CompileRequest) -> dict[str, Path]:
    """Compile selected raw notes into a scaffold note and/or prompt-pack."""
    title = request.title.strip()
    if not title:
        raise ValueError("--title is required.")
    if not request.sources:
        raise ValueError("Provide at least one source note via --sources.")

    category = request.category.strip().lower() or "topic"
    if category not in CATEGORY_DESTINATIONS:
        raise ValueError(
            f"Unsupported category: {request.category}. Use source_summary, concept, or topic."
        )

    mode = request.mode.strip().lower() or "scaffold"
    if mode not in {"scaffold", "prompt-pack", "both"}:
        raise ValueError("Unsupported mode. Use scaffold, prompt-pack, or both.")

    source_paths = [request.root / source if not source.is_absolute() else source for source in request.sources]
    sources = [read_source_note(path) for path in source_paths]
    canonical = resolve_canonical_topic(title, request.root / "metadata" / "topic-registry.json")
    output_paths = resolve_output_paths(
        CompileRequest(
            sources=request.sources,
            title=canonical.title,
            category=category,
            mode=mode,
            force=request.force,
            root=request.root,
        ),
        canonical,
    )
    ensure_writable_outputs(output_paths, request.force)

    today = date.today().isoformat()
    created: dict[str, Path] = {}

    if "scaffold" in output_paths:
        scaffold_path = output_paths["scaffold"]
        scaffold_path.parent.mkdir(parents=True, exist_ok=True)
        scaffold_path.write_text(build_scaffold_note(canonical.title, category, sources, today), encoding="utf-8")
        created["scaffold"] = scaffold_path

    if "prompt-pack" in output_paths:
        prompt_path = output_paths["prompt-pack"]
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(build_prompt_pack(canonical, category, sources), encoding="utf-8")
        created["prompt-pack"] = prompt_path

    return created


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Compile selected raw markdown notes into a reusable compiled note scaffold or prompt-pack."
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        type=Path,
        required=True,
        help="One or more raw markdown note paths to compile.",
    )
    parser.add_argument("--title", required=True, help="Title for the compiled note.")
    parser.add_argument(
        "--mode",
        default="scaffold",
        choices=["scaffold", "prompt-pack", "both"],
        help="Compilation output mode. Defaults to scaffold.",
    )
    category_group = parser.add_mutually_exclusive_group()
    category_group.add_argument("--source-summary", dest="category", action="store_const", const="source_summary")
    category_group.add_argument("--concept", dest="category", action="store_const", const="concept")
    category_group.add_argument("--topic", dest="category", action="store_const", const="topic")
    parser.set_defaults(category="topic")
    parser.add_argument("--force", action="store_true", help="Overwrite output files if they already exist.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        created = compile_notes(
            CompileRequest(
                sources=args.sources,
                title=args.title,
                category=args.category,
                mode=args.mode,
                force=args.force,
            )
        )
    except (FileExistsError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for mode_name, output_path in created.items():
        print(f"Created {mode_name}: {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

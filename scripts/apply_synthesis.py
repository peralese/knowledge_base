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

OUTPUT_DESTINATIONS = {
    "compiled": Path("compiled/topics"),
    "answer": Path("outputs/answers"),
    "report": Path("outputs/reports"),
}

CITATION_ARTIFACT_PATTERN = re.compile(r":contentReference\[[^\]]*\]|\[oaicite:[^\]]*\]|\{index=\d+\}")
COMMAND_SUBSTITUTION_PATTERN = re.compile(r"`?\$\([^)\n]*\)`?")
GITHUB_BLOB_PATTERN = re.compile(r"\b[\w.-]+/[\w.-]+/blob/[\w./-]+\b")
WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_BLOCK_PATTERN = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)
SUSPICIOUS_FILE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".js",
    ".ts",
    ".sh",
    ".bash",
    ".zsh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".mdx",
}


@dataclass
class PromptPackMetadata:
    prompt_pack_path: Path
    requested_title: str
    canonical_title: str
    canonical_slug: str
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
    generation_method: str = "manual_paste"


@dataclass
class SanitizationResult:
    text: str
    removed_wrapping_fence: bool = False
    removed_duplicate_frontmatter: bool = False
    removed_citation_artifacts: bool = False


def slugify_title(title: str) -> str:
    """Convert a title into a lowercase, filesystem-safe slug."""
    slug = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled-note"


def normalize_line_endings(content: str) -> str:
    """Normalize line endings while preserving the supplied markdown body."""
    return content.replace("\r\n", "\n").replace("\r", "\n")


def normalize_text(content: str) -> str:
    """Normalize text and trim outer blank space."""
    return normalize_line_endings(content).strip()


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
    normalized = normalize_line_endings(text)
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


def load_topic_registry(registry_path: Path = TOPIC_REGISTRY_PATH) -> dict[str, dict[str, object]]:
    """Load the optional topic registry as a slug-indexed dictionary."""
    if not registry_path.exists():
        return {}

    with registry_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    indexed: dict[str, dict[str, object]] = {}
    for item in payload.get("topics", []):
        slug = slugify_title(str(item.get("slug", "")).strip())
        if slug:
            indexed[slug] = item
    return indexed


def sanitize_title_value(title: str) -> str:
    """Remove suspicious title characters before using the title in frontmatter."""
    sanitized = re.sub(r"[\[\]{}()<>:$`|]+", " ", title)
    sanitized = " ".join(sanitized.split())
    return sanitized.strip() or "Untitled Note"


def is_valid_wikilink_target(target: str) -> bool:
    """Allow only note-like wikilink targets that will not create garbage graph nodes."""
    cleaned = target.strip()
    if not cleaned:
        return False
    if len(cleaned) > 120:
        return False
    if any(fragment in cleaned.lower() for fragment in ("blob/", "$(", "://", ":contentreference", "[oaicite:")):
        return False
    if re.search(r"[<>{}|]", cleaned):
        return False
    if cleaned.startswith((".", "/", "~")):
        return False
    suffix = Path(cleaned).suffix.lower()
    if suffix in SUSPICIOUS_FILE_EXTENSIONS:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _./-]*[A-Za-z0-9]", cleaned))


def ensure_source_notes_section(body: str, source_notes: list[str]) -> tuple[str, bool]:
    """Guarantee a # Source Notes section with wikilinks for every source note exists in the body.

    If the section is missing it is appended. If it exists but is missing wikilinks for
    one or more source notes, those wikilinks are appended to the section. Returns the
    updated body and a flag indicating whether any changes were made.
    """
    if not source_notes:
        return body, False

    normalized = normalize_line_endings(body)
    required_links = {note: f"[[{note}]]" for note in source_notes}

    # Check which source notes already appear as wikilinks anywhere in the body.
    existing = set(extract_wikilinks(normalized))
    missing = [note for note in source_notes if note not in existing]
    if not missing:
        return body, False

    missing_links = "\n".join(f"- [[{note}]]" for note in missing)

    # If a # Source Notes section exists, append the missing links there.
    section_match = re.search(r"^# Source Notes\s*$", normalized, re.MULTILINE)
    if section_match:
        insert_pos = section_match.end()
        # Find where this section ends (next # heading or EOF).
        next_section = re.search(r"^# ", normalized[insert_pos:], re.MULTILINE)
        if next_section:
            insert_pos = insert_pos + next_section.start()
            updated = normalized[:insert_pos] + missing_links + "\n\n" + normalized[insert_pos:]
        else:
            updated = normalized.rstrip() + "\n" + missing_links + "\n"
        return updated, True

    # No section found — append one at the end.
    updated = normalized.rstrip() + "\n\n# Source Notes\n\n" + missing_links + "\n"
    return updated, True


def extract_valid_wikilinks(text: str) -> list[str]:
    """Extract valid wikilink targets from text while ignoring fenced code blocks."""
    valid_links: list[str] = []
    in_code_block = False

    for line in normalize_line_endings(text).splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        for match in WIKILINK_PATTERN.findall(line):
            if is_valid_wikilink_target(match):
                valid_links.append(match.strip())

    return dedupe_preserve_order(valid_links)


def extract_wikilinks(text: str) -> list[str]:
    """Extract all wikilink targets from text while ignoring fenced code blocks."""
    links: list[str] = []
    in_code_block = False

    for line in normalize_line_endings(text).splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        links.extend(match.strip() for match in WIKILINK_PATTERN.findall(line))

    return dedupe_preserve_order(links)


def resolve_registry_topic_target(target: str, registry: dict[str, dict[str, object]]) -> str | None:
    """Resolve a wikilink target to a canonical registry slug when possible."""
    target_slug = slugify_title(target)
    for slug, item in registry.items():
        candidates = [slug, slugify_title(str(item.get("title", "")))]
        candidates.extend(slugify_title(str(alias)) for alias in item.get("aliases", []))
        if target_slug in candidates:
            return slug
    return None


def strip_wrapping_markdown_fence(text: str) -> tuple[str, bool]:
    """Remove a whole-document ```markdown fence when the model wraps the entire note.

    Handles cases where the model appends trailing text (instructions, comments)
    after the closing fence — the closing fence is the last ``` line, not
    necessarily the last line of the document.
    """
    normalized = normalize_text(text)
    lines = normalized.splitlines()
    if not lines:
        return normalized, False
    if not re.fullmatch(r"```(?:markdown|md)?", lines[0].strip(), re.IGNORECASE):
        return normalized, False

    # Find the last line that is exactly a closing fence.
    closing_idx = None
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip() == "```":
            closing_idx = i
            break

    if closing_idx is None:
        # Truncated response — opening fence present but no closing fence found.
        # Strip the opening fence and use all remaining content rather than leaving
        # the body wrapped in a code block (which breaks Obsidian wikilinks).
        inner = "\n".join(lines[1:]).strip()
        return inner, True

    # Extract content between the opening and closing fence; discard anything after.
    inner = "\n".join(lines[1:closing_idx]).strip()
    return inner, True


def strip_duplicate_inner_frontmatter(text: str) -> tuple[str, bool]:
    """Remove echoed frontmatter blocks from LLM body content.

    By the time this is called, the real frontmatter has already been split off
    by split_frontmatter(), so any leading or inline ---...--- block is a duplicate.
    """
    normalized = normalize_line_endings(text)

    # Case 1: body starts with a frontmatter block (model echoed it at the top)
    if normalized.startswith("---\n"):
        match = re.match(r"^---\n.*?\n---\n?", normalized, re.DOTALL)
        if match:
            cleaned = normalized[match.end():].strip()
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
            return cleaned, True
        return normalized.strip(), False

    # Case 2: frontmatter block appears inline after some content
    match = re.search(r"\n---\n.*?\n---\n?", normalized, re.DOTALL)
    if match:
        cleaned = (normalized[: match.start()] + "\n" + normalized[match.end():]).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned, True

    return normalized.strip(), False


def strip_citation_artifacts(text: str) -> tuple[str, bool]:
    """Remove obvious model citation placeholders that should not persist in notes."""
    removed = False
    stripped_lines = []

    for line in normalize_line_endings(text).splitlines():
        cleaned = CITATION_ARTIFACT_PATTERN.sub("", line).rstrip()
        if cleaned != line.rstrip():
            removed = True
        stripped_lines.append(cleaned)

    return "\n".join(stripped_lines), removed


def neutralize_wikilinks_in_line(line: str) -> str:
    """Remove malformed or suspicious wikilinks while preserving valid note wikilinks."""
    def replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        if is_valid_wikilink_target(target):
            return f"[[{target}]]"
        return target

    return WIKILINK_PATTERN.sub(replace, line)


def is_symbol_heavy_line(line: str) -> bool:
    """Detect lines that are mostly punctuation and likely to be shell or regex noise."""
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) < 4:
        return False

    alnum_count = sum(character.isalnum() for character in stripped)
    symbol_count = sum(not character.isalnum() and not character.isspace() for character in stripped)
    return symbol_count > alnum_count and symbol_count >= 4


def is_suspicious_line(line: str) -> bool:
    """Detect lines that should not become durable knowledge artifacts."""
    stripped = line.strip()
    if not stripped:
        return False
    if COMMAND_SUBSTITUTION_PATTERN.search(stripped):
        return True
    if GITHUB_BLOB_PATTERN.search(stripped):
        return True
    if re.search(r'!\s*"\$[A-Za-z_][A-Za-z0-9_]*"\s*=~\s*\^', stripped):
        return True
    if stripped.startswith(("$/", "./", "../")):
        return True
    if stripped.startswith(("chmod ", "curl ", "wget ", "node ", "npm ", "bash ", "sh ")):
        return True
    if is_symbol_heavy_line(stripped):
        return True
    return False


def sanitize_suspicious_lines(text: str) -> str:
    """Drop or neutralize suspicious non-prose lines outside fenced code blocks."""
    sanitized_lines: list[str] = []
    in_code_block = False

    for raw_line in normalize_line_endings(text).splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            sanitized_lines.append(line)
            continue

        if in_code_block:
            sanitized_lines.append(line)
            continue

        line = neutralize_wikilinks_in_line(line)
        line = COMMAND_SUBSTITUTION_PATTERN.sub("", line)
        line = GITHUB_BLOB_PATTERN.sub("", line).rstrip()

        if is_suspicious_line(line):
            continue

        if re.search(r"\[\[[^\]]+\]\]", line):
            valid_links = extract_valid_wikilinks(line)
            if not valid_links:
                line = WIKILINK_PATTERN.sub("", line).strip()

        if line.strip():
            sanitized_lines.append(line.rstrip())
        else:
            sanitized_lines.append("")

    sanitized_text = "\n".join(sanitized_lines)
    sanitized_text = re.sub(r"\n{3,}", "\n\n", sanitized_text)
    return sanitized_text.strip()


def sanitize_markdown_body(body: str) -> SanitizationResult:
    """Apply conservative sanitization to synthesized markdown before writing it to disk."""
    working = normalize_text(body)
    working, removed_wrapping_fence = strip_wrapping_markdown_fence(working)
    working, removed_duplicate_frontmatter = strip_duplicate_inner_frontmatter(working)
    working, removed_citations = strip_citation_artifacts(working)
    working = sanitize_suspicious_lines(working)
    return SanitizationResult(
        text=working.strip(),
        removed_wrapping_fence=removed_wrapping_fence,
        removed_duplicate_frontmatter=removed_duplicate_frontmatter,
        removed_citation_artifacts=removed_citations,
    )


def build_wikilink_index(root: Path) -> dict[str, list[str]]:
    """Build a slug-indexed map of valid wikilink targets in the vault, excluding archives."""
    search_dirs = [
        root / "raw" / "articles",
        root / "raw" / "notes",
        root / "raw" / "pdfs",
        root / "compiled" / "source_summaries",
        root / "compiled" / "concepts",
        root / "compiled" / "topics",
    ]
    index: dict[str, list[str]] = {}

    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            stem = path.stem
            index.setdefault(slugify_title(stem), [])
            if stem not in index[slugify_title(stem)]:
                index[slugify_title(stem)].append(stem)

    return index


def patch_source_wikilinks(text: str, source_notes: list[str], registry: dict[str, dict[str, object]]) -> str:
    """Patch wikilinks that drift from prompt-pack source note names or canonical topics."""
    source_map = {slugify_title(source_name): source_name for source_name in source_notes}
    sanitized_lines: list[str] = []
    in_code_block = False

    for raw_line in normalize_line_endings(text).splitlines():
        line = raw_line
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            sanitized_lines.append(line)
            continue
        if in_code_block:
            sanitized_lines.append(line)
            continue

        def replace(match: re.Match[str]) -> str:
            target = match.group(1).strip()
            source_target = source_map.get(slugify_title(target))
            if source_target:
                return f"[[{source_target}]]"

            canonical_target = resolve_registry_topic_target(target, registry)
            if canonical_target:
                return f"[[{canonical_target}]]"

            return f"[[{target}]]"

        sanitized_lines.append(WIKILINK_PATTERN.sub(replace, line))

    return "\n".join(sanitized_lines).strip()


def validate_wikilinks(
    text: str,
    root: Path,
    source_notes: list[str],
    registry: dict[str, dict[str, object]],
    current_output_stem: str,
) -> None:
    """Validate wikilinks in a compiled note body and fail on unresolved or ambiguous targets."""
    index = build_wikilink_index(root)
    if current_output_stem:
        index.setdefault(slugify_title(current_output_stem), [])
        if current_output_stem not in index[slugify_title(current_output_stem)]:
            index[slugify_title(current_output_stem)].append(current_output_stem)

    unresolved: list[str] = []

    for target in extract_wikilinks(text):
        patched_target = target
        source_match = next((source for source in source_notes if slugify_title(source) == slugify_title(target)), None)
        if source_match:
            patched_target = source_match
        else:
            registry_target = resolve_registry_topic_target(target, registry)
            if registry_target:
                patched_target = registry_target

        matches = index.get(slugify_title(patched_target), [])
        if len(matches) != 1:
            unresolved.append(target)

    if unresolved:
        raise ValueError(f"Validation failed: unresolved wikilinks: {sorted(dedupe_preserve_order(unresolved))}")


def extract_prompt_pack_metadata(prompt_pack_path: Path) -> PromptPackMetadata:
    """Extract canonical metadata and source notes from a prompt-pack."""
    if not prompt_pack_path.exists():
        raise FileNotFoundError(f"Prompt-pack not found: {prompt_pack_path}")
    if not prompt_pack_path.is_file():
        raise ValueError(f"Prompt-pack path is not a file: {prompt_pack_path}")

    text = normalize_line_endings(prompt_pack_path.read_text(encoding="utf-8"))

    title_match = re.search(r"^- Requested title:\s*(.+)$", text, re.MULTILINE)
    if not title_match:
        raise ValueError(f"Could not extract requested title from prompt-pack: {prompt_pack_path}")

    canonical_title_match = re.search(r"^- Canonical title:\s*(.+)$", text, re.MULTILINE)
    canonical_slug_match = re.search(r"^- Canonical slug:\s*(.+)$", text, re.MULTILINE)
    category_match = re.search(r"^- Note category:\s*(.+)$", text, re.MULTILINE)

    requested_title = sanitize_title_value(title_match.group(1).strip())
    canonical_title = sanitize_title_value(canonical_title_match.group(1).strip()) if canonical_title_match else requested_title
    canonical_slug = slugify_title(canonical_slug_match.group(1).strip()) if canonical_slug_match else slugify_title(canonical_title)
    note_category = category_match.group(1).strip() if category_match else "topic"
    if note_category not in CATEGORY_DESTINATIONS:
        note_category = "topic"

    source_notes = extract_valid_wikilinks(text)

    return PromptPackMetadata(
        prompt_pack_path=prompt_pack_path,
        requested_title=requested_title,
        canonical_title=canonical_title,
        canonical_slug=canonical_slug,
        note_category=note_category,
        source_notes=source_notes,
    )


def destination_dir_for_category(category: str) -> Path:
    """Map a compiled category to the correct compiled/ destination."""
    return CATEGORY_DESTINATIONS.get(category.strip().lower(), CATEGORY_DESTINATIONS["topic"])


def resolve_destination(
    root: Path,
    canonical_slug: str,
    output_type: str,
    note_category: str,
) -> Path:
    """Resolve the final output path for the applied synthesis."""
    safe_slug = slugify_title(canonical_slug)

    if output_type == "compiled":
        return root / destination_dir_for_category(note_category) / f"{safe_slug}.md"

    return root / OUTPUT_DESTINATIONS[output_type] / f"{safe_slug}.md"


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
    resolved_title = title
    resolved_note_type = note_type
    resolved_compiled_from = compiled_from

    existing_topics = existing_metadata.get("topics", [])
    resolved_topics = list(existing_topics) if isinstance(existing_topics, list) and existing_topics else topics

    existing_tags = existing_metadata.get("tags", [])
    resolved_tags = list(existing_tags) if isinstance(existing_tags, list) and existing_tags else tags

    confidence = str(existing_metadata.get("confidence", "")).strip() or "medium"
    generation = generation_method
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
    resolved_title = title
    resolved_output_type = output_type
    resolved_query = str(existing_metadata.get("generated_from_query", "")).strip() or generated_from_query
    resolved_generated_on = str(existing_metadata.get("generated_on", "")).strip() or today
    resolved_generation = generation_method

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
    root: Path,
    generation_method: str = "manual_paste",
) -> tuple[str, SanitizationResult]:
    """Build the saved markdown text with required frontmatter and preserved body."""
    sanitization = sanitize_markdown_body(body)
    normalized_body = sanitization.text
    source_notes = prompt_pack_metadata.source_notes
    registry = load_topic_registry(root / "metadata" / "topic-registry.json")

    if output_type == "compiled":
        normalized_body = patch_source_wikilinks(normalized_body, source_notes, registry)
        normalized_body, injected = ensure_source_notes_section(normalized_body, source_notes)
        if injected:
            print("Injected missing source wikilinks into # Source Notes section")
        validate_wikilinks(
            normalized_body,
            root,
            source_notes,
            registry,
            current_output_stem=prompt_pack_metadata.canonical_slug,
        )
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
            generation_method=generation_method,
            today=today,
            existing_metadata=metadata,
        )
    else:
        frontmatter = build_output_frontmatter(
            title=title,
            output_type=output_type,
            generated_from_query=extract_generated_query(normalized_body) or prompt_pack_metadata.requested_title,
            sources_used=source_notes,
            compiled_notes_used=[prompt_pack_metadata.canonical_slug],
            generation_method=generation_method,
            today=today,
            existing_metadata=metadata,
        )

    body_text = normalized_body or "[no synthesized body provided]"
    return f"{frontmatter}\n\n{body_text}\n", sanitization


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

    requested_title = sanitize_title_value(request.title_override.strip()) if request.title_override.strip() else prompt_pack_metadata.canonical_title
    canonical_title = prompt_pack_metadata.canonical_title
    canonical_slug = prompt_pack_metadata.canonical_slug

    registry = load_topic_registry(request.root / "metadata" / "topic-registry.json")
    if canonical_slug in registry:
        registry_entry = registry[canonical_slug]
        canonical_title = sanitize_title_value(str(registry_entry.get("title", canonical_title)))
        canonical_slug = slugify_title(str(registry_entry.get("slug", canonical_slug)))

    destination = resolve_destination(
        root=request.root,
        canonical_slug=canonical_slug,
        output_type=output_type,
        note_category=prompt_pack_metadata.note_category,
    )

    if destination.exists() and not request.force:
        raise FileExistsError(f"Destination file already exists: {destination}. Use --force to overwrite.")

    existing_frontmatter, body = split_frontmatter(synthesized_text)
    metadata = parse_frontmatter(existing_frontmatter)
    original_title = str(metadata.get("title", "")).strip()
    output_text, sanitization = assemble_output_text(
        body=body if existing_frontmatter else synthesized_text,
        metadata=metadata,
        prompt_pack_metadata=PromptPackMetadata(
            prompt_pack_path=prompt_pack_metadata.prompt_pack_path,
            requested_title=prompt_pack_metadata.requested_title,
            canonical_title=canonical_title,
            canonical_slug=canonical_slug,
            note_category=prompt_pack_metadata.note_category,
            source_notes=prompt_pack_metadata.source_notes,
        ),
        output_type=output_type,
        title=canonical_title if output_type == "compiled" else requested_title,
        today=date.today().isoformat(),
        root=request.root,
        generation_method=request.generation_method,
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output_text, encoding="utf-8")

    if original_title and sanitize_title_value(original_title) != canonical_title and output_type == "compiled":
        print(f"Patched title to canonical topic title: {canonical_title}")
    print(f"Enforced canonical slug: {canonical_slug}")
    if sanitization.removed_wrapping_fence:
        print("Removed wrapping markdown fence")
    if sanitization.removed_duplicate_frontmatter:
        print("Removed duplicate inner frontmatter")
    if sanitization.removed_citation_artifacts:
        print("Removed citation artifacts")

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
    except (FileExistsError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created artifact: {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

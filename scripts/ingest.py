from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "metadata" / "source-manifest.json"
ARCHIVE_DIR = Path("raw/archive")
DEFAULT_STATUS = "raw"
DEFAULT_LANGUAGE = "en"

DESTINATION_FOLDERS = {
    "article": Path("raw/articles"),
    "note": Path("raw/notes"),
    "pdf": Path("raw/pdfs"),
}


@dataclass
class IngestRequest:
    title: str
    source_type: str
    origin: str
    canonical_url: str = ""
    input_path: str = ""
    text: str = ""
    author: str = ""
    date_created: str = ""
    date_published: str = ""
    summary: str = ""
    license_name: str = ""
    language: str = DEFAULT_LANGUAGE
    status: str = DEFAULT_STATUS
    confidence: str = ""
    force: bool = False
    root: Path = ROOT


def slugify_title(title: str) -> str:
    """Convert a title into a lowercase, filesystem-safe slug."""
    slug = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled-note"


def destination_dir_for_source_type(source_type: str) -> Path:
    """Map a source type to the correct raw/ destination."""
    return DESTINATION_FOLDERS.get(source_type.strip().lower(), Path("raw/inbox"))


class _TextExtractor(HTMLParser):
    """Extract readable text from HTML, discarding scripts, styles, and markup."""

    _SKIP_TAGS = frozenset({"script", "style", "head", "noscript", "iframe", "svg", "template"})
    _BLOCK_TAGS = frozenset({
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "br", "tr", "blockquote", "article", "section",
        "header", "footer", "nav", "main", "figure", "figcaption",
    })

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS and not self._skip_depth:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BLOCK_TAGS and not self._skip_depth:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = html_module.unescape("".join(self._parts))
        lines = [line.rstrip() for line in raw.splitlines()]
        result: list[str] = []
        blank_run = 0
        for line in lines:
            if line.strip():
                blank_run = 0
                result.append(line)
            else:
                blank_run += 1
                if blank_run == 1:
                    result.append("")
        return "\n".join(result).strip()


def html_to_text(html_content: str) -> str:
    """Convert HTML to plain readable text using stdlib only."""
    extractor = _TextExtractor()
    extractor.feed(html_content)
    return extractor.get_text()


def normalize_text(content: str) -> str:
    """Keep content readable without attempting advanced conversion."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def load_manifest(manifest_path: Path) -> dict:
    """Load the manifest or return a minimal default structure."""
    if not manifest_path.exists():
        return {
            "manifest_version": "0.2.0",
            "last_updated": "",
            "description": "Source manifest for tracking ingested raw notes and preserving lineage.",
            "sources": [],
        }

    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    manifest.setdefault("manifest_version", "0.2.0")
    manifest.setdefault("last_updated", "")
    manifest.setdefault(
        "description",
        "Source manifest for tracking ingested raw notes and preserving lineage.",
    )
    manifest.setdefault("sources", [])
    return manifest


def save_manifest(manifest_path: Path, manifest: dict) -> None:
    """Write manifest JSON with stable formatting."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")


def generate_source_id(manifest: dict, today: date | None = None) -> str:
    """Generate a simple incrementing source ID for the current date."""
    today = today or date.today()
    prefix = f"SRC-{today.strftime('%Y%m%d')}-"
    max_counter = 0

    for entry in manifest.get("sources", []):
        source_id = str(entry.get("source_id", ""))
        if source_id.upper().startswith(prefix):
            suffix = source_id.split("-")[-1]
            if suffix.isdigit():
                max_counter = max(max_counter, int(suffix))

    return f"{prefix}{max_counter + 1:04d}"


def read_input_content(input_file: Path | None, text: str | None) -> tuple[str, str]:
    """Read content from a file or direct CLI text and return normalized content plus input path."""
    if input_file and text:
        raise ValueError("Provide either --input-file or --text, not both.")
    if not input_file and not text:
        raise ValueError("Provide one of --input-file or --text.")

    if input_file:
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        if not input_file.is_file():
            raise ValueError(f"Input path is not a file: {input_file}")
        raw = input_file.read_text(encoding="utf-8")
        if input_file.suffix.lower() == ".html":
            raw = html_to_text(raw)
        return normalize_text(raw), str(input_file)

    return normalize_text(text or ""), ""


def build_note_body(source_type: str, content: str, input_path: str) -> str:
    """Create the standardized markdown body for the ingested note."""
    if source_type.strip().lower() == "pdf":
        source_content = (
            "PDF parsing is not implemented in Phase 2.\n\n"
            f"Pending source path: {input_path or '[not provided]'}"
        )
    else:
        source_content = content or "[no content provided]"

    return (
        "# Overview\n\n"
        "Brief description of what this source is and why it matters.\n\n"
        "# Source Content\n\n"
        f"{source_content}\n\n"
        "# Key Points\n\n"
        "- \n\n"
        "# Notes\n\n"
        "# Lineage\n\n"
        "- Ingested via: scripts/ingest.py\n"
        "- Manifest entry:\n"
        f"- Source path: {input_path}\n"
        "- Canonical URL:\n"
    )


def format_yaml_list(values: list[str]) -> str:
    """Render a YAML list in a simple multiline format."""
    if not values:
        return "[]"
    rendered = "\n".join(f'  - "{value}"' for value in values)
    return f"\n{rendered}"


def escape_yaml_string(value: str) -> str:
    """Escape a string for double-quoted YAML values."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_frontmatter(
    request: IngestRequest,
    source_id: str,
    date_ingested: str,
) -> str:
    """Build YAML frontmatter for an ingested raw note."""
    return (
        "---\n"
        f'title: "{escape_yaml_string(request.title)}"\n'
        f'source_type: "{escape_yaml_string(request.source_type)}"\n'
        f'origin: "{escape_yaml_string(request.origin)}"\n'
        f'date_ingested: "{date_ingested}"\n'
        f'status: "{escape_yaml_string(request.status)}"\n'
        f"topics: {format_yaml_list([])}\n"
        f"tags: {format_yaml_list([])}\n"
        f'author: "{escape_yaml_string(request.author)}"\n'
        f'date_created: "{escape_yaml_string(request.date_created)}"\n'
        f'date_published: "{escape_yaml_string(request.date_published)}"\n'
        f'language: "{escape_yaml_string(request.language)}"\n'
        f'summary: "{escape_yaml_string(request.summary)}"\n'
        f'source_id: "{source_id}"\n'
        f'canonical_url: "{escape_yaml_string(request.canonical_url)}"\n'
        f"related_sources: {format_yaml_list([])}\n"
        f'confidence: "{escape_yaml_string(request.confidence)}"\n'
        f'license: "{escape_yaml_string(request.license_name)}"\n'
        "---"
    )


def update_lineage_section(note_text: str, manifest_entry_path: str, canonical_url: str) -> str:
    """Fill in the manifest path and canonical URL placeholders in the lineage section."""
    updated = note_text.replace("- Manifest entry:\n", f"- Manifest entry: {manifest_entry_path}\n")
    updated = updated.replace("- Canonical URL:\n", f"- Canonical URL: {canonical_url}\n")
    return updated


def build_note_text(
    request: IngestRequest,
    source_id: str,
    content: str,
    date_ingested: str,
    manifest_entry_path: str,
) -> str:
    """Assemble frontmatter and markdown body."""
    frontmatter = build_frontmatter(request, source_id, date_ingested)
    body = build_note_body(request.source_type, content, request.input_path)
    note = f"{frontmatter}\n\n{body}"
    return update_lineage_section(note, manifest_entry_path, request.canonical_url)


def build_manifest_entry(
    request: IngestRequest,
    source_id: str,
    output_path: Path,
    date_ingested: str,
    archive_path: Path | None = None,
) -> dict:
    """Create a manifest entry for the ingested note."""
    entry = {
        "source_id": source_id,
        "title": request.title,
        "filename": output_path.name,
        "path": str(output_path.relative_to(request.root)),
        "source_type": request.source_type,
        "origin": request.origin,
        "date_ingested": date_ingested,
        "canonical_url": request.canonical_url,
        "input_path": request.input_path,
        "status": request.status,
    }
    if archive_path is not None:
        entry["archive_path"] = str(archive_path.relative_to(request.root))
    return entry


def is_inbox_input(input_path: Path, root: Path) -> bool:
    """Return True when the input file came from raw/inbox/ inside the repository."""
    try:
        relative_path = input_path.resolve().relative_to((root / "raw" / "inbox").resolve())
    except ValueError:
        return False
    return not str(relative_path).startswith("..")


def build_archive_filename(input_path: Path, archived_at: datetime | None = None) -> str:
    """Build a timestamped archive filename that avoids note-name collisions in the vault."""
    archived_at = archived_at or datetime.now()
    timestamp = archived_at.strftime("%Y%m%d-%H%M%S")
    return f"{input_path.stem}--archived-{timestamp}{input_path.suffix}"


def archive_input_file(input_path: Path, root: Path, archived_at: datetime | None = None) -> Path:
    """Move an inbox file into raw/archive/ with a timestamped, collision-safe filename."""
    archive_dir = root / ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_at = archived_at or datetime.now()
    archive_name = build_archive_filename(input_path, archived_at)
    archive_path = archive_dir / archive_name
    suffix_counter = 2

    while archive_path.exists():
        archive_name = (
            f"{input_path.stem}--archived-{archived_at.strftime('%Y%m%d-%H%M%S')}-{suffix_counter}"
            f"{input_path.suffix}"
        )
        archive_path = archive_dir / archive_name
        suffix_counter += 1

    return input_path.replace(archive_path)


def upsert_manifest_entry(manifest: dict, entry: dict) -> tuple[dict, bool]:
    """Insert or update a manifest entry by output path."""
    sources = manifest.setdefault("sources", [])
    existing_index = next(
        (index for index, item in enumerate(sources) if item.get("path") == entry["path"]),
        None,
    )

    if existing_index is None:
        sources.append(entry)
        return manifest, False

    sources[existing_index] = {**sources[existing_index], **entry}
    return manifest, True


def ingest_source(request: IngestRequest) -> Path:
    """Ingest a source into a standardized raw markdown note and update the manifest."""
    title = request.title.strip()
    if not title:
        raise ValueError("--title is required.")

    input_file = Path(request.input_path) if request.input_path else None
    content, detected_input_path = read_input_content(
        input_file,
        request.text or None,
    )
    if detected_input_path:
        request.input_path = detected_input_path
        input_file = Path(detected_input_path)

    destination_dir = request.root / destination_dir_for_source_type(request.source_type)
    destination_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify_title(title)
    output_path = destination_dir / f"{slug}.md"

    if output_path.exists() and not request.force:
        counter = 2
        while output_path.exists():
            output_path = destination_dir / f"{slug}-{counter}.md"
            counter += 1

    manifest_path = request.root / "metadata" / "source-manifest.json"
    manifest = load_manifest(manifest_path)
    existing_entry = next(
        (entry for entry in manifest.get("sources", []) if entry.get("path") == str(output_path.relative_to(request.root))),
        None,
    )

    source_id = existing_entry.get("source_id") if existing_entry else generate_source_id(manifest)
    today = date.today().isoformat()
    manifest_entry_path = f"metadata/source-manifest.json::{source_id}"
    note_text = build_note_text(request, source_id, content, today, manifest_entry_path)

    output_path.write_text(note_text + "\n", encoding="utf-8")

    archive_path: Path | None = None
    if input_file and is_inbox_input(input_file, request.root):
        archive_path = archive_input_file(input_file, request.root)

    entry = build_manifest_entry(request, source_id, output_path, today, archive_path=archive_path)
    manifest, _ = upsert_manifest_entry(manifest, entry)
    manifest["last_updated"] = today
    manifest["manifest_version"] = "0.2.0"
    save_manifest(manifest_path, manifest)

    return output_path


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Normalize a source input into a raw markdown note and update the source manifest."
    )
    parser.add_argument("--input-file", type=Path, help="Path to a source text, markdown, or PDF file.")
    parser.add_argument("--text", help="Direct text to ingest.")
    parser.add_argument("--title", required=True, help="Title for the ingested note.")
    parser.add_argument("--source-type", required=True, help="Source type: article, note, pdf, or another label.")
    parser.add_argument("--origin", required=True, help="Origin label such as local-file, local-markdown, web, or manual-entry.")
    parser.add_argument("--canonical-url", default="", help="Canonical URL for web-derived sources.")
    parser.add_argument("--author", default="", help="Optional author name.")
    parser.add_argument("--date-created", default="", help="Optional original creation date.")
    parser.add_argument("--date-published", default="", help="Optional publication date.")
    parser.add_argument("--summary", default="", help="Optional short summary.")
    parser.add_argument("--license", dest="license_name", default="", help="Optional license string.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Language code. Defaults to en.")
    parser.add_argument("--status", default=DEFAULT_STATUS, help="Status value. Defaults to raw.")
    parser.add_argument("--confidence", default="", help="Optional confidence value.")
    parser.add_argument("--force", action="store_true", help="Overwrite the destination file if it already exists.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        request = IngestRequest(
            title=args.title,
            source_type=args.source_type,
            origin=args.origin,
            canonical_url=args.canonical_url,
            input_path=str(args.input_file) if args.input_file else "",
            text=args.text or "",
            author=args.author,
            date_created=args.date_created,
            date_published=args.date_published,
            summary=args.summary,
            license_name=args.license_name,
            language=args.language,
            status=args.status,
            confidence=args.confidence,
            force=args.force,
        )
        output_path = ingest_source(request)
    except (FileNotFoundError, FileExistsError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created note: {output_path.relative_to(ROOT)}")
    print(f"Updated manifest: {MANIFEST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

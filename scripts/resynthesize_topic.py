"""Re-synthesize topic notes from all linked approved source summaries."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"

sys.path.insert(0, str(Path(__file__).parent))
from git_ops import commit_pipeline_stage  # noqa: E402
from llm_driver import _check_model_available, call_ollama  # noqa: E402


class ResynthesisError(Exception):
    error_code = "resynthesis_failed"


class TopicNotFoundError(ResynthesisError):
    error_code = "topic_not_found"


class InsufficientSourcesError(ResynthesisError):
    error_code = "insufficient_sources"


class OllamaUnavailableError(ResynthesisError):
    error_code = "ollama_unavailable"


@dataclass
class ResynthesisResult:
    topic_slug: str
    topic_path: Path
    synthesis_version: int
    sources_used: int
    committed: bool
    dry_run: bool = False
    preview: str = ""


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized.strip()
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return {}, normalized.strip()

    fm_text = normalized[4:end]
    body = normalized[end + 5:].strip()
    data: dict[str, object] = {}
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
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", stripped)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
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


def _wiki_targets(text: str) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", text):
        target = match.group(1).strip()
        if target and target not in seen:
            targets.append(target)
            seen.add(target)
    return targets


def _source_path(target: str, root: Path) -> Path | None:
    cleaned = target.strip()
    candidates = [
        root / cleaned,
        root / "compiled" / "source_summaries" / cleaned,
        root / "compiled" / "source_summaries" / f"{cleaned}.md",
    ]
    if cleaned.endswith(".md"):
        candidates.append(root / "compiled" / "source_summaries" / Path(cleaned).name)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _linked_source_paths(topic_text: str, root: Path) -> list[Path]:
    paths: list[Path] = []
    fm, _ = _split_frontmatter(topic_text)
    for target in _wiki_targets(topic_text):
        path = _source_path(target, root)
        if path and path not in paths:
            paths.append(path)

    compiled_from = fm.get("compiled_from", [])
    if isinstance(compiled_from, str):
        compiled_from = [compiled_from]
    if isinstance(compiled_from, list):
        for stem in compiled_from:
            path = _source_path(str(stem), root)
            if path and path not in paths:
                paths.append(path)
    return paths


def _approved_sources(paths: list[Path]) -> list[Path]:
    approved: list[Path] = []
    for path in paths:
        fm, _ = _split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if _yaml_bool(fm.get("approved", False)):
            approved.append(path)
    return approved


def _title_for_slug(slug: str, root: Path) -> str:
    registry_path = root / "metadata" / "topic-registry.json"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for topic in registry.get("topics", []):
                if topic.get("slug") == slug:
                    return str(topic.get("title", slug.replace("-", " ").title()))
        except (json.JSONDecodeError, OSError):
            pass
    return slug.replace("-", " ").title()


def build_resynthesis_prompt(topic_title: str, source_summaries: list[tuple[str, str]]) -> str:
    joined = "\n\n---\n\n".join(
        f"Source: [[{stem}]]\n\n{body.strip()}" for stem, body in source_summaries
    )
    return f"""You are maintaining a personal research wiki. Below are source summaries
for the topic "{topic_title}".

Your task:
1. Write a unified synthesis that captures the key knowledge across all sources
2. Identify the main themes and how the sources relate to each other
3. Note any contradictions or tensions between sources
4. Identify gaps — important questions this set of sources does not answer
5. Use [[wikilinks]] to reference specific source summaries when citing them

Format your response as a markdown document with these sections:
## Overview
## Key Themes
## Source Relationships
## Contradictions & Tensions (if any)
## Open Questions & Gaps

Source summaries:
{joined}
"""


def _strip_wrappers(text: str) -> str:
    text = re.sub(r"^```(?:markdown)?\s*\n", "", text.strip())
    text = re.sub(r"\n```\s*$", "", text.strip())
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    return text.strip()


def _render_frontmatter(data: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def topic_status(topic_slug: str, root: Path = ROOT) -> dict[str, object]:
    topic_path = root / "compiled" / "topics" / f"{topic_slug}.md"
    if not topic_path.exists():
        raise TopicNotFoundError(f"Topic note not found: compiled/topics/{topic_slug}.md")
    topic_text = topic_path.read_text(encoding="utf-8", errors="replace")
    fm, _ = _split_frontmatter(topic_text)
    sources = _linked_source_paths(topic_text, root)
    approved = _approved_sources(sources)
    return {
        "slug": topic_slug,
        "display_name": str(fm.get("title") or _title_for_slug(topic_slug, root)),
        "date_updated": str(fm.get("date_updated") or fm.get("date_compiled") or ""),
        "synthesis_version": int(str(fm.get("synthesis_version", "1")) or "1"),
        "source_count": len(sources),
        "approved_source_count": len(approved),
    }


def resynthesize_topic(
    topic_slug: str,
    *,
    model: str = DEFAULT_MODEL,
    root: Path = ROOT,
    dry_run: bool = False,
    force: bool = False,
    no_commit: bool = False,
) -> ResynthesisResult:
    topic_path = root / "compiled" / "topics" / f"{topic_slug}.md"
    if not topic_path.exists():
        raise TopicNotFoundError(f"Topic note not found: compiled/topics/{topic_slug}.md")

    topic_text = topic_path.read_text(encoding="utf-8", errors="replace")
    fm, _ = _split_frontmatter(topic_text)
    topic_title = str(fm.get("title") or _title_for_slug(topic_slug, root))
    all_sources = _linked_source_paths(topic_text, root)
    sources = _approved_sources(all_sources)

    if len(sources) < 2 and not force:
        raise InsufficientSourcesError(
            f"Only {len(sources)} approved source summary found. Need at least 2. Use --force to override."
        )
    if not sources:
        raise InsufficientSourcesError("No approved source summaries found for this topic.")

    source_payload: list[tuple[str, str]] = []
    for path in sources:
        _, body = _split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        source_payload.append((path.stem, body))

    prompt = build_resynthesis_prompt(topic_title, source_payload)
    old_version = int(str(fm.get("synthesis_version", "1")) or "1")
    new_version = old_version + 1

    if dry_run:
        return ResynthesisResult(
            topic_slug=topic_slug,
            topic_path=topic_path,
            synthesis_version=new_version,
            sources_used=len(sources),
            committed=False,
            dry_run=True,
            preview=prompt,
        )

    try:
        _check_model_available(model)
        body = call_ollama(prompt, model)
    except (ConnectionError, ValueError, URLError, OSError) as exc:
        raise OllamaUnavailableError(
            "Ollama is not responding. Ensure it is running with: ollama serve"
        ) from exc

    today = date.today().isoformat()
    date_created = str(fm.get("date_created") or fm.get("date_compiled") or today)
    rel_sources = [str(path.relative_to(root)) for path in sources]
    new_frontmatter: dict[str, object] = {
        "title": topic_title,
        "type": "topic",
        "note_type": "topic",
        "slug": topic_slug,
        "sources": rel_sources,
        "compiled_from": [path.stem for path in sources],
        "date_created": date_created,
        "date_compiled": date_created,
        "date_updated": today,
        "synthesis_version": new_version,
        "approved": "true",
    }
    note_text = f"{_render_frontmatter(new_frontmatter)}\n\n{_strip_wrappers(body)}\n"
    topic_path.write_text(note_text, encoding="utf-8")
    committed = commit_pipeline_stage(
        message=f"resynth: {topic_slug} (v{new_version}, {len(sources)} sources)",
        paths=[topic_path],
        no_commit=no_commit,
        root=root,
    )
    return ResynthesisResult(
        topic_slug=topic_slug,
        topic_path=topic_path,
        synthesis_version=new_version,
        sources_used=len(sources),
        committed=committed,
    )


def _topic_slugs(root: Path) -> list[str]:
    topics_dir = root / "compiled" / "topics"
    return sorted(path.stem for path in topics_dir.glob("*.md")) if topics_dir.exists() else []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-synthesize topic notes from approved source summaries.")
    parser.add_argument("topic_slug", nargs="?", help="Topic slug to re-synthesize.")
    parser.add_argument("--all", action="store_true", help="Re-synthesize every topic note.")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt without writing.")
    parser.add_argument("--force", action="store_true", help="Allow re-synthesis with fewer than 2 sources.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model. Default: {DEFAULT_MODEL}")
    parser.add_argument("--no-commit", action="store_true", help="Write files without auto-committing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.all and not args.topic_slug:
        parser.error("provide a topic slug or --all")

    slugs = _topic_slugs(ROOT) if args.all else [args.topic_slug]
    rc = 0
    for slug in slugs:
        try:
            result = resynthesize_topic(
                slug,
                model=args.model,
                dry_run=args.dry_run,
                force=args.force,
                no_commit=args.no_commit,
            )
        except ResynthesisError as exc:
            print(f"{slug}: {exc}", file=sys.stderr)
            rc = 1
            continue
        if result.dry_run:
            print(result.preview)
        else:
            rel = result.topic_path.relative_to(ROOT)
            print(
                f"{slug}: wrote {rel} v{result.synthesis_version} "
                f"from {result.sources_used} source(s); committed={result.committed}"
            )
    return rc


if __name__ == "__main__":
    sys.exit(main())

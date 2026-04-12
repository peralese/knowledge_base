from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIRS = [
    ROOT / "raw" / "articles",
    ROOT / "raw" / "notes",
    ROOT / "raw" / "pdfs",
]
ARTIFACT_DIRS = [
    ROOT / "compiled",
    ROOT / "outputs",
]
METADATA_DIR = ROOT / "metadata"

REQUIRED_STATUS = {"draft", "reviewed", "stable"}
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#]([^\]]+))?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
BODY_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)
RAW_PATH_RE = re.compile(r"raw/(?:articles|notes|pdfs)/([A-Za-z0-9._-]+\.md)")


@dataclass
class FileRecord:
    path: Path
    original_frontmatter: dict[str, object]
    original_body: str
    frontmatter: dict[str, object]
    body: str
    created: str
    sources: list[str]
    tags: list[str]
    status: str
    placeholders: list[str] = field(default_factory=list)
    stale_reasons: list[str] = field(default_factory=list)
    recommended_action: str = ""
    link_repairs: list[str] = field(default_factory=list)
    link_plaintext_replacements: list[str] = field(default_factory=list)
    link_health: str = "valid"

    @property
    def relpath(self) -> str:
        return self.path.relative_to(ROOT).as_posix()


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    normalized = normalize_text(text)
    match = FRONTMATTER_RE.match(normalized)
    if not match:
        return {}, normalized.strip()
    frontmatter = parse_frontmatter(match.group(1))
    body = normalized[match.end():].strip()
    return frontmatter, body


def parse_scalar(value: str) -> object:
    cleaned = value.strip()
    if cleaned == "[]":
        return []
    if cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return cleaned


def parse_frontmatter(text: str) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            value = stripped[2:].strip()
            data.setdefault(current_key, [])
            assert isinstance(data[current_key], list)
            data[current_key].append(str(parse_scalar(value)))
            continue
        if ":" not in line:
            current_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = []
            current_key = key
            continue
        data[key] = parse_scalar(value)
        current_key = None
    return data


def yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "\n" + "\n".join(f'  - "{yaml_escape(item)}"' for item in values)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def raw_file_map() -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for directory in RAW_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            mapping[path.name] = path
            mapping[path.stem] = path
    return mapping


def artifact_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in ARTIFACT_DIRS:
        if directory.exists():
            paths.extend(sorted(directory.rglob("*.md")))
    return paths


def existing_wikilink_targets() -> dict[str, Path]:
    targets: dict[str, Path] = {}
    for path in artifact_paths():
        targets[path.stem] = path
    for directory in RAW_DIRS:
        if directory.exists():
            for path in directory.glob("*.md"):
                targets[path.stem] = path
    return targets


def infer_title(path: Path, frontmatter: dict[str, object], body: str) -> tuple[str, bool]:
    if isinstance(frontmatter.get("title"), str) and str(frontmatter["title"]).strip():
        return str(frontmatter["title"]).strip(), False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip(), False
        if stripped:
            return stripped[:120], False
    return path.stem.replace("-", " ").replace("_", " ").title(), True


def git_date_for_file(path: Path, fmt: str) -> str:
    try:
        result = subprocess.run(
            ["git", "log", f"--diff-filter=A", f"--format={fmt}", "--", str(path.relative_to(ROOT))],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def infer_created(path: Path, frontmatter: dict[str, object]) -> tuple[str, bool]:
    for key in ("created", "date_compiled", "generated_on", "date_ingested", "date_created", "date"):
        value = frontmatter.get(key)
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
            return value.strip(), False
    created = git_date_for_file(path, "%cs")
    if created:
        return created, False
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat(), True


def infer_tags(frontmatter: dict[str, object]) -> tuple[list[str], bool]:
    tags = frontmatter.get("tags")
    if isinstance(tags, list):
        return dedupe([str(item) for item in tags]), False
    if isinstance(tags, str) and tags.strip():
        return dedupe([tags]), False
    return [], True


def infer_status(frontmatter: dict[str, object]) -> tuple[str, bool]:
    status = str(frontmatter.get("status", "")).strip().lower()
    if status in REQUIRED_STATUS:
        return status, False
    confidence = str(frontmatter.get("confidence", "")).strip().lower()
    if confidence == "high":
        return "reviewed", True
    return "draft", True


def body_source_candidates(body: str) -> list[str]:
    candidates = RAW_PATH_RE.findall(body)
    for wikilink, _display in WIKILINK_RE.findall(body):
        candidates.append(f"{wikilink.strip()}.md")
    return dedupe(candidates)


def infer_sources(
    path: Path,
    frontmatter: dict[str, object],
    body: str,
    raw_map: dict[str, Path],
    compiled_source_map: dict[str, list[str]],
    all_compiled_sources: list[str],
) -> tuple[list[str], list[str], bool]:
    missing: list[str] = []
    placeholder = False
    sources: list[str] = []

    existing_sources = frontmatter.get("sources")
    if isinstance(existing_sources, list):
        for item in existing_sources:
            source_name = str(item).strip()
            if source_name in raw_map:
                sources.append(raw_map[source_name].name)
            elif source_name.endswith(".md") and source_name not in raw_map:
                missing.append(source_name)
            elif source_name in raw_map:
                sources.append(raw_map[source_name].name)

    compiled_from = frontmatter.get("compiled_from")
    if isinstance(compiled_from, list):
        for item in compiled_from:
            name = str(item).strip()
            if name in raw_map:
                sources.append(raw_map[name].name)
            elif f"{name}.md" in raw_map:
                sources.append(raw_map[f"{name}.md"].name)
            else:
                missing.append(f"{name}.md")

    compiled_notes_used = frontmatter.get("compiled_notes_used")
    if isinstance(compiled_notes_used, list):
        for item in compiled_notes_used:
            sources.extend(compiled_source_map.get(str(item).strip(), []))

    if path == ROOT / "compiled" / "index.md":
        sources.extend(all_compiled_sources)

    if "outputs/reports" in path.as_posix():
        for wikilink, _display in WIKILINK_RE.findall(body):
            sources.extend(compiled_source_map.get(wikilink.strip(), []))

    if not sources:
        for candidate in body_source_candidates(body):
            if candidate in raw_map:
                sources.append(raw_map[candidate].name)
            elif candidate.endswith(".md") and candidate[:-3] in raw_map:
                sources.append(raw_map[candidate[:-3]].name)

    sources = dedupe(sources)
    if not sources:
        placeholder = True
    return sources, dedupe(missing), placeholder


def strip_duplicate_body_frontmatter(body: str) -> tuple[str, bool]:
    normalized = normalize_text(body).strip()
    if not normalized.startswith("---\n"):
        return normalized, False
    match = BODY_FRONTMATTER_RE.match(normalized)
    if not match:
        return normalized, False
    cleaned = normalized[match.end():].strip()
    return cleaned, True


def build_preserved_frontmatter(original: dict[str, object], required: dict[str, object]) -> str:
    lines = [
        "---",
        f'title: "{yaml_escape(str(required["title"]))}"',
        f'created: "{required["created"]}"',
        f"sources: {yaml_list(list(required['sources']))}",
        f"tags: {yaml_list(list(required['tags']))}",
        f'status: "{required["status"]}"',
    ]

    for key, value in original.items():
        if key in required:
            continue
        if isinstance(value, list):
            lines.append(f"{key}: {yaml_list([str(item) for item in value])}")
        else:
            lines.append(f'{key}: "{yaml_escape(str(value))}"')

    lines.append("---")
    return "\n".join(lines)


def reference_map(paths: list[Path]) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for target, _display in WIKILINK_RE.findall(text):
            refs.setdefault(target.strip(), set()).add(path.relative_to(ROOT).as_posix())

    for meta_path in sorted(METADATA_DIR.rglob("*")):
        if not meta_path.is_file():
            continue
        text = meta_path.read_text(encoding="utf-8", errors="replace")
        for path in paths:
            stem = path.stem
            rel = path.relative_to(ROOT).as_posix()
            if stem in text or rel in text or path.name in text:
                refs.setdefault(stem, set()).add(meta_path.relative_to(ROOT).as_posix())
    return refs


def last_modified_date(path: Path) -> datetime:
    git_date = git_date_for_file(path, "%cI")
    if git_date:
        try:
            return datetime.fromisoformat(git_date.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def make_stale_report(records: list[FileRecord]) -> str:
    lines = [
        "# Stale Artifact Audit",
        "",
        f"Generated: {datetime.now().date().isoformat()}",
        "",
    ]
    if not any(record.stale_reasons for record in records):
        lines.append("No stale artifacts detected.")
        return "\n".join(lines) + "\n"

    lines.extend([
        "| File | Age (days) | Stale Reason | Recommended Action |",
        "|---|---:|---|---|",
    ])
    now = datetime.now()
    for record in records:
        if not record.stale_reasons:
            continue
        age_days = (now - last_modified_date(record.path)).days
        lines.append(
            f"| `{record.relpath}` | {age_days} | {'; '.join(record.stale_reasons)} | {record.recommended_action} |"
        )
    return "\n".join(lines) + "\n"


def make_shape_report(records: list[FileRecord], duplicate_body_frontmatter: dict[str, bool]) -> str:
    lines = [
        "# Shape Normalization Report",
        "",
        f"Generated: {datetime.now().date().isoformat()}",
        "",
    ]
    flagged = [
        record for record in records
        if record.placeholders or duplicate_body_frontmatter.get(record.relpath, False)
    ]
    if not flagged:
        lines.append("No placeholder values or structural repairs were required.")
        return "\n".join(lines) + "\n"

    for record in flagged:
        lines.append(f"## `{record.relpath}`")
        if record.placeholders:
            lines.append("")
            lines.append(f"- Placeholder or inferred fallback fields: {', '.join(record.placeholders)}")
        if duplicate_body_frontmatter.get(record.relpath, False):
            lines.append("- Removed duplicated embedded frontmatter block from body.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_wikilink_report(records: list[FileRecord]) -> str:
    lines = [
        "# Wikilink Report",
        "",
        f"Generated: {datetime.now().date().isoformat()}",
        "",
    ]
    touched = [
        record for record in records
        if record.link_repairs or record.link_plaintext_replacements or record.link_health == "broken"
    ]
    if not touched:
        lines.append("All wikilinks validated cleanly. No repairs were needed.")
        return "\n".join(lines) + "\n"

    for record in touched:
        lines.append(f"## `{record.relpath}`")
        lines.append("")
        if record.link_repairs:
            for item in record.link_repairs:
                lines.append(f"- Repaired: {item}")
        if record.link_plaintext_replacements:
            for item in record.link_plaintext_replacements:
                lines.append(f"- Replaced with plain text: {item}")
        if record.link_health == "broken":
            lines.append("- Broken wikilinks remain after repair pass.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_metadata_index(records: list[FileRecord]) -> str:
    status_counts: dict[str, int] = {}
    stale_counts: dict[str, int] = {}
    remaining_broken = 0

    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
        for reason in record.stale_reasons:
            stale_counts[reason] = stale_counts.get(reason, 0) + 1
        if record.link_health == "broken":
            remaining_broken += 1

    lines = [
        "# Artifact Metadata Index",
        "",
        f"Generated: {datetime.now().date().isoformat()}",
        "",
        "## Totals",
        "",
    ]

    for status in sorted(status_counts):
        lines.append(f"- Status `{status}`: {status_counts[status]}")
    if stale_counts:
        for reason in sorted(stale_counts):
            lines.append(f"- Stale reason `{reason}`: {stale_counts[reason]}")
    else:
        lines.append("- Stale reason counts: none")
    lines.append(f"- Files with broken links remaining: {remaining_broken}")
    lines.append("")
    lines.extend([
        "## Files",
        "",
        "| File | Title | Created | Status | Sources | Stale | Wikilinks |",
        "|---|---|---|---|---|---|---|",
    ])

    for record in sorted(records, key=lambda item: item.relpath):
        stale = "; ".join(record.stale_reasons) if record.stale_reasons else "no"
        sources = ", ".join(record.sources) if record.sources else "[]"
        lines.append(
            f"| `{record.relpath}` | {record.frontmatter['title']} | {record.created} | "
            f"{record.status} | {sources} | {stale} | {record.link_health} |"
        )

    return "\n".join(lines) + "\n"


def repair_wikilinks(text: str, targets: dict[str, Path], record: FileRecord) -> tuple[str, str]:
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        target = match.group(1).strip()
        display = match.group(2).strip() if match.group(2) else target
        if target in targets:
            return match.group(0)

        best_target = ""
        best_score = 0.0
        for candidate in targets:
            score = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
            if score > best_score:
                best_score = score
                best_target = candidate

        if best_score >= 0.8:
            changed = True
            record.link_repairs.append(f"`[[{target}]]` -> `[[{best_target}]]` ({best_score:.0%} similarity)")
            alias = f"|{display}" if match.group(2) else ""
            return f"[[{best_target}{alias}]]"

        changed = True
        record.link_plaintext_replacements.append(f"`[[{target}]]` -> `{display}`")
        return display

    updated = WIKILINK_RE.sub(replace, text)
    unresolved = any(target.strip() not in targets for target, _display in WIKILINK_RE.findall(updated))
    if unresolved:
        record.link_health = "broken"
    elif record.link_repairs or record.link_plaintext_replacements:
        record.link_health = "repaired"
    else:
        record.link_health = "valid"
    return updated, "changed" if changed else "unchanged"


def main() -> int:
    raw_map = raw_file_map()
    paths = artifact_paths()
    refs = reference_map(paths)

    initial_frontmatter: dict[str, dict[str, object]] = {}
    initial_bodies: dict[str, str] = {}
    for path in paths:
        fm, body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        initial_frontmatter[path.relative_to(ROOT).as_posix()] = fm
        initial_bodies[path.relative_to(ROOT).as_posix()] = body

    compiled_source_map: dict[str, list[str]] = {}
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        if not rel.startswith("compiled/") or rel == "compiled/index.md":
            continue
        sources, _missing, _placeholder = infer_sources(
            path=path,
            frontmatter=initial_frontmatter[rel],
            body=initial_bodies[rel],
            raw_map=raw_map,
            compiled_source_map={},
            all_compiled_sources=[],
        )
        compiled_source_map[path.stem] = sources

    all_compiled_sources = dedupe(
        [source for stem, sources in compiled_source_map.items() if stem != "index" for source in sources]
    )

    records: list[FileRecord] = []
    duplicate_body_frontmatter: dict[str, bool] = {}

    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        frontmatter = dict(initial_frontmatter[rel])
        body, removed_dup = strip_duplicate_body_frontmatter(initial_bodies[rel])
        duplicate_body_frontmatter[rel] = removed_dup

        title, title_placeholder = infer_title(path, frontmatter, body)
        created, created_placeholder = infer_created(path, frontmatter)
        tags, tags_placeholder = infer_tags(frontmatter)
        status, status_placeholder = infer_status(frontmatter)
        sources, missing_sources, sources_placeholder = infer_sources(
            path=path,
            frontmatter=frontmatter,
            body=body,
            raw_map=raw_map,
            compiled_source_map=compiled_source_map,
            all_compiled_sources=all_compiled_sources,
        )

        placeholders: list[str] = []
        if title_placeholder:
            placeholders.append("title")
        if created_placeholder:
            placeholders.append("created")
        if tags_placeholder:
            placeholders.append("tags")
        if status_placeholder:
            placeholders.append("status")
        if sources_placeholder:
            placeholders.append("sources")

        record = FileRecord(
            path=path,
            original_frontmatter=dict(frontmatter),
            original_body=initial_bodies[rel],
            frontmatter=frontmatter,
            body=body,
            created=created,
            sources=sources,
            tags=tags,
            status=status,
            placeholders=placeholders,
        )

        required = {
            "title": title,
            "created": created,
            "sources": sources,
            "tags": tags,
            "status": status,
        }
        record.frontmatter.update(required)

        original_has_lineage = bool(
            record.original_frontmatter.get("compiled_from")
            or record.original_frontmatter.get("compiled_notes_used")
            or record.original_frontmatter.get("sources_used")
            or RAW_PATH_RE.search(record.original_body)
        )

        if missing_sources:
            record.stale_reasons.append(f"missing source(s): {', '.join(missing_sources)}")
            record.recommended_action = "re-derive"
        if not original_has_lineage:
            record.stale_reasons.append("no lineage metadata")
            if not record.recommended_action:
                record.recommended_action = "review"
        age_days = (datetime.now() - last_modified_date(path)).days
        if age_days >= 90 and not refs.get(path.stem):
            record.stale_reasons.append("unreferenced and older than 90 days")
            if not record.recommended_action:
                record.recommended_action = "delete"
        if not record.recommended_action:
            record.recommended_action = "review" if record.stale_reasons else ""

        records.append(record)

    targets = existing_wikilink_targets()
    for record in records:
        updated_body, _ = repair_wikilinks(record.body, targets, record)
        record.body = updated_body

    for record in records:
        frontmatter_text = build_preserved_frontmatter(
            original=record.frontmatter,
            required={
                "title": record.frontmatter["title"],
                "created": record.created,
                "sources": record.sources,
                "tags": record.tags,
                "status": record.status,
            },
        )
        record.path.write_text(f"{frontmatter_text}\n\n{record.body.strip()}\n", encoding="utf-8")

    (METADATA_DIR / "stale_audit.md").write_text(make_stale_report(records), encoding="utf-8")
    (METADATA_DIR / "shape_normalization.md").write_text(
        make_shape_report(records, duplicate_body_frontmatter),
        encoding="utf-8",
    )
    (METADATA_DIR / "wikilink_report.md").write_text(make_wikilink_report(records), encoding="utf-8")
    (METADATA_DIR / "index.md").write_text(make_metadata_index(records), encoding="utf-8")

    print("Wrote metadata/stale_audit.md")
    print("Wrote metadata/shape_normalization.md")
    print("Wrote metadata/wikilink_report.md")
    print("Wrote metadata/index.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

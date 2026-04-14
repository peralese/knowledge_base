"""Phase 6 Inbox Watcher: monitor raw/inbox/ and auto-ingest new files.

Watches raw/inbox/ using a polling loop (no external dependencies). When a
new file appears it is automatically ingested via ingest.py using metadata
derived from the file itself. Already-processed files are tracked in
metadata/.watcher-state.json so the watcher is safe to stop and restart.

Phase 1 ingestion automation extends this with a second stage after ingest:
every ingested note is validated against the repository raw-note shape and
queued for human review in metadata/review-queue.json and metadata/review-queue.md.
Auto-synthesis is intentionally not triggered.

Title derivation (in priority order):
  1. YAML frontmatter `title:` field (for markdown files)
  2. First non-empty line of the file (trimmed of # and whitespace)
  3. The filename stem with hyphens/underscores converted to spaces

Source type derivation:
  - .pdf          -> pdf
  - .md / .txt    -> article  (override with --source-type)
  - anything else -> article

Usage:
    # Foreground (Ctrl-C to stop)
    python3 scripts/inbox_watcher.py

    # Custom poll interval and source type default
    python3 scripts/inbox_watcher.py --interval 10 --source-type note

    # One-shot: process whatever is in inbox right now then exit
    python3 scripts/inbox_watcher.py --once
"""
from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX_DIR = ROOT / "raw" / "inbox"
STATE_PATH = ROOT / "metadata" / ".watcher-state.json"
REVIEW_QUEUE_PATH = ROOT / "metadata" / "review-queue.json"
REVIEW_QUEUE_REPORT_PATH = ROOT / "metadata" / "review-queue.md"
DEFAULT_INTERVAL = 5  # seconds
WATCHED_EXTENSIONS = {".md", ".txt", ".pdf", ".html", ".json"}
ADAPTER_DIRECTORIES = {
    "inbox": INBOX_DIR,
    "browser": INBOX_DIR / "browser",
    "clipboard": INBOX_DIR / "clipboard",
    "feeds": INBOX_DIR / "feeds",
    "pdf-drop": INBOX_DIR / "pdf-drop",
}
REQUIRED_FRONTMATTER_KEYS = [
    "title",
    "source_type",
    "origin",
    "date_ingested",
    "status",
    "topics",
    "tags",
    "source_id",
    "canonical_url",
]
REQUIRED_BODY_HEADINGS = [
    "# Overview",
    "# Source Content",
    "# Key Points",
    "# Notes",
    "# Lineage",
]


@dataclass
class IngestOutcome:
    processed: bool
    output_path: Path | None = None
    validation_issues: list[str] | None = None
    adapter: str = "inbox"
    source_type: str = ""
    origin: str = ""
    title: str = ""


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state() -> dict[str, str]:
    """Load the set of already-processed inbox paths from the state file."""
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, str]) -> None:
    """Persist the processed-paths state."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_review_queue() -> list[dict[str, object]]:
    """Load the pending review queue."""
    if not REVIEW_QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(REVIEW_QUEUE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    return []


def save_review_queue(entries: list[dict[str, object]]) -> None:
    """Persist the review queue and its markdown view."""
    REVIEW_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE_PATH.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    REVIEW_QUEUE_REPORT_PATH.write_text(render_review_queue(entries), encoding="utf-8")


# ---------------------------------------------------------------------------
# Metadata derivation
# ---------------------------------------------------------------------------

def _parse_frontmatter_title(text: str) -> str:
    """Return the title from YAML frontmatter if present, else empty string."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return ""
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return ""
    for line in parts[0].splitlines():
        m = re.match(r'^title:\s*"?([^"]+)"?\s*$', line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _parse_frontmatter_value(text: str, key: str) -> str:
    """Extract a scalar frontmatter value from staged markdown when present."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return ""
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return ""
    pattern = re.compile(rf'^{re.escape(key)}:\s*"?([^"]+)"?\s*$')
    for line in parts[0].splitlines():
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    return ""


def _first_content_line(text: str) -> str:
    """Return the first non-empty, non-frontmatter line stripped of markdown heading markers."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    if not lines:
        return ""

    # Skip YAML frontmatter block (--- ... ---) if present at top of file.
    start = 0
    if lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break

    for line in lines[start:]:
        stripped = line.strip()
        if stripped:
            return re.sub(r"^#+\s*", "", stripped)
    return ""


def derive_title(path: Path) -> str:
    """Derive the best available title for an inbox file."""
    if path.suffix.lower() == ".pdf":
        return path.stem.replace("-", " ").replace("_", " ").title()

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path.stem.replace("-", " ").replace("_", " ").title()

    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            for key in ("title", "headline", "name"):
                value = str(payload.get(key, "")).strip()
                if value:
                    return value[:120]

    if path.suffix.lower() == ".html":
        # Try <title> tag before falling back to text extraction
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", text, re.IGNORECASE)
        if title_match:
            html_title = html_module.unescape(title_match.group(1).strip())
            if html_title:
                return html_title[:120]
        # Fall back to first meaningful line of stripped text
        from ingest import html_to_text  # noqa: PLC0415
        stripped = html_to_text(text)
        first_line = _first_content_line(stripped)
        if first_line:
            return first_line[:120]
        return path.stem.replace("-", " ").replace("_", " ").title()

    title = _parse_frontmatter_title(text)
    if title:
        return title

    first_line = _first_content_line(text)
    if first_line:
        return first_line[:120]  # cap at a sensible length

    return path.stem.replace("-", " ").replace("_", " ").title()


def detect_adapter(path: Path) -> str:
    """Identify which intake adapter folder a file came from."""
    normalized_parts = [part.lower() for part in path.resolve().parts]
    for adapter in ("browser", "clipboard", "feeds", "pdf-drop"):
        if adapter in normalized_parts:
            return adapter
    return "inbox"


def derive_source_type(path: Path, default: str) -> str:
    """Derive source type from file extension."""
    if path.suffix.lower() == ".pdf":
        return "pdf"
    if path.suffix.lower() == ".json":
        return "article"
    return default


def derive_origin(path: Path) -> str:
    """Derive origin label from file extension and content hints."""
    adapter = detect_adapter(path)
    if adapter == "browser":
        return "web"
    if adapter == "clipboard":
        return "clipboard"
    if adapter == "feeds":
        return "feed"
    if path.suffix.lower() == ".pdf":
        return "local-file"
    if path.suffix.lower() == ".md":
        return "local-markdown"
    return "local-file"


def derive_canonical_url(path: Path) -> str:
    """Best-effort canonical URL extraction from staged adapter files."""
    if path.suffix.lower() == ".pdf":
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    frontmatter_url = _parse_frontmatter_value(text, "canonical_url")
    if frontmatter_url:
        return frontmatter_url

    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return ""
        if isinstance(payload, dict):
            for key in ("canonical_url", "url", "link"):
                value = str(payload.get(key, "")).strip()
                if value:
                    return value
        return ""

    url_match = re.search(r"https?://\S+", text)
    return url_match.group(0).rstrip(").,]") if url_match else ""


def _parse_frontmatter(text: str) -> dict[str, object]:
    """Parse the limited raw-note frontmatter schema used in this repository."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return {}
    payload: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in parts[0].splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            payload.setdefault(current_key, [])
            assert isinstance(payload[current_key], list)
            payload[current_key].append(stripped[2:].strip().strip('"'))
            continue
        if ":" not in line:
            current_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            payload[key] = []
            current_key = key
            continue
        payload[key] = value.strip('"')
        current_key = None
    return payload


def validate_ingested_note(path: Path) -> list[str]:
    """Validate the raw note shape created by ingest.py before queueing review."""
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter = _parse_frontmatter(text)
    issues: list[str] = []

    for key in REQUIRED_FRONTMATTER_KEYS:
        if key not in frontmatter:
            issues.append(f"missing frontmatter field: {key}")

    for key in ("topics", "tags"):
        value = frontmatter.get(key)
        if not isinstance(value, list) and value != "[]":
            issues.append(f"frontmatter field should be a list: {key}")

    if frontmatter.get("status") not in {"raw", "draft", "reviewed"}:
        issues.append("unexpected status value")

    for heading in REQUIRED_BODY_HEADINGS:
        if heading not in text:
            issues.append(f"missing section heading: {heading}")

    return issues


def queue_review_item(
    *,
    source_note_path: Path,
    inbox_path: Path,
    title: str,
    source_type: str,
    origin: str,
    adapter: str,
    validation_issues: list[str],
) -> None:
    """Add or update a pending review entry for an ingested note."""
    queue = load_review_queue()
    text = source_note_path.read_text(encoding="utf-8", errors="replace")
    frontmatter = _parse_frontmatter(text)
    entry = {
        "source_id": str(frontmatter.get("source_id", "")),
        "title": title,
        "source_note_path": str(source_note_path.relative_to(ROOT)),
        "input_path": str(inbox_path),
        "adapter": adapter,
        "source_type": source_type,
        "origin": origin,
        "queued_at": datetime.now().isoformat(),
        "review_status": "pending_review",
        "validation_status": "validated" if not validation_issues else "needs_review",
        "validation_issues": validation_issues,
    }

    existing_index = next(
        (
            idx for idx, item in enumerate(queue)
            if item.get("source_note_path") == entry["source_note_path"]
        ),
        None,
    )
    if existing_index is None:
        queue.append(entry)
    else:
        queue[existing_index] = {**queue[existing_index], **entry}

    save_review_queue(queue)


def render_review_queue(entries: list[dict[str, object]]) -> str:
    """Render the queue as a simple markdown review board."""
    lines = [
        "# Review Queue",
        "",
        f"_Generated on {datetime.now().date().isoformat()}_",
        "",
    ]
    if not entries:
        lines.append("No pending review items.")
        return "\n".join(lines) + "\n"

    lines.extend([
        "| Title | Source Note | Adapter | Validation | Review |",
        "|---|---|---|---|---|",
    ])
    for entry in entries:
        lines.append(
            f"| {entry.get('title', '')} | `{entry.get('source_note_path', '')}` | "
            f"{entry.get('adapter', '')} | {entry.get('validation_status', '')} | "
            f"{entry.get('review_status', '')} |"
        )
        issues = entry.get("validation_issues", [])
        if issues:
            for issue in issues:
                lines.append(f"|  |  |  | issue: {issue} |  |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Ingest dispatch
# ---------------------------------------------------------------------------

def ingest_file(path: Path, source_type: str) -> IngestOutcome:
    """Call ingest_source(), validate the result, and queue it for review."""
    sys.path.insert(0, str(Path(__file__).parent))
    from ingest import ingest_source, IngestRequest  # noqa: PLC0415

    title = derive_title(path)
    resolved_source_type = derive_source_type(path, source_type)
    origin = derive_origin(path)
    canonical_url = derive_canonical_url(path)
    adapter = detect_adapter(path)

    print(f"  Title       : {title}")
    print(f"  Source type : {resolved_source_type}")
    print(f"  Origin      : {origin}")
    if canonical_url:
        print(f"  Canonical   : {canonical_url}")

    try:
        result = ingest_source(
            IngestRequest(
                title=title,
                source_type=resolved_source_type,
                origin=origin,
                canonical_url=canonical_url,
                input_path=str(path),
                root=ROOT,
            )
        )
        validation_issues = validate_ingested_note(result)
        queue_review_item(
            source_note_path=result,
            inbox_path=path,
            title=title,
            source_type=resolved_source_type,
            origin=origin,
            adapter=adapter,
            validation_issues=validation_issues,
        )
        print(f"  -> {result.relative_to(ROOT)}")
        print(
            "  Validation  : "
            + ("validated" if not validation_issues else f"needs review ({len(validation_issues)} issue(s))")
        )
        print("  Queue       : metadata/review-queue.md")
        return IngestOutcome(
            processed=True,
            output_path=result,
            validation_issues=validation_issues,
            adapter=adapter,
            source_type=resolved_source_type,
            origin=origin,
            title=title,
        )
    except FileExistsError as exc:
        print(f"  Skipped (already exists): {exc}")
        return IngestOutcome(
            processed=True,
            adapter=adapter,
            source_type=resolved_source_type,
            origin=origin,
            title=title,
        )  # already ingested counts as processed
    except Exception as exc:  # noqa: BLE001
        print(f"  Error: {exc}")
        return IngestOutcome(
            processed=False,
            adapter=adapter,
            source_type=resolved_source_type,
            origin=origin,
            title=title,
        )


# ---------------------------------------------------------------------------
# Watcher loop
# ---------------------------------------------------------------------------

def scan_inbox(inbox: Path, state: dict[str, str], source_type: str) -> dict[str, str]:
    """Check for new files in inbox and ingest them. Returns updated state."""
    if not inbox.exists():
        return state

    updated = dict(state)
    for path in sorted(inbox.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in WATCHED_EXTENSIONS:
            continue
        key = str(path.resolve())
        if key in state:
            continue

        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] New file: {path.name}")
        outcome = ingest_file(path, source_type)
        if outcome.processed:
            updated[key] = datetime.now().isoformat()

    return updated


def watch(interval: int, source_type: str, once: bool) -> None:
    """Main watcher loop."""
    state = load_state()
    for directory in ADAPTER_DIRECTORIES.values():
        directory.mkdir(parents=True, exist_ok=True)

    if once:
        state = scan_inbox(INBOX_DIR, state, source_type)
        save_state(state)
        return

    print(f"Watching {INBOX_DIR.relative_to(ROOT)}  (interval: {interval}s, Ctrl-C to stop)")
    try:
        while True:
            new_state = scan_inbox(INBOX_DIR, state, source_type)
            if new_state != state:
                save_state(new_state)
                state = new_state
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 6 Inbox Watcher: auto-ingest files dropped into raw/inbox/."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Poll interval in seconds. Default: {DEFAULT_INTERVAL}",
    )
    parser.add_argument(
        "--source-type",
        default="article",
        help="Default source type when it cannot be derived from the file. Default: article",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process whatever is in inbox right now then exit (no loop).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    watch(interval=args.interval, source_type=args.source_type, once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())

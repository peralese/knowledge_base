"""Phase 6 Inbox Watcher: monitor raw/inbox/ and auto-ingest new files.

Watches raw/inbox/ using a polling loop (no external dependencies). When a
new file appears it is automatically ingested via ingest.py using metadata
derived from the file itself. Already-processed files are tracked in
metadata/.watcher-state.json so the watcher is safe to stop and restart.

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
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX_DIR = ROOT / "raw" / "inbox"
STATE_PATH = ROOT / "metadata" / ".watcher-state.json"
DEFAULT_INTERVAL = 5  # seconds
WATCHED_EXTENSIONS = {".md", ".txt", ".pdf"}


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

    title = _parse_frontmatter_title(text)
    if title:
        return title

    first_line = _first_content_line(text)
    if first_line:
        return first_line[:120]  # cap at a sensible length

    return path.stem.replace("-", " ").replace("_", " ").title()


def derive_source_type(path: Path, default: str) -> str:
    """Derive source type from file extension."""
    if path.suffix.lower() == ".pdf":
        return "pdf"
    return default


def derive_origin(path: Path) -> str:
    """Derive origin label from file extension and content hints."""
    if path.suffix.lower() == ".pdf":
        return "local-file"
    if path.suffix.lower() == ".md":
        return "local-markdown"
    return "local-file"


# ---------------------------------------------------------------------------
# Ingest dispatch
# ---------------------------------------------------------------------------

def ingest_file(path: Path, source_type: str) -> bool:
    """Call ingest_source() directly. Returns True on success."""
    sys.path.insert(0, str(Path(__file__).parent))
    from ingest import ingest_source, IngestRequest  # noqa: PLC0415

    title = derive_title(path)
    resolved_source_type = derive_source_type(path, source_type)
    origin = derive_origin(path)

    print(f"  Title       : {title}")
    print(f"  Source type : {resolved_source_type}")
    print(f"  Origin      : {origin}")

    try:
        result = ingest_source(
            IngestRequest(
                title=title,
                source_type=resolved_source_type,
                origin=origin,
                input_path=str(path),
                root=ROOT,
            )
        )
        print(f"  -> {result.relative_to(ROOT)}")
        return True
    except FileExistsError as exc:
        print(f"  Skipped (already exists): {exc}")
        return True  # already ingested counts as processed
    except Exception as exc:  # noqa: BLE001
        print(f"  Error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Watcher loop
# ---------------------------------------------------------------------------

def scan_inbox(inbox: Path, state: dict[str, str], source_type: str) -> dict[str, str]:
    """Check for new files in inbox and ingest them. Returns updated state."""
    if not inbox.exists():
        return state

    updated = dict(state)
    for path in sorted(inbox.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in WATCHED_EXTENSIONS:
            continue
        key = str(path.resolve())
        if key in state:
            continue

        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] New file: {path.name}")
        success = ingest_file(path, source_type)
        if success:
            updated[key] = datetime.now().isoformat()

    return updated


def watch(interval: int, source_type: str, once: bool) -> None:
    """Main watcher loop."""
    state = load_state()

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

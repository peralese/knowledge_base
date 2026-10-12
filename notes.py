"""Notes: short snippets kept as `## ` entries in one Markdown file per topic.

  <LIBRARY_ROOT>/<category folder>/<Topic>.md

Each entry is a heading, the body, then `Source:` and `Saved:` lines, so each
heading becomes one citable section once indexed.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from store import CATEGORIES, LIBRARY_ROOT


def category_dir(category: int, root: Path = LIBRARY_ROOT) -> Path:
    if category not in CATEGORIES:
        raise ValueError(f"category must be 1-7, got {category}")
    for d in sorted(root.iterdir()):
        if d.is_dir() and re.match(rf"^\s*{category}\b", d.name):
            return d
    raise FileNotFoundError(f"No folder for category {category} under {root}")


def topic_file(category: int, topic: str, root: Path = LIBRARY_ROOT) -> Path:
    """The topic's file, matching an existing one case-insensitively."""
    name = re.sub(r'[/\\:*?"<>|]+', " ", topic).strip().rstrip(".")
    if not name:
        raise ValueError("topic is empty")
    folder = category_dir(category, root)
    for f in folder.glob("*.md"):
        if f.stem.lower() == name.lower():
            return f
    return folder / f"{name}.md"


def append_note(category: int, topic: str, heading: str, body: str, source: str,
                root: Path = LIBRARY_ROOT, today: date | None = None) -> tuple[Path, bool]:
    """Append one entry; returns (file, created)."""
    heading, body, source = heading.strip(), body.strip(), source.strip()
    if not heading or not body:
        raise ValueError("heading and body are required")
    path = topic_file(category, topic, root)
    created = not path.exists()
    text = path.read_text(encoding="utf-8") if not created else (
        f"---\ntitle: {path.stem}\n---\n")
    entry = (f"\n## {heading}\n\n{body}\n\nSource: {source or 'not recorded'}\n"
             f"Saved: {(today or date.today()).isoformat()}\n")
    path.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")
    return path, created

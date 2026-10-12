"""Log of library tool calls, to see whether the library is actually used.

Kept in its own database (data/usage.db), apart from the index: `indexer.py
--rebuild` deletes library.db, and the MCP server shouldn't compete with the
indexer for write locks.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

USAGE_DB = Path(os.environ.get(
    "LIBRARY_USAGE_DB", Path(__file__).resolve().parent / "data" / "usage.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,        -- local time
    tool TEXT NOT NULL,
    arg TEXT,                -- query, section_id, source, url, ...
    project TEXT,            -- directory of the Claude Code session
    hits TEXT                -- JSON list of top result titles
);
"""


def project_name(cwd: str | None = None) -> str:
    cwd = cwd or os.getcwd()
    home = str(Path.home())
    return "~" + cwd[len(home):] if cwd.startswith(home) else cwd


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5)
    db.executescript(SCHEMA)
    return db


def log_call(tool: str, arg: str | None = None, hits: list[str] | None = None,
             project: str | None = None, path: Path | None = None) -> None:
    """Record one call. Never raises: logging must not break a tool."""
    try:
        with _connect(path or USAGE_DB) as db:
            db.execute("INSERT INTO calls (at, tool, arg, project, hits) VALUES (?, ?, ?, ?, ?)",
                       (datetime.now().isoformat(sep=" ", timespec="seconds"), tool,
                        arg, project or project_name(), json.dumps(hits or [])))
    except Exception:
        pass


def summary(days: int = 7, path: Path | None = None) -> list[str]:
    path = path or USAGE_DB
    if not path.exists():
        return [f"Usage: no library calls logged yet ({path})"]
    since = (datetime.now() - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")
    with _connect(path) as db:
        rows = db.execute("SELECT tool, project, hits FROM calls WHERE at >= ?",
                          (since,)).fetchall()
    if not rows:
        return [f"Usage, last {days} days: no library calls"]
    tools = Counter(t for t, _, _ in rows)
    projects = Counter(p for _, p, _ in rows)
    books = Counter(h for _, _, hits in rows for h in json.loads(hits or "[]")[:1])
    lines = [f"Usage, last {days} days: " + ", ".join(f"{n} {t}" for t, n in tools.most_common())
             + f" from {len(projects)} project(s)"]
    lines += [f"  {n:3} {p}" for p, n in projects.most_common(5)]
    if books:
        lines.append("  top hits: " + "; ".join(f"{b} ({n})" for b, n in books.most_common(5)))
    return lines

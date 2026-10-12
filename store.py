"""SQLite index: sources, sections, passages, FTS5 and sqlite-vec tables.

The index holds the full text of every passage and section, so search and
read_section never touch the book files (which live on the NAS).
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import sqlite_vec

LIBRARY_ROOT = Path(os.environ.get("LIBRARY_ROOT", "~/Books/library")).expanduser()
DB_PATH = Path(os.environ.get(
    "LIBRARY_DB", Path(__file__).resolve().parent / "data" / "library.db"))
EMBED_DIM = 768  # nomic-embed-text

CATEGORIES = {
    1: "Enterprise & Software",
    2: "Cloud, Platform & Infrastructure Engineering",
    3: "Integration, APIs & Automation",
    4: "Data, AI & Machine Learning Engineering",
    5: "Cybersecurity & Security Architecture",
    6: "AI Strategy, Society & Emerging Technology",
    7: "Developer & Systems Reference",
}

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    rel_path TEXT UNIQUE NOT NULL,   -- relative to LIBRARY_ROOT
    sha256 TEXT NOT NULL,
    kind TEXT NOT NULL,              -- book | article
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    category INTEGER NOT NULL,
    url TEXT,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    ord INTEGER NOT NULL,
    chapter TEXT NOT NULL,
    path TEXT NOT NULL,              -- breadcrumb joined with ' > '
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS passages (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    ord INTEGER NOT NULL,            -- position within the section
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS passages_section ON passages(section_id);
CREATE INDEX IF NOT EXISTS sections_source ON sections(source_id);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
    text, path, content='', contentless_delete=1, tokenize='porter unicode61'
);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_vec USING vec0(
    passage_id INTEGER PRIMARY KEY,
    embedding float[{EMBED_DIM}] distance_metric=cosine,
    category INTEGER
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.executescript(SCHEMA)
    return db


def delete_source(db: sqlite3.Connection, source_id: int) -> None:
    ids = [r[0] for r in db.execute(
        "SELECT id FROM passages WHERE source_id = ?", (source_id,))]
    for pid in ids:
        db.execute("DELETE FROM passages_fts WHERE rowid = ?", (pid,))
        db.execute("DELETE FROM passages_vec WHERE passage_id = ?", (pid,))
    db.execute("DELETE FROM sources WHERE id = ?", (source_id,))

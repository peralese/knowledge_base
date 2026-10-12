"""Index everything under LIBRARY_ROOT.

Category comes from the top-level folder ("4 - Data, AI & ..." -> 4).
Unchanged files (same sha256) are skipped; changed files are re-indexed;
files that disappeared are removed from the index.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import sqlite_vec

from embed import embed_documents
from parse import parse, split_passages
from store import DB_PATH, LIBRARY_ROOT, connect, delete_source

SUFFIXES = {".epub", ".html", ".htm", ".md"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _category(rel: Path) -> int | None:
    m = re.match(r"^\s*(\d+)\b", rel.parts[0]) if len(rel.parts) > 1 else None
    return int(m.group(1)) if m else None


def discover(root: Path = LIBRARY_ROOT) -> list[Path]:
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() in SUFFIXES
                  and not p.name.startswith(("._", ".")))


def _url_for(path: Path) -> str | None:
    """Articles saved by add_url.py carry a sidecar <name>.url.json."""
    side = path.with_suffix(path.suffix + ".url.json")
    if side.exists():
        return json.loads(side.read_text()).get("url")
    return None


def index_file(db: sqlite3.Connection, path: Path, rel: Path, category: int,
               sha: str, log=print) -> int:
    t0 = time.time()
    doc = parse(path)
    kind = "book" if path.suffix.lower() == ".epub" else "article"
    cur = db.execute(
        "INSERT INTO sources (rel_path, sha256, kind, title, authors, category, url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(rel), sha, kind, doc.title, ", ".join(doc.authors), category,
         _url_for(path)))
    source_id = cur.lastrowid

    rows = []  # (section_id, ord, text, path)
    for s_ord, sec in enumerate(doc.sections):
        path_str = " > ".join(sec.path)
        sid = db.execute(
            "INSERT INTO sections (source_id, ord, chapter, path, text) VALUES (?, ?, ?, ?, ?)",
            (source_id, s_ord, sec.chapter, path_str, sec.text)).lastrowid
        for p_ord, text in enumerate(split_passages(sec)):
            rows.append((sid, p_ord, text, path_str))

    # Embed with the title and breadcrumb in front, so a passage that only
    # says "this approach" still carries what it is about.
    vectors = embed_documents([f"{doc.title} — {p}\n\n{t}" for _, _, t, p in rows])
    for (sid, p_ord, text, path_str), vec in zip(rows, vectors):
        pid = db.execute(
            "INSERT INTO passages (source_id, section_id, ord, text) VALUES (?, ?, ?, ?)",
            (source_id, sid, p_ord, text)).lastrowid
        db.execute("INSERT INTO passages_fts (rowid, text, path) VALUES (?, ?, ?)",
                   (pid, text, f"{doc.title} {path_str}"))
        db.execute("INSERT INTO passages_vec (passage_id, embedding, category) VALUES (?, ?, ?)",
                   (pid, sqlite_vec.serialize_float32(vec), category))
    log(f"  indexed {doc.title!r}: {len(doc.sections)} sections, "
        f"{len(rows)} passages in {time.time() - t0:.0f}s")
    return len(rows)


def run(root: Path = LIBRARY_ROOT, log=print) -> dict:
    if not root.exists():
        raise SystemExit(f"Library folder not found: {root} (is the NAS mounted?)")
    db = connect()
    seen = set()
    stats = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0, "skipped": 0}
    for path in discover(root):
        rel = path.relative_to(root)
        category = _category(rel)
        if category is None:
            log(f"  skip (not in a numbered category folder): {rel}")
            stats["skipped"] += 1
            continue
        seen.add(str(rel))
        sha = _sha256(path)
        row = db.execute("SELECT id, sha256, category FROM sources WHERE rel_path = ?",
                         (str(rel),)).fetchone()
        if row and row["sha256"] == sha and row["category"] == category:
            stats["unchanged"] += 1
            continue
        if row:
            delete_source(db, row["id"])
        log(f"{'re-indexing' if row else 'indexing'} {rel}")
        index_file(db, path, rel, category, sha, log)
        db.commit()
        stats["updated" if row else "added"] += 1

    for row in db.execute("SELECT id, rel_path FROM sources").fetchall():
        if row["rel_path"] not in seen:
            log(f"removing (file gone): {row['rel_path']}")
            delete_source(db, row["id"])
            stats["removed"] += 1
    db.commit()
    return stats


if __name__ == "__main__":
    # --rebuild: drop the index and re-index everything (e.g. after a parser change)
    args = [a for a in sys.argv[1:] if a != "--rebuild"]
    if "--rebuild" in sys.argv:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB_PATH}{suffix}").unlink(missing_ok=True)
    print(run(Path(args[0]).expanduser() if args else LIBRARY_ROOT))

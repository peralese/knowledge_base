"""Index everything under LIBRARY_ROOT.

Category comes from the top-level folder ("4 - Data, AI & ..." -> 4).
Unchanged files are skipped (same size and mtime, else same sha256); changed
files are re-indexed; files that disappeared are removed from the index, unless
so many look gone that the share is probably half-mounted.

  python indexer.py            index new/changed files (prints progress)
  python indexer.py --rebuild  drop the index and re-index everything
  python indexer.py --status   counts, last runs and files that failed
  python indexer.py --auto     unattended run for launchd: exits quietly when
                               the NAS or Ollama is unavailable, logs to
                               logs/indexer.log, notifies on changes
  --allow-removals             remove more than MAX_REMOVALS gone files
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import sqlite_vec

from embed import OLLAMA_URL, embed_documents
from parse import parse, split_passages
from store import DB_PATH, LIBRARY_ROOT, connect, delete_source

SUFFIXES = {".epub", ".html", ".htm", ".md"}
MAX_REMOVALS = 5  # more files gone than this in one run -> hold removals back
LOG_PATH = Path(__file__).resolve().parent / "logs" / "indexer.log"


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



def run(root: Path = LIBRARY_ROOT, log=print, db: sqlite3.Connection | None = None,
        allow_removals: bool = False) -> dict:
    if not root.exists():
        raise SystemExit(f"Library folder not found: {root} (is the NAS mounted?)")
    db = db or connect()
    started = datetime.now().isoformat(sep=" ", timespec="seconds")
    seen = set()
    stats = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0, "skipped": 0,
             "failed": 0, "held": 0}
    changed: list[str] = []   # titles added or updated, for the notification
    failed: list[str] = []    # files that failed this run (not previously known)
    note = None
    for path in discover(root):
        rel = path.relative_to(root)
        category = _category(rel)
        if category is None:
            log(f"  skip (not in a numbered category folder): {rel}")
            stats["skipped"] += 1
            continue
        seen.add(str(rel))
        st = path.stat()
        row = db.execute("SELECT id, sha256, category, size, mtime FROM sources "
                         "WHERE rel_path = ?", (str(rel),)).fetchone()
        if (row and row["category"] == category
                and row["size"] == st.st_size and row["mtime"] == st.st_mtime):
            stats["unchanged"] += 1
            continue
        known_fail = db.execute("SELECT 1 FROM failures WHERE rel_path = ? AND size = ? "
                                "AND mtime = ?", (str(rel), st.st_size, st.st_mtime)).fetchone()
        if known_fail:
            stats["failed"] += 1
            continue
        sha = _sha256(path)
        if row and row["sha256"] == sha and row["category"] == category:
            # Same content, new mtime (or size/mtime not recorded yet).
            db.execute("UPDATE sources SET size = ?, mtime = ? WHERE id = ?",
                       (st.st_size, st.st_mtime, row["id"]))
            db.commit()
            stats["unchanged"] += 1
            continue
        if row:
            delete_source(db, row["id"])
        log(f"{'re-indexing' if row else 'indexing'} {rel}")
        try:
            index_file(db, path, rel, category, sha, log)
        except httpx.HTTPError:
            db.rollback()
            raise  # Ollama trouble: stop the run, every file would fail
        except Exception as e:  # a book that won't parse shouldn't stop the rest
            db.rollback()
            err = f"{type(e).__name__}: {e}"
            log(f"  FAILED {rel}: {err}")
            db.execute("INSERT OR REPLACE INTO failures (rel_path, size, mtime, error) "
                       "VALUES (?, ?, ?, ?)", (str(rel), st.st_size, st.st_mtime, err))
            db.commit()
            stats["failed"] += 1
            failed.append(rel.name)
            continue
        db.execute("UPDATE sources SET size = ?, mtime = ? WHERE rel_path = ?",
                   (st.st_size, st.st_mtime, str(rel)))
        db.execute("DELETE FROM failures WHERE rel_path = ?", (str(rel),))
        db.commit()
        stats["updated" if row else "added"] += 1
        changed.append(db.execute("SELECT title FROM sources WHERE rel_path = ?",
                                  (str(rel),)).fetchone()["title"])

    gone = [r for r in db.execute("SELECT id, rel_path FROM sources").fetchall()
            if r["rel_path"] not in seen]
    if len(gone) > MAX_REMOVALS and not allow_removals:
        # A half-mounted or emptied share looks exactly like deleted books.
        note = (f"held back removing {len(gone)} sources whose files look gone "
                f"(limit {MAX_REMOVALS}); check the NAS, then run "
                f"`indexer.py --allow-removals` if they really were deleted")
        log(f"WARNING: {note}")
        stats["held"] = len(gone)
    else:
        for r in gone:
            log(f"removing (file gone): {r['rel_path']}")
            delete_source(db, r["id"])
            stats["removed"] += 1
    db.execute("DELETE FROM failures WHERE rel_path NOT IN (%s)"
               % ",".join("?" * len(seen)) if seen else "DELETE FROM failures",
               tuple(seen))
    db.execute("INSERT INTO runs (started_at, finished_at, stats, note) VALUES (?, ?, ?, ?)",
               (started, datetime.now().isoformat(sep=" ", timespec="seconds"),
                json.dumps(stats), note))
    db.commit()
    stats["_changed"], stats["_failed"], stats["_note"] = changed, failed, note
    return stats


# ------------------------------------------------------------------ helpers

class Locked(Exception):
    pass


def lock(path: Path = DB_PATH.parent / ".indexer.lock"):
    """Hold an exclusive lock so a manual and a scheduled run never overlap."""
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise Locked(f"another indexer run holds {path}")
    return f  # keep it open; the lock lasts until the process exits


def ollama_up() -> bool:
    try:
        return httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5).is_success
    except httpx.HTTPError:
        return False


def notify(message: str, title: str = "Reference library") -> None:
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    subprocess.run(["/usr/bin/osascript", "-e", script], check=False,
                   capture_output=True)


def summary(stats: dict) -> str | None:
    """One-line notification text, or None when nothing worth telling happened."""
    parts = []
    if stats["_changed"]:
        names = ", ".join(stats["_changed"][:3])
        more = f" +{len(stats['_changed']) - 3} more" if len(stats["_changed"]) > 3 else ""
        parts.append(f"Indexed {len(stats['_changed'])}: {names}{more}")
    if stats["removed"]:
        parts.append(f"removed {stats['removed']}")
    if stats["_failed"]:
        parts.append(f"FAILED: {', '.join(stats['_failed'])}")
    if stats["_note"]:
        parts.append(f"held back {stats['held']} removals — check the NAS")
    return "; ".join(parts) or None


def status(db: sqlite3.Connection | None = None) -> str:
    db = db or connect()
    out = []
    for r in db.execute("SELECT kind, count(*) n FROM sources GROUP BY kind"):
        out.append(f"{r['n']} {r['kind']}s")
    n = db.execute("SELECT count(*) FROM passages").fetchone()[0]
    lines = [f"Index: {', '.join(out) or 'empty'}; {n} passages ({DB_PATH})"]
    for r in db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5"):
        st = {k: v for k, v in json.loads(r["stats"]).items() if v}
        lines.append(f"  run {r['finished_at']}: {st}" + (f" — {r['note']}" if r["note"] else ""))
    fails = db.execute("SELECT * FROM failures ORDER BY failed_at").fetchall()
    if fails:
        lines.append("Failed (retried when the file changes):")
        lines += [f"  {f['rel_path']}: {f['error']}" for f in fails]
    return "\n".join(lines)


def auto() -> int:
    """Unattended run (launchd): skip quietly when prerequisites are missing."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logf = LOG_PATH.open("a")

    def log(msg: str) -> None:
        logf.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
        logf.flush()

    if not LIBRARY_ROOT.exists():
        log(f"skip: {LIBRARY_ROOT} not mounted")
        return 0
    try:
        if not any(LIBRARY_ROOT.iterdir()):
            log(f"skip: {LIBRARY_ROOT} is empty (half-mounted?)")
            return 0
    except OSError as e:
        # Under launchd, macOS privacy controls block network volumes unless
        # the Python binary has Full Disk Access; no dialog is ever shown.
        log(f"skip: can't read {LIBRARY_ROOT}: {e}")
        notify("Can't read the NAS. Give Python Full Disk Access "
               "(see README, Automatic indexing).")
        return 0
    if not ollama_up():
        log(f"skip: Ollama not reachable at {OLLAMA_URL}")
        return 0
    try:
        held = lock()
    except Locked as e:
        log(f"skip: {e}")
        return 0
    try:
        stats = run(log=log)
    except httpx.HTTPError as e:
        log(f"aborted: Ollama error mid-run: {e}")
        notify(f"Indexing stopped: Ollama error ({type(e).__name__})")
        return 1
    finally:
        held.close()
    log(f"done: { {k: v for k, v in stats.items() if not k.startswith('_') and v} }")
    if msg := summary(stats):
        notify(msg)
    return 0


if __name__ == "__main__":
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--status" in flags:
        print(status())
        sys.exit(0)
    if "--auto" in flags:
        sys.exit(auto())
    try:
        held = lock()
    except Locked as e:
        sys.exit(str(e))
    # --rebuild: drop the index and re-index everything (e.g. after a parser change)
    if "--rebuild" in flags:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB_PATH}{suffix}").unlink(missing_ok=True)
    stats = run(Path(args[0]).expanduser() if args else LIBRARY_ROOT,
                allow_removals="--allow-removals" in flags)
    print({k: v for k, v in stats.items() if not k.startswith("_")})

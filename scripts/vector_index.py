"""2D-2 — Vector Index for semantic search over compiled notes.

Implementation notes:
- Storage: stdlib sqlite3 with JSON-encoded embeddings. No new pip dependencies
  needed at the current corpus size (~37 notes). Pure Python cosine similarity
  is fast enough (<1ms for <200 vectors).
- Embedding model: nomic-embed-text via Ollama's /api/embeddings endpoint.
  Requires: ollama pull nomic-embed-text
- Index location: outputs/vector_index.db
- Staleness threshold: 7 days (checked by query.py for graceful degradation)

Why sqlite-vec was not used: sqlite-vec is not installed in this environment
and the corpus is too small to warrant it. stdlib sqlite3 + JSON is a better
fit for <1000 vectors, zero dependencies, and full portability.

Why FAISS was not used: FAISS requires pip install faiss-cpu (not installed),
adds complexity, and provides no benefit below ~5000 vectors. At 3x corpus
growth (111 notes), pure Python cosine similarity remains under 1ms.

Usage:
    python3 scripts/vector_index.py build
    python3 scripts/vector_index.py update
    python3 scripts/vector_index.py search "semantic memory in agents"
    python3 scripts/vector_index.py stats
    python3 scripts/vector_index.py --embedding-model qwen2.5:7b build
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
OLLAMA_BASE_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
INDEX_DB_PATH = ROOT / "outputs" / "vector_index.db"
STALENESS_DAYS = 7


# ---------------------------------------------------------------------------
# Content eligibility
# ---------------------------------------------------------------------------

_STUB_PATTERNS = [
    "description not yet written",
    "_description not yet written_",
    "update this stub",
    "stub note",
]


def is_stub(body: str) -> bool:
    """Return True if this note body has no substantive content worth embedding."""
    stripped = body.strip()
    if len(stripped) < 150:
        return True
    lower = stripped.lower()
    return any(p in lower for p in _STUB_PATTERNS)


def _strip_frontmatter(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return normalized.strip()
    parts = normalized.split("\n---\n", 1)
    return parts[1].strip() if len(parts) == 2 else normalized.strip()


def _note_type(path: Path, root: Path) -> str | None:
    """Return the note type string or None if the note should not be indexed."""
    rel = path.relative_to(root)
    parts = rel.parts
    if len(parts) < 2:
        return None
    parent = parts[-2]
    if parent == "topics":
        return "topic"
    if parent == "concepts":
        return "concept"
    if parent == "entities":
        return "entity"
    if parent == "source_summaries":
        return "source_summary"
    return None


def _eligible_notes(root: Path) -> list[tuple[Path, str]]:
    """Return list of (path, note_type) for all notes eligible for indexing.

    Excludes stub concept notes and unapproved source summaries.
    """
    eligible: list[tuple[Path, str]] = []
    dirs = [
        (root / "compiled" / "topics", "topic"),
        (root / "compiled" / "concepts", "concept"),
        (root / "compiled" / "entities", "entity"),
        (root / "compiled" / "source_summaries", "source_summary"),
    ]
    for directory, note_type in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            body = _strip_frontmatter(text)
            if note_type == "concept" and is_stub(body):
                continue
            if note_type == "source_summary" and "approved: true" not in text:
                continue
            eligible.append((path, note_type))
    return eligible


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Ollama embeddings
# ---------------------------------------------------------------------------

def _check_embed_model_available(model: str) -> None:
    """Raise a clear error if the embedding model is not pulled."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except URLError as exc:
        raise ConnectionError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. Is it running?\n"
            "  Start with: ollama serve"
        ) from exc

    available = [m.get("name", "") for m in data.get("models", [])]
    if model not in available:
        available_str = ", ".join(available) if available else "(none pulled)"
        raise ValueError(
            f"Embedding model '{model}' is not available in Ollama.\n"
            f"  Available: {available_str}\n"
            f"  Pull with: ollama pull {model}\n\n"
            "  nomic-embed-text is the recommended embedding model for this project:\n"
            "    ollama pull nomic-embed-text"
        )


def call_ollama_embeddings(text: str, model: str = EMBED_MODEL) -> list[float]:
    """Generate an embedding vector for text using Ollama."""
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    # Handle both /api/embeddings (list[float]) and /api/embed (list[list[float]])
    result = data.get("embedding") or data.get("embeddings", [])
    if isinstance(result, list) and result and isinstance(result[0], list):
        return result[0]
    return result


# ---------------------------------------------------------------------------
# Cosine similarity — pure Python, no numpy
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# SQLite index management
# ---------------------------------------------------------------------------

def _open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS note_embeddings (
            id TEXT PRIMARY KEY,
            note_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedded_at TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM index_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)", (key, value)
    )


def _note_id(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _load_all_embeddings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, note_type, file_path, content_hash, embedding FROM note_embeddings"
    ).fetchall()
    results = []
    for row in rows:
        try:
            embedding = json.loads(row[4])
        except (json.JSONDecodeError, TypeError):
            continue
        results.append({
            "id": row[0],
            "note_type": row[1],
            "file_path": row[2],
            "content_hash": row[3],
            "embedding": embedding,
        })
    return results


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_build(root: Path, model: str, db_path: Path) -> int:
    """Embed all eligible notes and build a fresh index."""
    _check_embed_model_available(model)

    notes = _eligible_notes(root)
    if not notes:
        print("No eligible notes found. Run the pipeline first.", file=sys.stderr)
        return 1

    print(f"Building vector index — {len(notes)} eligible notes")
    print(f"Model: {model}")
    print(f"Index: {db_path}")

    conn = _open_db(db_path)
    conn.execute("DELETE FROM note_embeddings")
    conn.execute("DELETE FROM index_meta")

    now = datetime.now(timezone.utc).isoformat()
    success = 0
    for i, (path, note_type) in enumerate(notes, 1):
        text = path.read_text(encoding="utf-8", errors="replace")
        body = _strip_frontmatter(text)
        note_id = _note_id(path, root)
        h = _content_hash(text)

        print(f"  [{i}/{len(notes)}] {path.name}", end=" ", flush=True)
        t0 = time.perf_counter()
        try:
            embedding = call_ollama_embeddings(body[:4000], model)
        except Exception as exc:
            print(f"FAILED: {exc}")
            continue
        elapsed = time.perf_counter() - t0

        conn.execute(
            "INSERT OR REPLACE INTO note_embeddings "
            "(id, note_type, file_path, content_hash, embedded_at, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (note_id, note_type, str(path), h, now, json.dumps(embedding)),
        )
        print(f"({elapsed:.1f}s, {len(embedding)}d)")
        success += 1

    _set_meta(conn, "last_built", now)
    _set_meta(conn, "model", model)
    conn.commit()
    conn.close()

    print(f"\nIndexed {success}/{len(notes)} notes. Index saved: {db_path}")
    return 0 if success > 0 else 1


def cmd_update(root: Path, model: str, db_path: Path) -> int:
    """Re-embed only notes that have changed or are missing from the index."""
    _check_embed_model_available(model)

    notes = _eligible_notes(root)
    conn = _open_db(db_path)

    # Load existing hashes
    existing = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT id, content_hash FROM note_embeddings"
        ).fetchall()
    }

    # Determine which notes exist in the eligible set
    eligible_ids = set()
    to_embed: list[tuple[Path, str]] = []
    now = datetime.now(timezone.utc).isoformat()

    for path, note_type in notes:
        note_id = _note_id(path, root)
        eligible_ids.add(note_id)
        text = path.read_text(encoding="utf-8", errors="replace")
        h = _content_hash(text)
        if note_id not in existing or existing[note_id] != h:
            to_embed.append((path, note_type))

    # Remove stale entries (notes that no longer exist)
    stale = [nid for nid in existing if nid not in eligible_ids]
    for nid in stale:
        conn.execute("DELETE FROM note_embeddings WHERE id = ?", (nid,))
    if stale:
        print(f"Removed {len(stale)} stale entries.")

    if not to_embed:
        print("Vector index is up to date. No notes to re-embed.")
        _set_meta(conn, "last_built", now)
        conn.commit()
        conn.close()
        return 0

    print(f"Updating vector index — {len(to_embed)} note(s) to embed (model: {model})")
    success = 0
    for i, (path, note_type) in enumerate(to_embed, 1):
        text = path.read_text(encoding="utf-8", errors="replace")
        body = _strip_frontmatter(text)
        note_id = _note_id(path, root)
        h = _content_hash(text)

        print(f"  [{i}/{len(to_embed)}] {path.name}", end=" ", flush=True)
        t0 = time.perf_counter()
        try:
            embedding = call_ollama_embeddings(body[:4000], model)
        except Exception as exc:
            print(f"FAILED: {exc}")
            continue
        elapsed = time.perf_counter() - t0

        conn.execute(
            "INSERT OR REPLACE INTO note_embeddings "
            "(id, note_type, file_path, content_hash, embedded_at, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (note_id, note_type, str(path), h, now, json.dumps(embedding)),
        )
        print(f"({elapsed:.1f}s)")
        success += 1

    _set_meta(conn, "last_built", now)
    _set_meta(conn, "model", model)
    conn.commit()
    conn.close()

    print(f"\nUpdated {success}/{len(to_embed)} note(s).")
    return 0


def cmd_search(query: str, root: Path, model: str, db_path: Path, top_n: int = 5) -> int:
    """Search the vector index with a natural language query."""
    if not db_path.exists():
        print("Vector index not found. Run: python3 scripts/vector_index.py build", file=sys.stderr)
        return 1

    _check_embed_model_available(model)

    print(f"Generating query embedding ({model})...", end=" ", flush=True)
    t0 = time.perf_counter()
    query_embedding = call_ollama_embeddings(query, model)
    print(f"{(time.perf_counter() - t0) * 1000:.0f}ms")

    conn = _open_db(db_path)
    entries = _load_all_embeddings(conn)
    conn.close()

    if not entries:
        print("Vector index is empty. Run: python3 scripts/vector_index.py build")
        return 0

    t0 = time.perf_counter()
    scored = [
        (entry, cosine_similarity(query_embedding, entry["embedding"]))
        for entry in entries
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    search_ms = (time.perf_counter() - t0) * 1000

    print(f"\nVector search results for: {query!r}  ({search_ms:.1f}ms)\n")
    for rank, (entry, score) in enumerate(scored[:top_n], 1):
        path_rel = entry["id"]
        note_type = entry["note_type"]
        print(f"  {rank}. [{note_type}] {Path(path_rel).stem}  (similarity: {score:.4f})")

    return 0


def cmd_stats(root: Path, db_path: Path) -> int:
    """Show vector index statistics."""
    eligible = _eligible_notes(root)
    if not db_path.exists():
        print("Vector index not found. Run: python3 scripts/vector_index.py build")
        print(f"Eligible notes: {len(eligible)}")
        return 0

    conn = _open_db(db_path)
    total_indexed = conn.execute("SELECT COUNT(*) FROM note_embeddings").fetchone()[0]
    by_type = conn.execute(
        "SELECT note_type, COUNT(*) FROM note_embeddings GROUP BY note_type"
    ).fetchall()
    last_built = _get_meta(conn, "last_built")
    model = _get_meta(conn, "model")
    conn.close()

    db_size_kb = db_path.stat().st_size // 1024

    print(f"Vector Index Stats")
    print(f"  Index file    : {db_path}  ({db_size_kb} KB)")
    print(f"  Last built    : {last_built or 'unknown'}")
    print(f"  Model         : {model or 'unknown'}")
    print(f"  Total indexed : {total_indexed} / {len(eligible)} eligible notes")
    print(f"  By type:")
    for note_type, count in sorted(by_type):
        print(f"    {note_type:<20} {count}")

    # Check staleness
    if last_built:
        try:
            from datetime import timezone as tz  # noqa: PLC0415
            built_dt = datetime.fromisoformat(last_built)
            if built_dt.tzinfo is None:
                built_dt = built_dt.replace(tzinfo=tz.utc)
            age_days = (datetime.now(tz.utc) - built_dt).days
            if age_days >= STALENESS_DAYS:
                print(f"\n  WARNING: index is {age_days} days old (threshold: {STALENESS_DAYS} days)")
                print("  Run: python3 scripts/vector_index.py update")
        except (ValueError, AttributeError):
            pass

    return 0


# ---------------------------------------------------------------------------
# Index freshness check (for use by query.py)
# ---------------------------------------------------------------------------

def index_is_fresh(db_path: Path = INDEX_DB_PATH, max_age_days: int = STALENESS_DAYS) -> bool:
    """Return True if the vector index exists and was built within max_age_days."""
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT value FROM index_meta WHERE key = 'last_built'"
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM note_embeddings").fetchone()[0]
        conn.close()
        if not row or count == 0:
            return False
        built_dt = datetime.fromisoformat(row[0])
        if built_dt.tzinfo is None:
            built_dt = built_dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - built_dt).days
        return age_days < max_age_days
    except Exception:
        return False


def vector_search(
    query_embedding: list[float],
    db_path: Path = INDEX_DB_PATH,
    top_n: int = 10,
) -> list[tuple[str, str, float]]:
    """Search the vector index with a pre-computed query embedding.

    Returns list of (note_id, note_type, similarity_score) sorted desc by score.
    Fast: pure Python cosine similarity over <200 vectors completes in <1ms.
    """
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        entries = _load_all_embeddings(conn)
        conn.close()
    except Exception:
        return []

    t0 = time.perf_counter()
    scored = [
        (entry["id"], entry["note_type"], cosine_similarity(query_embedding, entry["embedding"]))
        for entry in entries
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Log if over budget (should not happen at this corpus size)
    if elapsed_ms > 200:
        sys.stderr.write(f"Warning: vector search took {elapsed_ms:.0f}ms (target: <200ms)\n")

    return [(nid, ntype, score) for nid, ntype, score in scored[:top_n] if score > 0]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2D-2 Vector Index: manage the local semantic search index over compiled notes."
    )
    parser.add_argument(
        "--embedding-model",
        default=EMBED_MODEL,
        dest="embedding_model",
        help=f"Ollama embedding model. Default: {EMBED_MODEL}. "
             "Install with: ollama pull nomic-embed-text",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=INDEX_DB_PATH,
        help=f"Path to the SQLite index file. Default: {INDEX_DB_PATH}",
    )

    subs = parser.add_subparsers(dest="command")

    subs.add_parser("build", help="Embed all eligible notes and build a fresh index.")
    subs.add_parser("update", help="Re-embed only changed or new notes.")

    search_p = subs.add_parser("search", help="Search the index with a query string.")
    search_p.add_argument("query", help="Natural language query.")
    search_p.add_argument("--top-n", type=int, default=5, dest="top_n")

    subs.add_parser("stats", help="Show index statistics and staleness.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    model = getattr(args, "embedding_model", EMBED_MODEL)
    db_path = getattr(args, "db", INDEX_DB_PATH)

    if args.command == "build":
        return cmd_build(ROOT, model, db_path)
    if args.command == "update":
        return cmd_update(ROOT, model, db_path)
    if args.command == "search":
        return cmd_search(args.query, ROOT, model, db_path, top_n=args.top_n)
    if args.command == "stats":
        return cmd_stats(ROOT, db_path)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

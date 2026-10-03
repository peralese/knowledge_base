"""Hybrid search: FTS5 (exact words) + sqlite-vec (meaning), fused with RRF."""
from __future__ import annotations

import re
import sqlite3

import sqlite_vec

from embed import embed_query

RRF_K = 60
CANDIDATES = 50
MAX_PER_SECTION = 2

STOPWORDS = set("""a an and are as at be but by do does for from how i in into is it
its of on or so that the their there these this to was what when where which who
why will with you your can should would could my me we our about vs versus""".split())


def fts_query(q: str) -> str | None:
    """User text -> FTS5 query. Quoted phrases are kept; other words are OR'd."""
    phrases = re.findall(r'"([^"]+)"', q)
    rest = re.sub(r'"[^"]*"', " ", q)
    words = [w for w in re.findall(r"[\w][\w\-\.]*", rest.lower())
             if w not in STOPWORDS and len(w) > 1]
    terms = [f'"{p}"' for p in phrases] + [f'"{w.strip(".-")}"' for w in words if w.strip(".-")]
    return " OR ".join(dict.fromkeys(terms)) or None


def _fts(db, q, category, n):
    fq = fts_query(q)
    if not fq:
        return []
    sql = ("SELECT f.rowid FROM passages_fts f JOIN passages p ON p.id = f.rowid "
           "JOIN sources s ON s.id = p.source_id WHERE passages_fts MATCH ?")
    args: list = [fq]
    if category:
        sql += " AND s.category = ?"
        args.append(category)
    sql += " ORDER BY bm25(passages_fts, 1.0, 0.5) LIMIT ?"
    args.append(n)
    return [r[0] for r in db.execute(sql, args)]


def _vec(db, q, category, n):
    vec = sqlite_vec.serialize_float32(embed_query(q))
    sql = "SELECT passage_id FROM passages_vec WHERE embedding MATCH ? AND k = ?"
    args: list = [vec, n]
    if category:
        sql += " AND category = ?"
        args.append(category)
    return [r[0] for r in db.execute(sql + " ORDER BY distance", args)]


def search(db: sqlite3.Connection, query: str, category: int | None = None,
           source: str | None = None, limit: int = 8) -> list[dict]:
    n = CANDIDATES * (4 if source else 1)  # filter by source after fusion
    scores: dict[int, float] = {}
    for ranked in (_fts(db, query, category, n), _vec(db, query, category, n)):
        for rank, pid in enumerate(ranked):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (RRF_K + rank + 1)
    if not scores:
        return []
    ordered = sorted(scores, key=scores.get, reverse=True)
    marks = ",".join("?" * len(ordered))
    rows = {r["id"]: r for r in db.execute(
        f"SELECT p.id, p.text, p.section_id, sec.path, sec.chapter, s.title, s.authors, "
        f"s.category, s.kind, s.url FROM passages p JOIN sections sec ON sec.id = p.section_id "
        f"JOIN sources s ON s.id = p.source_id WHERE p.id IN ({marks})", ordered)}
    out = []
    per_section: dict[int, int] = {}
    for pid in ordered:
        r = rows[pid]
        if source and source.lower() not in r["title"].lower():
            continue
        # leave room for other sections; read_section gets the rest
        if per_section.get(r["section_id"], 0) >= MAX_PER_SECTION:
            continue
        per_section[r["section_id"]] = per_section.get(r["section_id"], 0) + 1
        out.append({**dict(r), "score": round(scores[pid], 4)})
        if len(out) >= limit:
            break
    return out


def read_section(db: sqlite3.Connection, section_id: int, max_words: int = 6000) -> dict | None:
    r = db.execute(
        "SELECT sec.id, sec.path, sec.chapter, sec.text, sec.ord, sec.source_id, s.title, s.authors, s.url "
        "FROM sections sec JOIN sources s ON s.id = sec.source_id WHERE sec.id = ?",
        (section_id,)).fetchone()
    if not r:
        return None
    out = dict(r)
    words = out["text"].split(" ")
    if len(out["text"].split()) > max_words:
        out["text"] = " ".join(words[:max_words]) + "\n\n[... section truncated ...]"
        out["truncated"] = True
    # neighbours, so the caller can keep reading
    nb = db.execute("SELECT id, path FROM sections WHERE source_id = ? AND ord IN (?, ?) ORDER BY ord",
                    (r["source_id"], r["ord"] - 1, r["ord"] + 1)).fetchall()
    out["previous"] = next(({"section_id": x["id"], "path": x["path"]} for x in nb if x["id"] < r["id"]), None)
    out["next"] = next(({"section_id": x["id"], "path": x["path"]} for x in nb if x["id"] > r["id"]), None)
    del out["ord"], out["source_id"]
    return out

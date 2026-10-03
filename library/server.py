"""MCP server for the reference library (stdio).

Register once, at user level:
  claude mcp add --scope user reference-library -- \\
      <repo>/library/.venv/bin/python <repo>/library/server.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

import search as lib  # noqa: E402
from store import CATEGORIES, connect  # noqa: E402

INSTRUCTIONS = """\
The user's personal reference library: full text of technical books and lasting
engineering articles they own, split into citable passages.

Use `search` BEFORE answering questions about software/enterprise architecture,
system design, ML/AI engineering, data, security, cloud/infrastructure, APIs and
integration, or developer tooling (e.g. git) — and when the user is reading or
studying one of these books. Search once or twice with different phrasings; use
`read_section` when a passage is relevant but cut short.

When a passage informs your answer, cite it inline as
(Title, Chapter > Section). Say when the library has nothing relevant rather than
implying it does. Your own knowledge still applies; the library adds the user's
sources, it doesn't replace reasoning.
"""

server = MCPServer("reference-library", instructions=INSTRUCTIONS)
_db = None


def db():
    global _db
    if _db is None:
        _db = connect()
    return _db


@server.tool()
def search(query: str, category: int | None = None, source: str | None = None,
           limit: int = 8) -> str:
    """Search the library by meaning and exact words.

    query: a natural-language question or keywords; put exact phrases or
      commands in double quotes, e.g. '"git rebase --onto"'.
    category: optional filter. 1 = Enterprise & Software; 2 = Cloud, Platform &
      Infrastructure Engineering; 3 = Integration, APIs & Automation; 4 = Data,
      AI & Machine Learning Engineering; 5 = Cybersecurity & Security
      Architecture; 6 = AI Strategy, Society & Emerging Technology;
      7 = Developer & Systems Reference.
    source: optional case-insensitive substring of a book/article title.
    limit: number of passages (default 8, max 20).
    """
    results = lib.search(db(), query, category=category, source=source,
                         limit=max(1, min(limit, 20)))
    if not results:
        return "No matching passages in the library."
    parts = []
    for i, r in enumerate(results, 1):
        cite = f"{r['title']} — {r['path']}"
        head = f"[{i}] {cite}\n    (section_id={r['section_id']}, category={r['category']}"
        head += f", url={r['url']})" if r["url"] else ")"
        parts.append(f"{head}\n\n{r['text']}")
    return "\n\n---\n\n".join(parts)



@server.tool()
def read_section(section_id: int) -> str:
    """Read the full text of one section (from a search result's section_id).

    Returns the section plus the ids of the previous and next sections, so you
    can keep reading.
    """
    s = lib.read_section(db(), section_id)
    if not s:
        return f"No section with id {section_id}."
    nav = []
    if s["previous"]:
        nav.append(f"previous: section_id={s['previous']['section_id']} ({s['previous']['path']})")
    if s["next"]:
        nav.append(f"next: section_id={s['next']['section_id']} ({s['next']['path']})")
    return f"{s['title']} — {s['path']}\n\n{s['text']}\n\n" + "\n".join(nav)


@server.tool()
def list_sources(category: int | None = None) -> str:
    """List the books and articles in the library, grouped by category."""
    sql = ("SELECT s.title, s.authors, s.category, s.kind, s.url, COUNT(p.id) AS n "
           "FROM sources s LEFT JOIN passages p ON p.source_id = s.id")
    args = []
    if category:
        sql += " WHERE s.category = ?"
        args.append(category)
    rows = db().execute(sql + " GROUP BY s.id ORDER BY s.category, s.title", args).fetchall()
    if not rows:
        return "The library is empty."
    out, last = [], None
    for r in rows:
        if r["category"] != last:
            out.append(f"\n## {r['category']}. {CATEGORIES.get(r['category'], '?')}")
            last = r["category"]
        by = f" — {r['authors']}" if r["authors"] else ""
        out.append(f"- {r['title']}{by} ({r['kind']}, {r['n']} passages)")
    return "\n".join(out).strip()


if __name__ == "__main__":
    server.run()

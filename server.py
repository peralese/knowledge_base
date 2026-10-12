"""MCP server for the reference library (stdio).

Register once, at user level:
  claude mcp add --scope user reference-library -- \\
      <repo>/.venv/bin/python <repo>/server.py

Every tool call is logged to data/usage.db (see usage.py) with the directory of
the Claude Code session, so `indexer.py --status` shows whether it's used.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

import add_url  # noqa: E402
import indexer  # noqa: E402
import notes  # noqa: E402
import search as lib  # noqa: E402
import usage  # noqa: E402
from store import CATEGORIES, LIBRARY_ROOT, connect  # noqa: E402

INSTRUCTIONS = """\
The user's personal reference library: full text of the technical books and
lasting engineering articles they own, plus their saved notes, split into
citable passages.

Search it (`search`, 1-3 phrasings) at these moments:
- choosing between designs, patterns, technologies or trade-offs;
- writing or reviewing architecture docs, ADRs, design write-ups or the
  architecture part of a README;
- questions on distributed systems, microservices, APIs and integration, data
  and ML, LLMs and agents, security, cloud, Linux, the shell or git;
- whenever the user is reading or discussing one of their books.
Don't search for routine code mechanics that the code in front of you answers.

Use `read_section` when a passage is relevant but cut short. When a passage
informs your answer, cite it inline as (Title, Chapter > Section). Say when the
library has nothing relevant rather than implying it does. Your own knowledge
still applies; the library adds the user's sources.

Reading with the user: `outline` gives a book's chapters (and a chapter's
sections) with section_ids. Use it to preview a chapter before they read it,
then `read_section` to explain parts in terms of their work or compare with
other books. Keep no progress records.

Saving: when the user says "save this as a note", "keep this" or similar about
a snippet, use `save_note`; for a web page worth keeping, `add_article`. Both
index immediately.
"""

server = MCPServer("reference-library", instructions=INSTRUCTIONS)
_db = None
PROJECT = usage.project_name()  # the Claude Code session's directory


def db():
    global _db
    if _db is None:
        _db = connect()
    return _db


def _log(tool: str, arg, hits: list[str] | None = None) -> None:
    usage.log_call(tool, None if arg is None else str(arg), hits, project=PROJECT)


def _stderr(msg: str) -> None:
    # stdout carries the MCP protocol; progress goes to stderr
    print(msg, file=sys.stderr)


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
    _log("search", query, [r["title"] for r in results[:3]])
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
    _log("read_section", section_id, [s["title"]] if s else None)
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
    _log("list_sources", category)
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


def outline_text(conn, source: str, chapter: str | None = None) -> str:
    matches = conn.execute("SELECT id, title FROM sources WHERE title LIKE ? ORDER BY title",
                           (f"%{source}%",)).fetchall()
    if not matches:
        return f"No book or article matching {source!r}. Use list_sources to see titles."
    exact = [m for m in matches if m["title"].lower() == source.lower()]
    if len(matches) > 1 and not exact:
        return "Several matches; be more specific:\n" + "\n".join(f"- {m['title']}" for m in matches)
    src = (exact or matches)[0]
    rows = conn.execute(
        "SELECT sec.id, sec.chapter, sec.path, COUNT(p.id) AS n FROM sections sec "
        "LEFT JOIN passages p ON p.section_id = sec.id WHERE sec.source_id = ? "
        "GROUP BY sec.id ORDER BY sec.ord", (src["id"],)).fetchall()
    if chapter is None:
        out, seen = [f"{src['title']} — chapters (section_id of each chapter's start, passages):"], {}
        for r in rows:
            if r["chapter"] not in seen:
                seen[r["chapter"]] = [r["id"], 0]
            seen[r["chapter"]][1] += r["n"]
        out += [f"- {ch}  (section_id={sid}, {n} passages)" for ch, (sid, n) in seen.items()]
        out.append("Call outline(source, chapter=...) for a chapter's sections.")
        return "\n".join(out)
    sel = [r for r in rows if chapter.lower() in r["chapter"].lower()]
    if not sel:
        return f"No chapter matching {chapter!r} in {src['title']}."
    out = [f"{src['title']} — {sel[0]['chapter']}:"]
    for r in sel:
        depth = r["path"].count(" > ")
        out.append(f"{'  ' * depth}- {r['path'].split(' > ')[-1]}  (section_id={r['id']})")
    return "\n".join(out)


@server.tool()
def outline(source: str, chapter: str | None = None) -> str:
    """A book's table of contents, for reading it with the user.

    source: title or part of it (see list_sources).
    chapter: optional part of a chapter title; returns that chapter's sections
      with section_ids for read_section. Without it, lists the chapters.
    """
    _log("outline", f"{source} | {chapter}" if chapter else source)
    return outline_text(db(), source, chapter)


@server.tool()
def save_note(topic: str, heading: str, body: str, source: str, category: int) -> str:
    """Save a short snippet (command switch, setup trick, how-to) as a note.

    topic: the notes file, e.g. "Claude Code Tips" or "Git Tips"; reuse an
      existing topic when one fits (search or list_sources to see them).
    heading: what the snippet does, e.g. "Resume sessions after a reboot".
    body: the snippet written as a reference: commands in backticks, short
      bullets.
    source: where it came from (link or description) and whether it was verified.
    category: 1-7 as in search (most tool tips are 7).
    The note is indexed immediately and becomes searchable.
    """
    _log("save_note", f"{topic} | {heading}")
    try:
        path, created = notes.append_note(category, topic, heading, body, source)
        outcome, detail = indexer.index_path(path, log=_stderr)
    except Exception as e:
        return f"Could not save the note: {type(e).__name__}: {e}"
    where = path.relative_to(LIBRARY_ROOT)
    if outcome == "failed":
        return f"Saved to {where}, but indexing failed: {detail}"
    return f"Saved to {where} ({'new topic file' if created else 'appended'}); indexed."


@server.tool()
def add_article(url: str, category: int) -> str:
    """Save a web article worth keeping as reference (not news) and index it.

    url: the page to fetch. category: 1-7 as in search.
    """
    _log("add_article", url)
    try:
        dest, msg = add_url.add(url, category)
        outcome, detail = indexer.index_path(dest, log=_stderr)
    except Exception as e:
        return f"Could not add the article: {type(e).__name__}: {e}"
    if outcome == "failed":
        return f"{msg}\nIndexing failed: {detail}"
    return f"{msg}\nIndexed ({outcome})."


if __name__ == "__main__":
    server.run()

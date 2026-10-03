# Reference library

Full-text, citable search over my books and reference articles, served to Claude (or any MCP client) over MCP. See `docs/reference-library-plan.md` for the why.

## Layout

- **Books and articles:** `~/Books/library/` links to the NAS folder `~/Network/peralese/Books/Technical Books/`. Each source goes in a numbered category folder (`1 - Enterprise & Software` … `7 - Developer & Systems Reference`), and **that folder sets its category**. Articles go in `<category>/articles/`.
- **Index:** `library/data/library.db` holds SQLite with FTS5 plus sqlite-vec and the full passage text. It's local only, gitignored and rebuildable. Search never touches the NAS.
- **Embeddings:** local Ollama `nomic-embed-text` (Ollama must be running for indexing *and* search).

## Commands

Run from `library/` with `.venv/bin/python` (Python 3.12. The repo's top-level `.venv` is 3.9 and can't load sqlite-vec).

| Do | Command |
|---|---|
| Index new/changed books (skips unchanged) | `.venv/bin/python indexer.py` |
| Rebuild from scratch (after a parser change) | `.venv/bin/python indexer.py --rebuild` |
| Add a web article | `.venv/bin/python add_url.py <url> <category 1-7>` |
| Tests | `.venv/bin/python -m pytest tests -q` |

To add a book, drop the EPUB in its category folder and run `indexer.py`. Use EPUBs, not PDFs.

## MCP

Registered at user scope as `reference-library` (`claude mcp list`). Tools: `search(query, category?, source?, limit?)`, `read_section(section_id)` and `list_sources(category?)`. The standing instruction to use it lives in `~/.claude/CLAUDE.md` and in the server's own `instructions`.

## How it works

- `parse.py` splits each EPUB into sections **by its table of contents**, because heading tags aren't reliable across publishers. It then groups blocks into passages of ~350 words (600 max) and never splits a code block. Front and back matter (index, copyright, etc.) is skipped. Citations are `Title — Chapter > Section`, since none of the EPUBs have page markers.
- `search.py` combines FTS5 bm25 (porter stemming, quoted phrases kept) with sqlite-vec cosine search using reciprocal rank fusion, with at most 2 passages per section.

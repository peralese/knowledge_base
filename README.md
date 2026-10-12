# Knowledge base: technical reference library

Full-text, citable search over my technical books and reference articles, served to Claude (or any MCP client) over MCP. See [`docs/design.md`](docs/design.md) for the design and what's next. The old ingest/synthesis/Obsidian pipeline was retired on 2026-10-11 and is recoverable from the `pre-library` tag.

## Layout

- **Books and articles:** `~/Books/library/` links to the NAS folder `~/Network/peralese/Books/Technical Books/`. Each source goes in a numbered category folder (`1 - Enterprise & Software` … `7 - Developer & Systems Reference`), and **that folder sets its category**. Articles go in `<category>/articles/`. Notes (short snippets) go in one Markdown file per topic in the category folder, e.g. `7 - Developer & Systems Reference/Claude Code Tips.md`; each `## ` heading becomes a citable section.
- **Index:** `data/library.db` holds SQLite with FTS5 plus sqlite-vec and the full passage text. It's local only, gitignored and rebuildable. Search never touches the NAS.
- **Embeddings:** local Ollama `nomic-embed-text` (Ollama must be running for indexing *and* search).

## Commands

Run from the repo root with `.venv/bin/python` (Python 3.12; sqlite-vec needs it). Set up with `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

| Do | Command |
|---|---|
| Index new/changed books (skips unchanged) | `.venv/bin/python indexer.py` |
| Show counts, recent runs, failed files and usage | `.venv/bin/python indexer.py --status` |
| Remove many deleted books at once (see below) | `.venv/bin/python indexer.py --allow-removals` |
| Rebuild from scratch (after a parser change) | `.venv/bin/python indexer.py --rebuild` |
| Add a web article (or ask Claude: `add_article`) | `.venv/bin/python add_url.py <url> <category 1-7>` |
| Tests | `.venv/bin/python -m pytest tests -q` |

To add a book, drop the EPUB in its category folder. The hourly job indexes it, or run `indexer.py` to do it now. Use EPUBs, not PDFs.

## Automatic indexing

The launchd job `com.library.indexer` (`launchd/com.library.indexer.plist`, installed in `~/Library/LaunchAgents/`) runs `indexer.py --auto` hourly and at login on the Mac mini.

- **Skips quietly** when the NAS isn't mounted or Ollama isn't running.
- **Cheap when nothing changed:** a file is re-read only if its size or modified time changed, so a quiet run takes well under a second.
- **Won't wipe the index:** if more than 5 indexed files look gone at once (a half-mounted share looks exactly like that), it removes nothing, logs a warning and notifies you. If you really deleted them, run `indexer.py --allow-removals`.
- **Bad files don't block the rest:** a book that fails to parse is recorded and retried only once the file changes. `--status` lists failures.
- **One run at a time,** enforced by a lock on `data/.indexer.lock`.
- **Feedback:** each run is logged in `logs/indexer.log`, and you get a macOS notification when something was added, removed or failed. Crashes go to `logs/indexer.launchd.log`.

**Permission:** macOS blocks background jobs from network volumes until you allow it. The first run shows an "access files on a network volume" prompt on the Mac mini's screen; click Allow. If it ever can't read the NAS (e.g. after Homebrew upgrades Python), you'll get a "Can't read the NAS" notification. Allow the prompt again, or add the Python.app under `/opt/homebrew/Cellar/python@3.12/<version>/Frameworks/Python.framework/Versions/3.12/Resources/` to Full Disk Access.

Run it now with `launchctl kickstart gui/$(id -u)/com.library.indexer`. Stop it with `launchctl bootout gui/$(id -u)/com.library.indexer`.

## MCP

Registered at user scope as `reference-library` (`claude mcp list`). Its tools:

| Tool | Does |
|---|---|
| `search(query, category?, source?, limit?)` | hybrid search; passages with citations |
| `read_section(section_id)` | a whole section, with previous/next ids |
| `list_sources(category?)` | books and articles by category |
| `outline(source, chapter?)` | a book's chapters, or one chapter's sections, for reading with Claude |
| `save_note(topic, heading, body, source, category)` | appends a note entry to `<category>/<topic>.md` on the NAS and indexes it at once |
| `add_article(url, category)` | fetches a web page into `<category>/articles/` and indexes it at once |

The standing instruction to use it lives in `~/.claude/CLAUDE.md` and in the server's own `instructions`.

**Usage log:** every tool call is recorded in `data/usage.db`, kept apart from the index so `--rebuild` doesn't wipe it, with the Claude Code session's directory. `indexer.py --status` summarises the last 7 days. This shows whether the library is actually used.

**Health at session start:** a user-level SessionStart hook in `~/.claude/settings.json` runs `indexer.py --health`. It prints one line only when indexing needs attention: failed books, held-back removals, or no run for 3+ hours. Over SSH, the job's macOS notifications are never seen, so this is how problems surface.

## Skills

`skills/` holds two Claude Code skills, symlinked into `~/.claude/skills/` so they work in every project:

- **`/ask-books <question>`:** a cross-book answer covering what the books say, where they agree or disagree, and what they don't cover, with every claim cited.
- **`/design-review [path|diff|doc]`:** reviews a design or codebase against the books. It gives findings ranked by impact, each with a citation and a suggestion, and can write an ADR.

To install on a fresh machine: `ln -s "$PWD/skills/ask-books" "$PWD/skills/design-review" ~/.claude/skills/`.

## How it works

- `parse.py` splits each EPUB into sections **by its table of contents**, because heading tags aren't reliable across publishers. It then groups blocks into passages of ~350 words (600 max) and never splits a code block. Front and back matter (index, copyright, etc.) is skipped. Citations are `Title — Chapter > Section`, since none of the EPUBs have page markers.
- `search.py` combines FTS5 bm25 (porter stemming, quoted phrases kept) with sqlite-vec cosine search using reciprocal rank fusion, with at most 2 passages per section.

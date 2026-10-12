# Knowledge base — design

_Last updated: 2026-10-11_

## What it is

A **reference library that Claude reads for me**. It holds the full text of my technical books, plus a few lasting reference articles and my own notes, split into citable passages. Claude Code searches it over MCP while I work and cites what it uses (`Title, Chapter > Section`). I never have to open or browse it.

**The rule for adding anything:** *will this make Claude more useful on work I'm actually doing?* If not, don't add it.

**Scope: technical books only.** Sources come from `Books/Technical Books` on the NAS and nothing else on the share.

The previous knowledge base (ingest → LLM synthesis → review → Obsidian wiki, plus feeds, dashboard and daily briefing) was mothballed on 2026-10-03 and deleted on 2026-10-11. It was built around browsing notes, which I never did. Its code is recoverable from the `pre-library` git tag.

## Current state (2026-10-11)

- **Corpus:** 52 EPUBs, 13 articles and 1 notes file, about 20k passages. The index is ~190 MB.
- **Categories (the folder sets the category):**
  1. Enterprise & Software
  2. Cloud, Platform & Infrastructure Engineering
  3. Integration, APIs & Automation
  4. Data, AI & Machine Learning Engineering
  5. Cybersecurity & Security Architecture
  6. AI Strategy, Society & Emerging Technology
  7. Developer & Systems Reference
- **Indexing speed:** about 10–30 s per book. A full rebuild takes ~12 min.

## How it works

```
NAS: ~/Books/library -> ~/Network/peralese/Books/Technical Books/<n - Category>/
        *.epub, articles/*.{html,md} (+ .url.json sidecar), <Topic>.md notes
            |
            v  indexer.py (sha256 diff; adds, re-indexes, removes)
  parse.py: EPUB TOC -> sections -> ~350-word passages (code blocks kept whole)
  embed.py: Ollama nomic-embed-text
            |
            v
  data/library.db (local SQLite: FTS5 + sqlite-vec + full passage text)
            |
            v  server.py (MCP, stdio): search / read_section / list_sources
  Claude Code  (standing instruction in ~/.claude/CLAUDE.md + server instructions)
```

### Fixed decisions

- **Sections follow each EPUB's table of contents,** not heading tags, which vary by publisher. EPUBs have no page markers, so citations stop at chapter and section.
- **Search is hybrid:** FTS5 bm25 combined with vector cosine via reciprocal rank fusion, with at most 2 passages per section.
- **The index stays local.** SQLite over SMB is unsafe, and search has to keep working when the NAS is asleep or I'm away. The index can always be rebuilt from the books, so only the books need backing up.
- **No LLM summarizing.** The full passage is what's worth citing.
- **Prefer EPUBs to PDFs.**

## Next: v2

The NAS is plain SMB storage and can't run anything, and this Mac is a laptop that sleeps. Both shape the design.

### 1. Automatic indexing (this Mac)

Books and notes dropped on the NAS should get indexed without anyone running a command.

- **Trigger:** a launchd agent, `com.library.indexer`, with `StartInterval` 3600 and `RunAtLoad`. `WatchPaths` doesn't fire reliably on SMB mounts. It exits quietly when the NAS isn't mounted or Ollama is down.
- **Cheap change detection:** store `size` and `mtime` per source and hash only files where either changed. Today every run reads about 1 GB over SMB to hash every file.
- **Removal guard:** if more than ~20% of sources (or more than 5) look gone, skip removals and log it. This stops a half-mounted share from wiping the index.
- **Lock:** an `fcntl` lock on `data/.indexer.lock`, so manual and scheduled runs can't overlap.
- **Feedback:** write to `logs/indexer.log`, send a macOS notification when books are added or a parse fails, and add an `indexer.py --status` flag.

### 2. Use from another computer at home

**Publish a read-only index snapshot to the NAS, and run a local MCP server on each machine.**

- After a run that changed something, write a consistent copy using SQLite's backup API to `Technical Books/.index/library.db`, plus a `manifest.json` (timestamp, counts, embed model). `discover()` already skips dotfiles.
- **The other computer** gets a clone of the repo, the venv, Ollama with `nomic-embed-text` (queries need embeddings) and the MCP server registered. A `sync_index.py` copies the snapshot locally when the manifest is newer. The database is never opened live over SMB.
- This works while the laptop sleeps, and needs no networking or auth. It costs ~190 MB copied per change.
- **Later, only if needed:** MCP over streamable HTTP from an always-on box.
- **Open question:** the other computer's OS, which decides the sync trigger.

### Not planned

PDF or video ingestion, retrieval tuning, a browse UI and study tools. Revisit only if real use shows a need.

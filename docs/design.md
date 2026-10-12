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

## v2

The library runs on a **Mac mini** (always on, so it can serve other machines). The NAS is plain SMB storage and can't run anything.

### 1. Automatic indexing — done 2026-10-11

A launchd job, `com.library.indexer`, runs `indexer.py --auto` hourly and at login. Details are in the README under *Automatic indexing*. In brief:

- It records each file's size and modified time, so a run with nothing new takes ~0.1 s instead of re-reading ~1 GB over SMB.
- A removal guard holds back removals when more than 5 files look gone.
- Files that fail to parse are recorded and retried only once they change.
- An `fcntl` lock prevents overlapping runs.
- Each run is logged, notifications go out on changes, and there's an `indexer.py --status` flag.

**macOS gotcha:** a launchd job can't read a network volume until the "access files on a network volume" prompt is allowed on the Mac mini's own screen. Before that, the read hangs for minutes and then fails with `EINTR`.

### 2. Use from another computer at home (next)

**Serve the library over the LAN from the Mac mini.** The MCP server already supports streamable HTTP, so it would run as a second launchd job on a fixed port. The other computer just registers `http://<mac-mini>.local:<port>/mcp` in Claude Code.

- The other machine needs no index copy, no Ollama and no syncing. It always sees the latest index.
- **To decide:**
  - LAN-only binding plus a simple shared token, versus no auth on a trusted home network.
  - Whether the stdio registration on the Mac mini stays as it is (simplest) or also moves to HTTP.
  - Waking the Mac mini if it sleeps (Energy settings: "Prevent automatic sleeping", or wake on network access).
- **Fallback, if the Mac mini can't stay on:** publish a read-only snapshot to `Technical Books/.index/` after each changing run, and keep a local server plus Ollama on the other machine.

### Not planned

PDF or video ingestion, retrieval tuning, a browse UI and study tools. Revisit only if real use shows a need.

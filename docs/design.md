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

The library runs on a **Mac mini** that never sleeps; I reach it over SSH from other machines. The NAS is plain SMB storage and can't run anything.

### 1. Automatic indexing — done 2026-10-11

A launchd job, `com.library.indexer`, runs `indexer.py --auto` hourly and at login. Details are in the README under *Automatic indexing*. In brief:

- It records each file's size and modified time, so a run with nothing new takes ~0.1 s instead of re-reading ~1 GB over SMB.
- A removal guard holds back removals when more than 5 files look gone.
- Files that fail to parse are recorded and retried only once they change.
- An `fcntl` lock prevents overlapping runs.
- Each run is logged, notifications go out on changes, and there's an `indexer.py --status` flag.

**macOS gotcha:** a launchd job can't read a network volume until the "access files on a network volume" prompt is allowed on the Mac mini's own screen. Before that, the read hangs for minutes and then fails with `EINTR`.

### 2. Use from another computer at home — not needed

I SSH into the Mac mini from other machines and run Claude Code there. The MCP server, the index, Ollama and the hourly job all live on the Mac mini, so no network serving or index syncing is required.

- Over SSH, the job's macOS notifications and any permission prompts appear on the Mac mini's own screen. Check with `indexer.py --status`.
- If Claude Code ever has to run on another machine directly, serve MCP over streamable HTTP from the Mac mini (LAN only) rather than copying the index.

### 3. Getting it used — built 2026-10-11

Session transcripts showed that the library's first 17 searches (2026-10-02 to 10-11) all came from this repo, mostly tests. My real uses are day-job architecture work, ad-hoc technical questions and reading the books. So:

- **Usage log** (`data/usage.db`, summarised by `--status`): whether it's used, from which projects, and which books answer.
- **Sharper standing instruction**, in `~/.claude/CLAUDE.md` and the server's instructions: search at concrete *moments* (design choices, architecture write-ups, technical questions, reading), not by topic.
- **Health line** at session start (SessionStart hook → `indexer.py --health`), silent when fine.
- **Skills:** `/ask-books` (a cross-book answer) and `/design-review` (a design checked against the books, with an optional ADR).
- **Reading support:** the `outline` tool. No progress tracking, by design.
- **Save from any project:** `save_note` and `add_article`, both indexed at once via `indexer.index_path()`. That takes the indexer lock, waiting for an hourly run if one is in progress.

**Next decision (after 2026-10-17):** review `--status` usage. If real use shows up, carry on. If it doesn't, the trigger isn't the problem and the library's value should be questioned before anything more is built.

### Not planned

PDF or video ingestion, retrieval tuning, a browse UI and study tools. Revisit only if real use shows a need.

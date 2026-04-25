# Knowledge Base

Knowledge Base is a local-first research pipeline for turning URLs, files, feeds, and notes into an Obsidian-readable compiled wiki. It ingests raw material, synthesizes source summaries with a local Ollama model, scores and reviews them, aggregates approved knowledge into topic notes, and supports querying or re-synthesizing the compiled wiki.

## Architecture

The repository is organized as four layers:

- `raw/` stores inbox drops, normalized source articles, PDFs, notes, and archives.
- `compiled/` stores source summaries, topic notes, concept notes, and the generated wiki index.
- `outputs/` stores reports and saved Q&A answers.
- Obsidian opens `compiled/` as the human-facing vault.

Pipeline flow:

```text
Dashboard / feeds / file drops
        |
        v
raw/inbox/ -> inbox_watcher.py -> raw/articles/
        |
        v
pipeline_run.py -> synthesize.py -> score_synthesis.py -> review.py
        |
        v
topic_aggregator.py -> compiled/topics/ -> index_notes.py -> compiled/index.md
        |
        +-> concept_aggregator.py -> compiled/concepts/ + compiled/entities/
        +-> query.py / Query tab -> outputs/answers/
        +-> resynthesize_topic.py -> refreshed topic note
        |
        v
Obsidian vault at compiled/
```

## Features

- Browser dashboard at `http://localhost:7842` for URL/file ingestion, metadata capture, review queue actions, Q&A, and topic re-synthesis.
- Inbox adapters for browser saves, clipboard drops, feed entries, and PDF drops under `raw/inbox/`.
- Normalized raw article notes with source metadata, source manifest tracking, and duplicate-safe staging.
- Local Ollama synthesis into `compiled/source_summaries/`, followed by confidence scoring and review.
- Topic aggregation from approved source summaries into canonical notes in `compiled/topics/`.
- BM25 keyword search over compiled notes and optional raw notes.
- Natural-language querying against all topic notes or a selected topic plus linked source summaries, with answers saved in `outputs/answers/`.
- Explicit topic re-synthesis from all approved linked source summaries, with versioned topic frontmatter and pipeline git commits.
- Generated `compiled/index.md` for human browsing and LLM context.
- Health lint reports for wikilinks, orphaned notes, unapproved items, and optional LLM-assisted coverage checks.
- Pipeline git auto-commits for durable operational history, with `GIT_DISABLED=1` and `--no-commit` escape hatches where supported.

## Getting Started

Use [INSTALL.md](INSTALL.md) for the full Fedora-oriented installation guide, including Python, Ollama, directory setup, systemd user services, first-run verification, troubleshooting, and uninstall steps.

## Daily Use

Dashboard: `http://localhost:7842`

Add article: Dashboard -> Ingest tab -> paste URL or upload file

Review queue: Dashboard -> Review Queue tab, or `python3 scripts/review.py list`

Query: `python3 scripts/query.py "your question"`

Query with explicit retrieval mode: `python3 scripts/query.py "your question" --retrieval hybrid`

Scoped query: `python3 scripts/query.py --topic openclaw-security "your question"`

Search: `python3 scripts/search.py "keyword"`

Pipeline log: `python3 scripts/log.py`

Lint: `python3 scripts/lint.py`

Open in Obsidian: point a vault at `compiled/`

## Pipeline Scripts

| Script | What it does |
|--------|-------------|
| `apply_synthesis.py` | Applies raw LLM output to durable compiled notes or answer artifacts. |
| `concept_aggregator.py` | Extracts concepts and entities from approved source summaries into `compiled/concepts/` and `compiled/entities/`. |
| `compile_notes.py` | Builds prompt packs from source notes for synthesis. |
| `feed_poller.py` | Polls RSS/Atom feeds from `metadata/feeds.json` into `raw/inbox/feeds/`. |
| `git_ops.py` | Shared helper for pipeline auto-commits. |
| `inbox_watcher.py` | Watches `raw/inbox/`, ingests new files, validates raw notes, and queues review entries. |
| `index_notes.py` | Generates `compiled/index.md` from compiled topics, concepts, and source summaries. |
| `ingest.py` | Normalizes raw source files into `raw/articles/` and updates the source manifest. |
| `lint.py` | Runs structural health checks and optional LLM-assisted wiki checks. |
| `llm_driver.py` | Sends prompt packs to Ollama and writes raw synthesis output. |
| `log.py` | Formats pipeline git history as an operational log. |
| `normalize_artifacts.py` | Helps clean legacy artifacts and naming drift. |
| `pipeline_run.py` | Runs synthesize -> score -> aggregate -> index for queued articles or watch mode. |
| `query.py` | Queries the compiled wiki from the CLI and saves answers. |
| `query_engine.py` | Shared query context loading, prompt building, citation parsing, and answer persistence. |
| `resynthesize_topic.py` | Rebuilds one or all topic notes from approved linked source summaries. |
| `review.py` | Lists, approves, and rejects synthesized review queue items. |
| `score_synthesis.py` | Scores synthesized notes with Ollama and auto-approves high-confidence items. |
| `search.py` | BM25 keyword search over compiled notes and optional raw notes. |
| `setup_project.py` | Creates the expected project directory skeleton and sample files. |
| `stage_to_inbox.py` | Stages browser, clipboard, feed, and PDF inputs into the inbox layout. |
| `synthesize.py` | Builds prompt packs, calls Ollama, applies synthesis, and updates queue status. |
| `topic_aggregator.py` | Classifies source summaries into registry topics and updates topic notes. |

## Background Services

| Service | What it does |
|---------|-------------|
| `kb-dashboard.service` | Runs the FastAPI dashboard on the configured dashboard port. |
| `kb-feed-poller.service` | Polls configured feeds and drops new entries into the inbox. |
| `kb-inbox-watcher.service` | Watches inbox directories and stages new raw articles for the pipeline. |
| `kb-lint.service` | Runs the weekly lint command as a one-shot service. |
| `kb-lint.timer` | Schedules `kb-lint.service` weekly. |
| `kb-pipeline.service` | Runs `pipeline_run.py --watch --interval 30` for continuous processing. |

## Phase 2 Roadmap

Phase 1–13 delivered a fully operational pipeline. Phase 2 focuses on making the knowledge graph richer, more trustworthy, and faster to query — in that order.

**Sequencing principle:** enrich graph → measure integrity → reduce capture friction → add retrieval layer. No managed cloud services at any phase.

---

### Phase 2A — Knowledge Usability

Make the existing graph denser and traversable before investing in UI.

| Step | Task | Notes |
|------|------|-------|
| 2A-1 | **Graph Health Baseline** | Script measuring wikilink density, stub ratio, orphan count. Run before/after as benchmark. |
| 2A-2 | **Concept Definitions** | Second LLM pass to write actual definitions for stub notes, sourced from approved content. |
| 2A-3 | **Wikilink Injection** | Back-annotate source/topic notes with `[[concept]]` links. Converts flat text to graph. |
| 2A-4 | **Concepts/Entities Browser** | Dashboard tab for browsing concept/entity notes. Build after 2A-2 and 2A-3 are complete. |

---

### Phase 2B — Knowledge Integrity

Detect drift, gaps, and contradictions as the corpus grows.

| Step | Task | Notes |
|------|------|-------|
| 2B-1 | **Query Feedback Loop** | Complete. `scripts/feedback.py` marks saved answers good/bad, stores feedback in answer frontmatter, reports feedback stats, and the dashboard Query tab exposes thumbs up/down controls via `POST /api/feedback`. |
| 2B-2 | **Cross-topic Contradiction Detection** | Complete. `scripts/lint.py --contradictions` extracts topic claims, compares topic pairs with Ollama, prints human-review candidates only, and saves JSON reports under `outputs/contradictions/`. Fixed: `issues` list now initialized before the LLM call loop so Ollama connection errors are captured correctly. |
| 2B-3 | **Gap Ranking** | Complete. `scripts/graph_health.py --gaps [--top N]` ranks under-covered topics using orphan concept ratio, inverse approved-source density, and stub ratio; gap data is included in graph-health snapshots and comparison output. |
| 2B-4 | **Staleness Lint** | Complete. `scripts/lint.py --staleness [--days N]` flags topic notes with newer approved related source summaries, writes reports under `outputs/staleness/`, and `--fix` prints the re-synthesis commands to queue. |

---

### Phase 2C — Capture Ergonomics

Reduce friction on daily ingestion and review.

| Step | Task | Notes |
|------|------|-------|
| 2C-1 | **Mobile Share-to-Inbox** | Complete. `POST /api/share` accepts a URL from any iOS/Android share sheet and queues it to `raw/inbox/feeds/` via the same `stage_to_inbox.stage_feed` path. Returns `{status:"queued", inbox_id:"INX-..."}` or `{status:"duplicate", existing_id:"..."}`. `mobile/ios-share-shortcut.md` and `mobile/android-share-intent.md` document exact setup steps for both platforms. Network requirement (same WiFi or Tailscale) is documented; no VPN integration built. |
| 2C-2 | **Review Workflow Improvements** | Complete. Audit found: CLI `list` showed metadata only (no synthesis), requiring two commands per item with no sequential mode; dashboard had a lazy Preview button but no auto-advance. Added: `review.py show <id>` (full synthesis + URL + confidence), `review.py list --full` (synthesis inline for all queued items), `review.py session` (single-keypress a/r/s/q interactive session with Ctrl-C support and summary). Dashboard review cards now show source URL and ingested date alongside confidence. |
| 2C-3 | **Saved Searches / Pinned Topics** | Complete. (A) Saved searches: `GET/POST/DELETE /api/saved-searches` persists queries to `outputs/saved_searches.json`; dashboard Query tab has a sidebar with save/run/delete; searches always re-run live. (B) Pinned topics: `POST /api/topics/{slug}/pin` and `/unpin` write `pinned: true/false` to topic note frontmatter; new Topics tab in dashboard shows pinned topics above the rest. (C) Recent entity activity: `GET /api/entities/recent` returns the 10 most recently active entities by static metadata scan (no LLM, under 500ms); "Recent Activity" panel shown in Concepts/Entities tab. |

---

### Phase 2D — Vector Retrieval Layer

Complement BM25 for semantic queries at scale. Sequenced last so embeddings are generated over high-quality, well-linked notes.

| Step | Task | Notes |
|------|------|-------|
| 2D-1 | **Latency Benchmarking** | Complete. `scripts/benchmark_query.py` measures BM25 retrieval and end-to-end latency per query type; saves JSON snapshots to `outputs/benchmarks/`. Benchmark finding: BM25 is <0.1ms at 37 notes; Ollama synthesis (~2–5s) dominates. Vector retrieval is warranted for semantic recall quality, not latency. |
| 2D-2 | **sqlite-vec or FAISS Index** | Complete. `scripts/vector_index.py` manages a local SQLite-based vector index (`outputs/vector_index.db`) using stdlib `sqlite3` + JSON embeddings + pure-Python cosine similarity (no new pip deps). Embedding model: `nomic-embed-text` via Ollama (install: `ollama pull nomic-embed-text`). Commands: `build`, `update` (hash-based incremental), `search`, `stats`. Stub concept notes and unapproved source summaries are excluded. |
| 2D-3 | **Hybrid Retrieval** | Complete. `query.py` defaults to hybrid (BM25 60% + vector 40%) when the index is fresh; falls back to BM25 silently otherwise. Flags: `--retrieval {bm25,vector,hybrid}` and `--show-retrieval`. Dashboard Query tab has BM25/Hybrid/Vector toggle. Graceful degradation confirmed: queries work with index absent or stale. |

**Post-ingest sequence** (run after approving new source summaries):

```bash
python3 scripts/concept_aggregator.py --all
python3 scripts/define_concepts.py
python3 scripts/inject_wikilinks.py
python3 scripts/vector_index.py update       # update vector index for new/changed notes
python3 scripts/graph_health.py
```

**nomic-embed-text requirement**: the vector index requires an Ollama embedding model. If not yet installed:
```bash
ollama pull nomic-embed-text
```

---

### What to avoid in Phase 2

- Managed vector databases (cloud)
- Complex agent frameworks
- Model fine-tuning
- Auto-merge or auto-rewrite of contradictions
- Heavy dashboard UI before the graph is richer
- Auto-rewrite of notes

---

### Phase 2 success signals

- Graph health baseline script shows measurable wikilink density and stub ratio improvement after 2A
- Query feedback scores trend upward as 2B integrity work lands
- Latency benchmarks remain acceptable through 2D without cloud dependency

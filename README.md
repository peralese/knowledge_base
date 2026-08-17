# Knowledge Base

## Domain-Aware KBs

The dashboard and pipeline now support multiple local domains, such as `ai` and `civil-war-history`, without mixing them into one reasoning space. New domain-aware flows write to `raw/domains/<slug>/`, `metadata/domains/<slug>/`, `compiled/domains/<slug>/`, `outputs/domains/<slug>/`, and `indexes/domains/<slug>/`.

See [docs/domains.md](docs/domains.md) for the architecture, migration command, and CLI examples.

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
| `briefing.py` | Evaluates RSS candidates, selects idempotent daily editions, generates validated contextual narratives, renders Markdown artifacts, and prunes old low-value candidates. |
| `feed_poller.py` | Polls RSS/Atom feeds from `metadata/feeds.json` into the separate SQLite Daily Briefing candidate store. |
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

## Mac mini Runtime Ownership and Safety

The Mac mini checkout at `/Users/erickperales/Projects/knowledge_base` is the
authoritative operational writer. Other machines should normally pull and read
generated Markdown through Git or Obsidian; they should not run competing inbox,
pipeline, or index writers against another checkout.

Automatic work has one owner per stage:

```text
Sources -> inbox watcher (normalize + queue only)
        -> scheduled pipeline worker (every 30 seconds)
        -> synthesize -> score -> approval gate
        -> approved topic/concept/entity aggregation -> indexes -> Git/Obsidian
```

The watcher never runs synthesis itself. Pending queue entries remain durable and
are rediscovered by the next worker run after a crash or reboot. The worker uses a
non-blocking global lock plus a per-source lock, so an overlapping launch defers
cleanly instead of processing the same source twice. Index rebuilds have a
per-domain lock.

Runtime locks are advisory `flock` files under `tmp/locks/`. The files may remain,
but lock ownership is held by the operating system and is automatically released
when a process exits, crashes, or the Mac reboots; lock files must not be deleted
to recover. Git staging/commits use a shared `git-write` lock and path-limited
commits. Ollama generation and embedding requests use a shared `ollama` lock so
expensive local inference is serialized.

Review queues, source manifests, feed/watcher state, and registries use a
same-directory temporary file followed by an atomic replacement. This prevents a
reader from observing a partially written JSON file. The production auto-approval
threshold is centralized at `0.85`; standalone scoring uses the same safe default.
Canonical topic aggregation requires both `review_action: approved` and
`approved: true` on the source summary.

On macOS, RSS is a scheduled one-shot LaunchAgent: `feed_poller.py --once` runs at
load and hourly. An absent or empty `metadata/feeds.json` logs a clear message and
exits successfully; it is never configured with `KeepAlive`. The authoritative
configuration currently enables 18 public RSS/Atom feeds.

## Perales Lab Daily Briefing

The Perales Lab Daily Briefing is an implemented, functionally validated extension of the knowledge-base platform. Phases 2A–2D provide an end-to-end local path from selected RSS information through an evidence-bounded narrative and human retention review to an inspectable speech script and WAV briefing.

The goal is not to archive every RSS item. The Daily Briefing will act as an editorial layer that determines:

- What is worth knowing today
- What relates to existing interests, projects, and knowledge
- What is useful only for the current briefing
- What deserves to be retained for future reference
- What should be promoted into the permanent knowledge base

The existing knowledge-base pipeline remains the authoritative path for durable knowledge.

### Current architecture

```text
Selected RSS feeds
        ↓
RSS polling and deduplication
        ↓
Briefing candidate store
        ↓
Relevance and editorial evaluation
        ↓
Daily edition selection
        ↓
Knowledge-base contextualization
        ↓
Narrative Daily Briefing
        ↓
Per-item retention decision
   ┌──────────┼───────────────┐
   ↓          ↓               ↓
Discard    Reference     Promote to KB
                               ↓
                    Existing KB ingestion
                               ↓
                 Synthesis / approval gate
                               ↓
              Topics / concepts / entities
                               ↓
                       Git / Obsidian

Narrative Daily Briefing
        ↓
Deterministic speech preparation
        ↓
Local macOS text-to-speech
        ↓
Validated PCM WAV
```

The Daily Briefing candidate layer will remain separate from the permanent KB inbox. RSS items will not automatically become durable knowledge.

Only items explicitly promoted should enter the existing knowledge-base ingestion and approval pipeline.

### Editorial principle

The Daily Briefing should not include an item simply because it is new.

An item should be selected when the system can explain why it matters in the context of the configured interests, active projects, or existing knowledge base.

The briefing answers:

> What is worth knowing today?

The knowledge base answers:

> What is worth remembering later?

These are intentionally separate decisions.

### Retention model

Each briefing item supports three outcomes:

#### Discard

The information was useful for the current briefing but has little durable value.

The item may remain in briefing history for audit purposes but should not enter the permanent knowledge base.

#### Reference

The information may be useful later but does not justify full promotion into canonical knowledge.

A reference should retain enough provenance to find and understand the source later while remaining outside normal topic/concept aggregation.

#### Promote to Knowledge Base

The information has durable value.

Promoted items enter the existing KB pipeline and use the current:

- Domain-aware ingestion
- Source normalization
- Local LLM synthesis
- Confidence scoring
- Human or automatic approval
- Topic aggregation
- Concept/entity extraction
- Markdown generation
- Vector indexing
- Git history
- Obsidian integration

The existing approval boundary remains authoritative. Information must be approved before it can affect accumulated canonical knowledge.

## Implementation phases

### Phase 1 — Runtime stabilization — Complete

The Mac mini runtime was stabilized before adding Daily Briefing functionality.

Completed work includes:

- Single automatic pipeline-processing owner
- Intake-only inbox watcher
- Scheduled one-shot pipeline worker
- Scheduled one-shot RSS poller
- Advisory processing locks
- Per-source locks
- Git serialization
- Ollama serialization
- Atomic shared-state writes
- Approval enforcement before topic aggregation
- Centralized `0.85` automatic approval threshold
- Runtime and launchd documentation

The Mac mini remains the authoritative operational writer.

### Phase 1.5 — Test baseline and isolation — Complete

The full test suite was triaged and repaired before beginning new functionality.

Current baseline:

```text
Canonical test command:
make test

Full suite:
1,082 passed

Focused Phase 1 safety suite:
201 passed
```

Two consecutive full-suite runs completed successfully with:

- 0 failures
- 0 errors
- 0 skipped tests
- 0 xfail tests
- 0 warnings

The default suite uses temporary roots and mocks and does not write test artifacts into the live knowledge base.

### Phase 2A — RSS and briefing candidate layer — Complete

Phase 2A provides a separate SQLite candidate layer, structured Ollama editorial evaluation, deterministic deduplication, novelty-aware daily selection, and Markdown review editions. See [docs/daily-briefing.md](docs/daily-briefing.md) for configuration, storage, scoring, CLI, retry, and retention details.

Implemented scope:

- Configure selected RSS/Atom feeds
- Improve feed provenance and metadata capture
- Deduplicate by appropriate identifiers such as URL, GUID, and/or content identity
- Store new feed items in a briefing-specific candidate store
- Keep candidates outside the permanent KB inbox
- Add editorial relevance evaluation
- Add novelty and duplicate-story detection
- Select a small daily set of high-value items
- Track which candidates were considered, selected, or ignored

The output is a structured daily edition containing a small set of selected items.

No podcast generation is required for Phase 2A.

No automatic KB promotion is required for Phase 2A.

### Phase 2B — Two-stage contextual narrative briefing — Complete

Phase 2B converts the selected daily edition into a concise, connected written briefing using two bounded local-Ollama stages. **2B1 Narrative Synthesis** creates the structured architectural draft. Deterministic topic proposals keep unrelated items separate and preserve explicit relationship semantics. **2B2 Evidence-Bounded Editorial Cleanup** identifies localized risky sentences and may only weaken, attribute, remove, or precisely restate those sentences from stored source evidence.

Cleanup never changes selection, grouping, section order, unrelated prose, or provenance. It gets at most two model attempts per flagged unit. After exhaustion, a deterministic fallback may remove only a field-classified nonessential takeaway or what-to-watch entry; it never removes an opening or substantive section body. Core failures still fail the generation. Legacy generations remain readable in `narrative_generations`; two-stage runs, sentence-level repairs, and fallback removals are recorded additively in `narrative_pipeline_runs`, `narrative_cleanup_attempts`, and `narrative_cleanup_fallbacks`.

For a remaining attribution-only comparison, 2B2 may deterministically prepend canonical publisher attribution after both model attempts. This requires one selected supporting source, an authoritative publisher mapping, exact evidence for every metric and comparison baseline, and no other violation. The original claim is otherwise unchanged, and the action is audited in `narrative_attribution_normalizations`.

If cleanup altered or omitted an evidence-bearing metric or baseline, a narrower reconstruction path may instead rebuild one literal comparative sentence from a single unambiguous stored-source clause. Publisher, product, metric, comparison dimension, and baseline are immutable; the fixed template adds no interpretation. Reconstructions are audited in `narrative_comparative_reconstructions` and must pass the ordinary validators.

Final wording validation also detects the scoped absolute construction `eliminat* … the need` and promotional adjectives such as exceptional/outstanding/remarkable when they directly characterize measurable performance, ratings, benchmarks, latency, throughput, efficiency, price-performance, or bandwidth. Cleanup is instructed to prefer exact stored measurements—such as a concrete aSAPS rating—over promotional paraphrase.

Implemented guarantees:

- Every section references selected candidate IDs, and every selected item is represented
- Titles, URLs, sources, timestamps, categories, and scores are restored from stored provenance rather than trusted from model output
- Invalid or hallucinated IDs and malformed schemas are rejected without changing the Phase 2A edition
- Default generation is idempotent; explicit `--regenerate` creates an auditable replacement only after validation
- Only a fully validated post-cleanup narrative becomes current, renders canonical Markdown, and is eligible for Phase 2D
- Failed synthesis or cleanup attempts are recorded and cannot displace the last valid narrative
- Markdown narratives include per-section citations and a source appendix

Generate manually with:

```bash
.venv/bin/python scripts/briefing.py narrative --date YYYY-MM-DD
.venv/bin/python scripts/briefing.py narrative --date YYYY-MM-DD --regenerate
make test-briefing
```

See [docs/daily-briefing.md](docs/daily-briefing.md) for architecture, provenance, validation, retry, and scope details. Phase 2B remains text-only and does not retrieve or promote permanent KB material.

### Phase 2C — Retention review and controlled KB promotion — Complete

Phase 2C adds an explicit human gate after briefing review. Selected items begin as pending and may be marked `discard`, `reference`, or `promote`; models and scores cannot make these decisions.

Semantics:

```text
Discard
Reference
Promote to Knowledge Base
```

- Discard preserves all briefing history and records only the auditable decision.
- Reference creates one deterministic metadata-only briefing reference outside permanent KB ingestion.
- Promote creates one deterministic domain feed-inbox artifact with briefing provenance. The existing watcher, raw-note validation, review queue, and approval gates remain authoritative; promote never means approved.

SQLite stores current state, append-only decision history, and downstream attempts. Identical actions are idempotent, failures are retryable, canonical-source duplicates are reconciled, and decision changes do not silently delete earlier references or KB intake artifacts.

```bash
.venv/bin/python scripts/briefing.py retention list --date YYYY-MM-DD --status pending
.venv/bin/python scripts/briefing.py retention show BFC-… --date YYYY-MM-DD
.venv/bin/python scripts/briefing.py retention discard BFC-… --date YYYY-MM-DD --reviewer NAME
.venv/bin/python scripts/briefing.py retention reference BFC-… --date YYYY-MM-DD --reviewer NAME
.venv/bin/python scripts/briefing.py retention promote BFC-… --date YYYY-MM-DD --reviewer NAME
.venv/bin/python scripts/briefing.py retention retry BFC-… --date YYYY-MM-DD
```

See [docs/daily-briefing.md](docs/daily-briefing.md) for the full retention model, provenance chain, promotion boundary, failure behavior, and exclusions.

### Phase 2D — Local audio briefing generation — Complete

Phase 2D converts the current validated Phase 2B narrative into a deterministic spoken script and local podcast-style WAV artifact. The narrative remains canonical; speech and audio are derived presentation artifacts.

The authoritative Mac mini uses the built-in `/usr/bin/say` Speech Synthesis Manager. Direct MP3 and AAC conversion were tested but are not operational on this host, while 22.05 kHz mono PCM WAV generation is reliable and broadly playable without another dependency.

```bash
# Inspect exactly what will be spoken
.venv/bin/python scripts/briefing.py audio script

# Generate or reuse today's audio
.venv/bin/python scripts/briefing.py audio generate

# Explicitly regenerate it
.venv/bin/python scripts/briefing.py audio generate --regenerate

# Inspect readiness, configuration, provenance, and narrative staleness
.venv/bin/python scripts/briefing.py audio status

# Listen locally
afplay outputs/briefing/audio/$(date +%F)-briefing.wav
```

Speech preparation removes Markdown, citations, raw URLs, and the source appendix; adds natural section transitions; and conservatively expands common technical acronyms. SQLite stores append-only successes/failures, narrative/configuration fingerprints, voice/rate, duration, paths, and provenance. Changed narratives make existing audio stale, and failed regeneration preserves the last valid artifact.

The speech layer also normalizes known structural heading slashes (for example, `Compute/Platform` becomes `Compute and Platform`) and accidental duplicate terminal periods without globally rewriting body slashes, paths, decimals, versions, or intentional ellipses.

### Completed operational baseline

The live-feed operational test completed the full path across 18 configured feeds. Seventeen returned entries and arXiv returned a valid empty Atom feed. Initial ingestion fetched 2,564 items, creating 2,525 candidates and identifying 39 duplicates. The test drove fixes for stale backfill selection, source domination, below-threshold filler, narrative grouping, evidence controls, attribution, and speech preparation.

The accepted August 9, 2026 edition contains four stories: DynamoDB real-time vector search, Bedrock AgentCore persistent runtime instances, EC2 R8i/R8i-Flex availability in Milan, and Azure ExpressRoute resiliency guard. Narrative generation 22 passed normal validation, the final evidence-only pass, and manual speech-readiness review. Its speech script and local WAV were generated, inspected, and listened to successfully.

The system has therefore reached a stable end-to-end baseline:

```text
RSS / Atom sources → candidate ingestion → editorial evaluation
→ current/diverse selection → contextual narrative synthesis
→ evidence-bounded editorial cleanup → human retention review
→ speech preparation → local WAV briefing
```

Latest milestone verification:

```text
Focused speech tests: 3 passed
make test-briefing: 159 passed
make test: 1,188 passed
git diff --check: passed
```

Operational artifacts are written under `outputs/briefing/editions/`, `outputs/briefing/narratives/`, `outputs/briefing/references/`, and `outputs/briefing/audio/`. The detailed design, commands, audit behavior, and operational findings are documented in [docs/daily-briefing.md](docs/daily-briefing.md).

Publishing, distribution, hosting, RSS, dashboard controls, music, multiple speakers, voice cloning, and cloud TTS remain out of scope. See [docs/daily-briefing.md](docs/daily-briefing.md) for configuration and troubleshooting.

## Longer-term possibilities

Potential future capabilities include:

- Additional private data sources beyond RSS
- GitHub project activity
- Personal project status
- Calendar information
- Selected email or notification sources
- User-defined briefing profiles
- Different weekday/weekend editions
- Weekly or project-specific briefings
- Interactive voice follow-up
- Asking the briefing system to explain an item in more depth
- Automatically identifying knowledge gaps or follow-up research opportunities
- Evaluating a slower speech rate, likely around 165–175 WPM
- Comparing additional locally available macOS voices
- Improving voice naturalness or optionally adopting a higher-quality local TTS engine
- Adding MP3/AAC when a lightweight reliable encoder is available
- Dashboard controls, publishing/distribution, podcast RSS, notifications, or automated delivery

These are polish and later-stage possibilities, not blockers for the completed baseline or current implementation commitments.

The guiding architectural principle remains:

```text
New information
      ↓
Editorial judgment
      ↓
Useful briefing
      ↓
Human-guided retention
      ↓
Durable knowledge
```

---

## Phase 2 Roadmap

Phase 1–13 delivered a fully operational pipeline. Phase 2 focuses on making the knowledge graph richer, more trustworthy, and faster to query — in that order.

**Sequencing principle:** enrich graph → measure integrity → reduce capture friction → add retrieval layer. No managed cloud services at any phase.

---

### Phase 2A — Knowledge Usability

Make the existing graph denser and traversable before investing in UI.

| Step | Task | Notes |
|------|------|-------|
| 2A-1 | **Graph Health Baseline** | Complete. `scripts/graph_health.py` measures note counts, wikilink density, stub ratio, orphan count, source coverage, and gap ranking; snapshots are saved under `outputs/domains/<slug>/graph_health/`. |
| 2A-2 | **Concept Definitions** | Complete for the current AI domain pass. `scripts/define_concepts.py` wrote grounded definitions for 26 concept stubs and skipped low-evidence concepts with fewer than two source excerpts. Current AI-domain stub ratio: 39.2%. |
| 2A-3 | **Wikilink Injection** | Complete and tightened. Topic/source-summary notes were back-annotated with concept/entity links, artifact/path-like extractions were filtered from future concept aggregation, and the AI graph now reports zero orphan concepts/entities. |
| 2A-4 | **Concepts/Entities Browser** | Next. Build a dashboard view for browsing concepts/entities, showing definitions, linked topics, source summaries, entity type, stub status, and graph-health signals. |

Current AI-domain graph status after 2A tightening:

- Topics: 10
- Concepts: 51
- Entities: 25
- Source summaries: 16
- Topic wikilink density: 9.70
- Source-summary wikilink density: 4.00
- Concept stub ratio: 39.2%
- Orphan concepts/entities: 0
- Latest snapshot: `outputs/domains/ai/graph_health/2026-06-30-212341.json`

Current post-ingest maintenance sequence after approving new source summaries:

```bash
python3 scripts/concept_aggregator.py --all
python3 scripts/define_concepts.py
python3 scripts/inject_wikilinks.py
python3 scripts/index_notes.py --no-commit
python3 scripts/vector_index.py update
python3 scripts/graph_health.py
```

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

---

### Future Enhancement — Document Ingestion Engine

Evaluate a document ingestion engine for uploaded source files such as PDF, DOCX, PPTX, and other project document formats. Current ingestion supports text/Markdown, HTML-to-text, and extractable-text PDFs; Docling is a candidate parser to investigate for higher-fidelity local document conversion before handoff to the existing knowledge-base pipeline.

Potential workflow:

1. User uploads a PDF, DOCX, PPTX, or similar source document.
2. Docling parses the document and extracts structured content.
3. Parsed output is converted to Markdown and/or JSON.
4. The Knowledge Base pipeline chunks, tags, and indexes the content.
5. The content becomes searchable and usable by the knowledge base app.

Possible use cases include ingesting project documents, requirements documents, architecture PDFs, vendor documentation, and meeting notes; extracting headings, sections, tables, and document metadata; handling scanned PDFs/OCR and table-heavy documents; preparing content for RAG/search workflows; and generating human-readable Markdown for the knowledge base while retaining structured JSON for application processing.

This is exploratory only. Docling is not yet selected as the final implementation choice, and future evaluation should compare it against simpler parsers and existing document loaders before adding dependencies or ingestion logic. Evaluation criteria should include local/offline behavior, dependency footprint, supported formats, OCR and table extraction quality, metadata preservation, Markdown/JSON output quality, chunking quality, and fallback behavior versus the current `pypdf` path.

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

### Next Steps

1. Build Phase 2A-4 Concepts/Entities Browser in the dashboard.
2. Add entity/concept detail API endpoints if the current dashboard routes do not expose enough metadata.
3. Use graph-health snapshots to show stub/orphan/source-coverage signals in the browser.
4. Continue reducing concept stubs with targeted source collection or manual definitions for high-value notes.
5. Run a separate Docling spike before committing to new ingestion dependencies.

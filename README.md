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
        +-> query.py / Query tab -> outputs/answers/
        +-> resynthesize_topic.py / Topic Management -> refreshed topic note
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

Scoped query: `python3 scripts/query.py --topic openclaw-security "your question"`

Search: `python3 scripts/search.py "keyword"`

Pipeline log: `python3 scripts/log.py`

Lint: `python3 scripts/lint.py`

Open in Obsidian: point a vault at `compiled/`

## Pipeline Scripts

| Script | What it does |
|--------|-------------|
| `apply_synthesis.py` | Applies raw LLM output to durable compiled notes or answer artifacts. |
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

## Roadmap

- Concept & Entity pages
- Backfill cleanup for generic-named legacy articles
- Two-machine sync with a git remote

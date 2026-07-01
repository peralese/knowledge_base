# Project Context

## Project
knowledge_base

## Current State
- Domain-aware KBs implemented: multiple local domains (e.g., ai, civil-war-history) with isolated directories under raw/metadata/compiled/outputs/indexes per domain; docs/domains.md covers architecture and migration/CLI.
- Fully operational, local-first pipeline with dashboard (localhost:7842), CLI scripts, and background services for ingestion, synthesis via local Ollama, review/approval, topic aggregation, indexing, search, and Obsidian-facing compiled vault.
- Integrity and quality tools delivered: query feedback loop, cross-topic contradiction detection, gap ranking, and staleness lint with reports saved under outputs/.
- Retrieval layer complete: BM25 plus SQLite-based vector index (nomic-embed-text via Ollama) with hybrid retrieval default and graceful BM25 fallback when index absent/stale.
- Capture ergonomics improved: mobile share-to-inbox API, enhanced review workflow (CLI interactive session and richer dashboard), saved searches, pinned topics, and recent entity activity.

## In Progress
- No explicit in-progress work found

## Open Issues
- Phase 2A items not marked complete: Graph Health Baseline, Concept Definitions, Wikilink Injection, Concepts/Entities Browser.
- Status of define_concepts.py and inject_wikilinks.py is implied by “Post-ingest sequence” but not listed under Pipeline Scripts; usage/flags not documented.
- Domain-aware migration exists per docs/domains.md, but current migration status of existing data is unclear.
- Vector index requires Ollama nomic-embed-text; without it, retrieval degrades to BM25 only.
- Future Document Ingestion Engine (e.g., Docling) is exploratory; parser not selected and no integration committed.

## Next Step
- Inferred: Run python3 scripts/concept_aggregator.py --all to extract concepts/entities from approved summaries as the foundation for 2A concept definitions and wikilink injection.

## Suggested Resume Prompt
"Resume the knowledge_base project. Confirm concepts/entities are aggregated (scripts/concept_aggregator.py --all), then proceed with Phase 2A by running scripts/define_concepts.py and scripts/inject_wikilinks.py, and finish with scripts/vector_index.py update and scripts/graph_health.py to baseline graph health."

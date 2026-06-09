# Project Context

## Project
knowledge_base

## Current State
- Multi-domain support implemented; dashboard and pipeline isolate domains with domain-scoped raw/metadata/compiled/outputs/indexes directories.
- Fully operational local-first pipeline: inbox/dashboard ingestion → Ollama synthesis → scoring/review → topic/concept aggregation → index; Obsidian opens compiled/ as the vault.
- Retrieval complete: BM25 plus SQLite-based vector index (nomic-embed-text via Ollama) with hybrid default and graceful BM25 fallback when index is absent/stale.
- Dashboard/CLI cover ingestion, review (interactive session, inline synthesis), query with saved searches and pinned topics; mobile share-to-inbox endpoints working.
- Integrity/maintenance tooling complete: query feedback loop, cross-topic contradiction detection, gap ranking, staleness lint; background services provided for continuous processing and weekly lint.

## In Progress
- No explicit in-progress work found

## Open Issues
- Phase 2A (Knowledge Usability) items not marked complete: graph health baseline, concept definitions, wikilink injection, concepts/entities browser.
- Embedding dependency: vector/hybrid retrieval requires ollama pull nomic-embed-text; without it, semantic recall relies on BM25 fallback.
- Domains migration exists in docs/domains.md; execution status for existing data not stated.
- Scripts referenced in post-ingest (define_concepts.py, inject_wikilinks.py) aren’t listed under Pipeline Scripts; operational status/documentation may be incomplete.

## Next Step
- Inferred: Run python3 scripts/graph_health.py to capture a pre-Phase-2A baseline snapshot (wikilink density, stub ratio, orphan count) before making graph-enrichment changes

## Suggested Resume Prompt
"Resume knowledge_base: kick off Phase 2A by running scripts/graph_health.py for a baseline, then proceed to concept definitions and wikilink injection if those scripts aren’t already in place."

# Project Context

## Project  
Knowledge-Base  

## Current State  
- Supports multiple local domains (ai, civil-war-history) with isolated reasoning spaces  
- Ingests URLs/files/feeds/notes into raw/ directory  
- Synthesizes source summaries with Ollama in compiled/source_summaries/  
- Aggregates approved knowledge into topic/concept notes in compiled/  
- Provides BM25 search and natural-language querying against compiled notes  
- Generates compiled/index.md for Obsidian vault integration  
- Runs health checks for wikilinks, orphans, and coverage  

## In Progress  
- Phase 2A: Graph Health Baseline, Concept Definitions, Wikilink Injection, Concepts/Entities Browser  
- Phase 2B: Query Feedback Loop, Cross-topic Contradiction Detection, Gap Ranking, Staleness Lint  
- Phase 2C: Mobile Share-to-Inbox, Review Workflow Improvements, Saved Searches/Pinned Topics  
- Phase 2D: SQLite-vec vector index, hybrid retrieval (BM25 + vector), post-ingest sequence automation  

## Open Issues  
- Avoid managed vector databases (cloud)  
- Avoid complex agent frameworks  
- Avoid model fine-tuning  
- Avoid auto-merge/auto-rewrite of contradictions  
- Avoid heavy dashboard UI before graph richness  
- Avoid auto-rewrite of notes  

## Next Step  
Run post-ingest sequence:  
```bash  
python3 scripts/concept_aggregator.py --all  
python3 scripts/define_concepts.py  
python3 scripts/inject_wikilinks.py  
python3 scripts/vector_index.py update  
python3 scripts/graph_health.py  
```  

## Suggested Resume Prompt  
"Resume pipeline after source approval: run concept aggregator, define concepts, inject wikilinks, update vector index, and check graph health"

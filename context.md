# Project Context

## Project
knowledge_base

## Current State
- Fully operational pipeline from Phase 1-13 with domain-aware flows and local-first research capabilities
- Knowledge graph has 10 topics, 51 concepts, 25 entities, 16 source summaries
- BM25 search and natural-language querying implemented with compiled wiki index
- Pipeline includes automation for synthesis, scoring, review, and git auto-commits
- Vector index using nomic-embed-text model with local SQLite-based storage

## In Progress
- Developing Phase 2A-4 Concepts/Entities Browser dashboard with graph-health signals
- Adding entity/concept detail API endpoints for metadata exposure
- Implementing hybrid retrieval (BM25 + vector) for semantic queries
- Evaluating Docling parser for document ingestion improvements

## Open Issues
- Need to compare Docling with simpler parsers for document ingestion
- Ensure vector index maintenance excludes stub concepts and unapproved sources
- Avoid cloud dependencies while maintaining query performance
- Maintain graph health with ongoing source collection and definition work

## Next Step
Build Phase 2A-4 Concepts/Entities Browser in the dashboard with stub/orphan/source-coverage signals

## Suggested Resume Prompt
"Continue developing the Concepts/Entities Browser dashboard with graph-health visualization"

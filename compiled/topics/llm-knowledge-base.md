---
title: "LLM Knowledge Base"
created: "2026-04-11"
sources: 
  - "karpathy-s-llm-knowledge-base-build-an-ai-second-brain.md"
tags: 
  - "topic"
  - "RAG pipelines"
  - "AI-powered personal knowledge management"
  - "Large language models (LLM)"
  - "karpathy-s-llm-knowledge-base-build-an-ai-second-brain"
status: "draft"
note_type: "topic"
compiled_from: 
  - "karpathy-s-llm-knowledge-base-build-an-ai-second-brain"
date_compiled: "2026-04-11"
topics: 
  - "RAG pipelines"
  - "AI-powered personal knowledge management"
  - "Large language models (LLM)"
confidence: "medium"
generation_method: "ollama_local"
---

# Summary

Karpathy's LLM knowledge base is a personal wiki system that uses large language models to compile and maintain structured information from various sources. The system consists of three main directories (`raw/`, `wiki/`, and `outputs/`), where the raw data is ingested into `raw/`, the LLM processes this data to create articles in `wiki/`, and query responses are stored in `outputs/`. This approach leverages active maintenance, including periodic linting passes for consistency checks. The system's simplicity enables easy setup with minimal tooling, focusing on efficient context management rather than traditional retrieval-based approaches.

# Key Insights

- **Active Maintenance Loop:** The LLM continuously updates and maintains the wiki by creating new articles or modifying existing ones based on newly added sources.
- **Three-Folder Architecture:** A simple yet effective structure that involves raw material ingestion (`raw/`), LLM-generated structured knowledge (`wiki/`), and query responses (`outputs/`).
- **Schema Configuration File:** Guides the LLM's operations by defining rules for data ingestion, article creation, backlinking, linting passes, and conflict resolution.
- **Context Window Utilization:** The system leverages large context windows of modern LLMs to avoid issues with chunk-based retrieval systems (RAG), ensuring full-context understanding during processing.

# Related Concepts

- RAG pipelines
- AI-powered personal knowledge management
- Large language models (LLM)

# Source Notes

- [[karpathy-s-llm-knowledge-base-build-an-ai-second-brain]]

# Source Highlights

## [[karpathy-s-llm-knowledge-base-build-an-ai-second-brain]]
The article provides a comprehensive explanation of Karpathy's approach to using LLMs for personal knowledge management. It details the three-folder structure, the role of the schema configuration file (`CLAUDE.md`), and the benefits of leveraging large context windows in modern LLMs.

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260411-0001
- Source path: /home/peralese/Projects/Knowledge_Base/raw/inbox/LLM_Knowledge_Base.md
- Canonical URL:

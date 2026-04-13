---
title: "LLM Knowledge Base"
note_type: "topic"
compiled_from: 
  - "karpathy-llm-knowledge-base-second-brain"
date_compiled: "2026-04-11"
topics: 
  - "Large Language Models (LLM)"
  - "Personal Knowledge Management"
  - "Obsidian Web Clipper"
  - "Markdown Files"
tags: 
  - "topic"
  - "Large Language Models (LLM)"
  - "Personal Knowledge Management"
  - "Obsidian Web Clipper"
  - "Markdown Files"
  - "karpathy-llm-knowledge-base-second-brain"
confidence: "medium"
generation_method: "ollama_local"
---

# Summary

The LLM Knowledge Base is a personal wiki system designed by Andrej Karpathy to build and maintain a structured knowledge base using large language models (LLMs). This system enables the automated writing, linking, categorizing, and consistency checking of articles based on raw research material. It consists of three main directories: `raw/`, `wiki/`, and `outputs/`. The LLM operates in two modes—compilation step and linting pass—to manage new source material and maintain wiki integrity, respectively. Unlike traditional RAG pipelines, it avoids document chunking and retrieval noise by leveraging the large context window of modern LLMs for efficient knowledge compilation.

# Key Insights

- **Three-Folder Architecture**: The system uses `raw/`, `wiki/`, and `outputs/` directories to manage raw sources, generated wiki articles, and query responses respectively.
- **LLM Roles**: The LLM performs tasks such as ingesting new sources, generating or updating wiki articles, creating backlinks, and running linting passes to maintain consistency.
- **Schema Configuration File**: An AGENTS.md file specifies rules for the LLM's operations like ingestion methods, index format, backlink generation, conflict resolution, and query responses.
- **Context Window Utilization**: Modern LLMs' large context window allows them to read full articles directly instead of using RAG pipelines for retrieval.

# Related Concepts

- Large Language Models (LLM)
- Personal Knowledge Management
- Obsidian Web Clipper
- Markdown Files

# Source Notes

- [[karpathy-llm-knowledge-base-second-brain]]

# Source Highlights

## [[karpathy-llm-knowledge-base-second-brain]]
- Title: Karpathy LLM Knowledge Base Second Brain
- Source Type: article
- Origin: web
- Summary: An overview of Andrej Karpathy's approach to using large language models for building a personal knowledge management system through automated wiki compilation.
- Notes:
  - The system relies on the Obsidian app and minimal tool choices such as Claude Code or Codex LLMs.
  - Steps provided for setting up one’s own LLM Knowledge Base.

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260411-0001
- Source path: /home/peralese/Projects/Knowledge_Base/raw/inbox/browser/karpathy-llm-knowledge-base-second-brain.md
- Canonical URL: https://ghost.codersera.com/blog/karpathy-karpathy-llm-knowledge-base-second-brain-second-brain/

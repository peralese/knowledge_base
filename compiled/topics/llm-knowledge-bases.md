---
title: "LLM Knowledge Bases"
note_type: "topic"
compiled_from: 
  - "how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis"
  - "llm-wiki-synthesis"
date_compiled: "2026-04-19"
date_updated: "2026-04-25"
topics:
  - "LLM Knowledge Bases"
tags:
  - "topic"
  - "llm-knowledge-bases"
confidence: "medium"
generation_method: "ollama_local"
approved: true
---

# Summary
This guide outlines the process of setting up an AI-driven knowledge base system known as LLM Wiki, inspired by Andrej Karpathy's approach. The setup involves using Obsidian for managing and navigating your knowledge base alongside Claude Code for automating tasks such as summarization and indexing. Key steps include preparing a directory structure, configuring Obsidian, creating a schema file (`claudefile.md`), ingesting raw data, processing with Claude code, and maintaining the system through regular linting operations. The guide highlights debates around Zettelkasten vs. mutable wiki page models, emphasizing immutable notes linked explicitly for reducing drift over time. Additionally, it discusses how LLM Wiki reduces cognitive load by automating maintenance tasks but faces limitations in scaling beyond 200K-300K tokens due to context window constraints.

# Key Insights
- **Directory Structure**: A well-defined directory structure (e.g., `raw`, `processed`, `outbox`) helps manage different stages of knowledge base files efficiently.
- **Claude Code Integration**: Utilizing Claude Code allows for automation of tasks such as data ingestion, summarization, and indexing, enhancing the efficiency of maintaining a large-scale knowledge base.
- **Obsidian Features**: Leveraging Obsidian's advanced features like backlinks, tags, and custom workspaces enables better organization and navigation within the knowledge base.
- **Regular Maintenance**: Regular linting operations are crucial for ensuring consistency and accuracy in the knowledge base over time.
- **Karpathy’s LLM Wiki Pattern**: This approach involves leveraging Large Language Models (LLMs) to create a wiki-like system for maintaining and updating knowledge, with an emphasis on immutability and explicit linking as per Zettelkasten principles.
- **Zettelkasten vs. Wiki Structure**: Using an immutable note structure linked explicitly can reduce drift over time compared to mutable wiki pages.
- **LLM Usage**: Ensuring that the LLM primarily generates new notes rather than rewriting existing ones helps maintain transparency and accuracy.
- **Immutable Raw Layer**: Every claim in the wiki should trace back to a source file stored in an immutable `raw` directory, helping mitigate quality degradation over repeated rewrites.
- **Hierarchical Navigation**: Reading index files instead of loading entire knowledge bases mitigates context window limitations by focusing on relevant pages only.
- **Schema Definition (`CLAUDE.MD`)**: Essential for defining how data should be structured and maintained within the wiki.
- **Three Core Operations**:
  - Ingest: Adding new information to the knowledge base.
  - Query: Retrieving information from the knowledge base.
  - Lint: Checking consistency and correctness across the knowledge base.
- **Maintenance Overhead**: Reduces cognitive load on human users by handling maintenance tasks automatically, but faces limitations as projects scale beyond a certain size.

# Related Concepts
- **Knowledge Management Systems (KMS)**: Tools and techniques used to capture, organize, store, retrieve, share, enhance, and use collective expertise in an organization.
- **Obsidian**: A note-taking application that leverages local markdown files for organizing information with powerful features like backlinks and graph views.
- **Claude Code**: A set of scripts or commands designed to interact with the Claude language model API, enabling automation of tasks related to AI-driven knowledge base management.
- **LLM Wiki**: An advanced system that integrates large language models (LLMs) for maintaining a knowledge base through automated summarization, indexing, and navigation features.
- **RAG (Retrieval-Augmented Generation)**: A technique suitable for larger-scale systems managing thousands of sources requiring complex retrieval mechanisms.

# Source Notes

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis]]
- [[llm-wiki-synthesis]]

# Lineage

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis]]
- [[llm-wiki-synthesis]]

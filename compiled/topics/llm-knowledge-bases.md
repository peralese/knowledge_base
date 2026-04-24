---
title: "LLM Knowledge Bases"
note_type: "topic"
compiled_from: 
  - "how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis"
  - "llm-wiki-synthesis"
date_compiled: "2026-04-19"
date_updated: "2026-04-22"
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
This guide outlines the process of setting up an AI-driven knowledge base system known as LLM Wiki, inspired by Andrej [[karpathy]]'s approach. The setup involves using Obsidian for managing and navigating your knowledge base alongside Claude Code for automating tasks such as summarization and indexing. Key steps include preparing a directory structure, configuring Obsidian, creating a schema file (`claudefile.md`), ingesting raw data, processing with Claude code, and maintaining the system through regular linting operations. The new source highlights debates around Zettelkasten vs. mutable wiki page models, emphasizing the importance of immutable notes linked explicitly for reducing drift over time.

# Key Insights
- **Directory Structure**: A well-defined directory structure (e.g., `raw`, `processed`, `outbox`) helps in managing different stages of knowledge base files efficiently.
- **Claude Code Integration**: Utilizing Claude Code allows for automation of tasks such as data ingestion, summarization, and indexing, which significantly enhances the efficiency of maintaining a large-scale knowledge base.
- **Obsidian Features**: Leveraging Obsidian's advanced features like backlinks, tags, and custom workspaces enables better organization and navigation within the knowledge base.
- **Regular Maintenance**: Regular linting operations are crucial for ensuring that the knowledge base remains consistent and up-to-date over time.
- **Karpathy's LLM Wiki Pattern**: The approach described by Andrej Karpathy involves leveraging Large Language Models (LLMs) to create a wiki-like system for maintaining and updating knowledge.
- **Zettelkasten vs. Wiki Structure**: Using an immutable note structure linked explicitly as in Zettelkasten can reduce drift over time compared to mutable wiki pages.
- **LLM Usage**: Ensuring that the LLM primarily generates new notes rather than rewriting existing ones helps maintain transparency and accuracy.

# Related Concepts
- **Knowledge Management Systems (KMS)**: Tools and techniques used to capture, organize, store, retrieve, share, enhance, and use collective expertise in an organization.
- **Obsidian**: A note-taking application that leverages local markdown files for organizing information with powerful features like backlinks and graph views.
- **Claude Code**: A set of scripts or commands designed to interact with the Claude language model API, enabling automation of tasks related to AI-driven knowledge base management.
- **LLM Wiki**: An advanced system that integrates large language models (LLMs) for maintaining a knowledge base through automated summarization, indexing, and navigation features.

# Source Notes

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis]]
- [[llm-wiki-synthesis]]

# Lineage

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis]]
- [[llm-wiki-synthesis]]

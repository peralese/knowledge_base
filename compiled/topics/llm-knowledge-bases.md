---
title: "LLM Knowledge Bases"
note_type: "topic"
compiled_from: 
  - "how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis"
date_compiled: "2026-04-18"
date_updated: "2026-04-18"
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

The summary covers the creation of a Knowledge Base with an AI-powered system inspired by Andrej Karpathy's approach. This involves storing original sources in an immutable `raw` directory, leveraging LLMs to manage and maintain cross-references automatically through three key operations: Ingest, Query, and Lint. A schema file (`CLAUDE.md`) guides how the LLM processes new information. The Obsidian frontend provides a user-friendly interface for interacting with the knowledge base.

# Key Insights

1. **Immutable Raw Layer**: Storing original sources in an immutable layer ensures traceability of all claims.
2. **Automated Maintenance**: Use an LLM to handle updates and cross-references, reducing maintenance costs significantly.
3. **Three Core Operations**:
   - Ingest: Import new data and generate relevant pages.
   - Query: Retrieve information from the knowledge base efficiently.
   - Lint: Regularly check for accuracy and consistency in the wiki's content.
4. **Obsidian Integration**: Utilize Obsidian as a frontend to visualize and interact with the generated knowledge base.
5. **Schema File**: Define how sources should be processed using templates and prompts in `CLAUDE.md`.
6. **Context Navigation Pattern**: Optimize context loading for better performance by only including relevant parts.

# Related Concepts

- **LLM (Large Language Models)**: AI models that can generate human-like text based on provided input.
- **Immutable Layer**: A storage layer where data remains unchanged after initial creation, aiding in version control and traceability.
- **Cross-referencing**: The process of linking related information across different documents or parts of a knowledge base to provide context and clarity.
- **Knowledge Graphs**: Structures that represent knowledge as nodes (entities) connected by edges (relationships), often used to enhance the accessibility and understanding of complex datasets.
- **Frontend Tools for Knowledge Management**: Applications like Obsidian that facilitate interaction, visualization, and navigation within structured data environments.

# Source Notes

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis]]

# Lineage

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis]]

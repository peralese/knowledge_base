---
title: "How to Build Karpathy's LLM Wiki The Complete Guide to AI-Maintained Knowledge Bases Synthesis"
note_type: "source_summary"
compiled_from: 
  - "how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases"
date_compiled: "2026-04-25"
date_updated: "2026-04-25"
topics: []
tags: 
  - "source_summary"
  - "how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases"
confidence: "medium"
confidence_score: 0.75
generation_method: "ollama_local"
approved: false
---

Based on the provided content, here are some key points and notes regarding the LLM Wiki concept:

### Key Points

1. **Immutable Raw Layer**: Every claim in the wiki should trace back to a source file stored in an immutable `raw` directory.
2. **Hierarchical Navigation**: The pattern of reading index files and only relevant pages instead of loading the entire knowledge base mitigates context window limitations.
3. **Schema Definition (`CLAUDE.MD`)**: This is essential for defining how data should be structured and maintained within the wiki.
4. **Three Core Operations**:
   - **Ingest**: Adding new information to the knowledge base.
   - **Query**: Retrieving information from the knowledge base.
   - **Lint**: Checking consistency and correctness across the knowledge base.
5. **Obsidian as Frontend**: Obsidian is recommended for its capabilities in managing markdown files, creating links between notes, and visualizing complex relationships within the wiki.
6. **LLM Wiki vs RAG**:
   - **LLM Wiki** is suitable for personal or team-level projects with around 50-200 source documents where maintenance overhead is low.
   - **RAG (Retrieval-Augmented Generation)** might be more appropriate for larger-scale, multi-agent systems managing thousands of sources and requiring complex retrieval mechanisms.

### Notes

1. **Maintenance Overhead**: The core idea behind LLM Wiki is to reduce the cognitive load on human users by handling maintenance tasks like summarization and cross-referencing automatically.
2. **Quality Degradation**: Beyond a certain scale (around 200K-300K tokens), the quality of knowledge management may degrade due to context window limitations in large language models.
3. **Model Collapse Risk**: The use of an immutable `raw` directory and regular linting helps mitigate issues related to information degradation over repeated rewrites.

### Lineage

The concept is built upon Vannevar Bush's vision from his 1945 essay "As We May Think", which introduced the idea of the Memex. Unlike Bush’s manual system, the LLM Wiki automates the maintenance and cross-referencing processes using large language models.

### Criticisms

- **Lack of Internalization**: Some argue that relying on an AI to handle knowledge maintenance means humans might not fully internalize or deeply understand the content.
- **Complexity Ceiling**: As projects scale beyond a certain size, the complexity of managing the system increases significantly and may require more sophisticated solutions like RAG.

### Additional Resources

- **Research Papers**:
  - A-MEM: Agentic Memory for LLM Agents (2025)
  - Survey on Knowledge-Oriented RAG (2025)

- **Primary Sources**:
  - [Karpathy's Gist](https://gist.github.com/karpathy/6c14a2e4d3bea97f489b9d1efc8a2d8c)
  - llms.txt Specification
  - QMD (Local Markdown Search)

- **Community Projects**:
  - [llmwiki](https://github.com/lucasastorian/llmwiki) by Lucas Astorian
  - [obsidian-wiki](https://github.com/Ar9av/obsidian-wiki)
  - [second-brain](https://github.com/NicholasSpisak/second-brain)

These points and notes provide a comprehensive overview of the LLM Wiki concept, its benefits, limitations, and implementation details.

# Source Notes

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases]]


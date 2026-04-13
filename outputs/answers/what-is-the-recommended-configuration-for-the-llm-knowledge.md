---
title: "What is the recommended configuration for the LLM Knowledge"
output_type: "answer"
generated_from_query: "What is the recommended configuration for the LLM Knowledge Base?"
generated_on: "2026-04-11"
compiled_notes_used: 
  - "llm-knowledge-base"
generation_method: "ollama_local"
model: "qwen2.5:14b"
---

# Question

What is the recommended configuration for the LLM Knowledge Base?

# Answer

The recommended configuration for the LLM Knowledge Base includes a three-folder architecture (`raw/`, `wiki/`, and `outputs/`), an AGENTS.md file specifying operational rules, and reliance on Obsidian app with Claude Code or Codex LLMs.

### Supporting Details:
- **Three-Folder Architecture**: The system utilizes directories named `raw/`, `wiki/`, and `outputs/` to manage different stages of the knowledge compilation process (source material, generated wiki articles, and query responses respectively). This is cited in the "Key Insights" section under "LLM Knowledge Base".
  
- **Schema Configuration File (AGENTS.md)**: An AGENTS.md file outlines specific rules for LLM operations including ingestion methods, index format, backlink generation, conflict resolution, and how to handle queries. This detail is supported by the notes in the "Key Insights" section of the compiled knowledge base.

- **LLM and Tool Choices**: The setup relies on Obsidian app as a primary tool along with Claude Code or Codex LLMs for processing tasks within the system (as highlighted in "Source Highlights" under [[karpathy-llm-knowledge-base-second-brain]] notes).

# Sources Used

- [[llm-knowledge-base]]

# Lineage

- Generated on: 2026-04-11
- Model: qwen2.5:14b
- Notes in context: 1

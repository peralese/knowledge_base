---
title: LLM Knowledge Bases
type: topic
note_type: topic
slug: llm-knowledge-bases
sources:
  - compiled/source_summaries/how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis.md
  - compiled/source_summaries/llm-wiki-synthesis.md
compiled_from:
  - how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases-synthesis
  - llm-wiki-synthesis
date_created: 2026-04-19
date_compiled: 2026-04-19
date_updated: 2026-06-09
synthesis_version: 2
approved: true
---

# LLM Knowledge Bases

LLM (Large Language Model) Knowledge Bases represent a novel approach to managing and maintaining personal or team knowledge using AI-driven systems. The concept draws inspiration from Vannevar Bush's 1945 essay "As We May Think," which introduced the idea of the Memex, a theoretical device for storing and retrieving information. Unlike the manual system envisioned by Bush, LLM Knowledge Bases leverage large language models to automate the maintenance and cross-referencing processes within knowledge management systems.

At its core, an LLM Knowledge Base follows a hierarchical navigation pattern where each claim or piece of information is traceable back to a source file stored in an immutable `raw` directory. This ensures that all content has a clear provenance and minimizes the risk of degradation through repeated rewrites or modifications. The architecture of such systems includes three core operations: ingestion, querying, and linting. Ingestion involves adding new information to the knowledge base; querying retrieves relevant pieces of information based on user queries; and linting checks for consistency and correctness across the entire knowledge base.

One popular tool recommended for managing an LLM Knowledge Base is Obsidian, a note-taking application that excels in handling Markdown files, creating links between notes, and visualizing complex relationships within the wiki. The use of Obsidian helps maintain the structure and integrity of the knowledge base while facilitating easy navigation through hierarchical index files.

The concept of an LLM Wiki stands in contrast to RAG (Retrieval-Augmented Generation) systems, which are more suited for larger-scale projects with thousands of source documents and complex retrieval mechanisms. While an LLM Wiki is ideal for personal or team-level projects managing around 50-200 source documents, it may face limitations when scaling beyond a certain point due to context window constraints in large language models.

One significant advantage of the LLM Wiki approach is its ability to reduce cognitive load on human users by automating maintenance tasks such as summarization and cross-referencing. However, this automation also presents challenges, including potential issues with information degradation over repeated rewrites. To mitigate these risks, systems often incorporate an immutable `raw` directory and regular linting processes.

The LLM Wiki concept has gained traction through contributions from various community projects like llmwiki by Lucas Astorian and obsidian-wiki by Ar9av. These projects showcase practical implementations of the theory outlined by figures such as Andrej Karpathy, who provided initial insights into how these systems can be built and maintained effectively.

Despite its benefits, there are criticisms around the reliance on AI for knowledge maintenance, with some arguing that it may prevent humans from fully internalizing or deeply understanding content. Additionally, there is a noted complexity ceiling beyond which managing the system becomes challenging, necessitating more sophisticated solutions like RAG.

In summary, LLM Knowledge Bases offer a promising framework for personal and team-level knowledge management, leveraging large language models to automate maintenance tasks while maintaining integrity through immutable storage and regular linting checks. This approach strikes a balance between manual oversight and automated efficiency, making it an attractive option for those looking to enhance their knowledge work practices with AI-driven tools.

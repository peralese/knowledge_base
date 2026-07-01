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
synthesis_version: 3
approved: true
---

# LLM Knowledge Bases

In an era where data is abundant yet fragmented, the concept of Large Language Model (LLM) knowledge bases emerges as a pivotal innovation for synthesizing and managing information. These knowledge bases empower users to harness AI-driven systems for personal or collaborative knowledge work by maintaining dynamic, structured repositories of insights and ideas. The LLM Wiki pattern, championed by [[andrej-karpathy]], represents one such approach that stands out for its ability to automate maintenance tasks like summarization and cross-referencing while balancing usability with technical efficiency.

At the core of an LLM Wiki is the **immutable raw layer**, a foundational component where every claim traces back to a source file stored in a non-alterable `raw` directory. This immutability ensures that information remains consistent over time, mitigating risks like model collapse and data degradation—a critical advantage as the system scales. The structured approach also includes hierarchical navigation strategies, allowing users to read index files and selectively access relevant pages rather than loading entire knowledge bases, thereby addressing context window limitations inherent in [[large-language-models]].

A key architectural element of this pattern is the **schema definition**, typically encapsulated within a file like `CLAUDE.MD`. This schema serves as a blueprint for organizing data, ensuring that information remains well-structured and accessible. The system revolves around three core operations: **ingest** (adding new information), **query** (retrieving existing knowledge), and **lint** (ensuring consistency and correctness). These processes are streamlined through tools like Obsidian, which is favored for its ability to manage markdown files efficiently, create interconnections between notes, and visualize complex relationships within the wiki.

The LLM Wiki pattern holds particular appeal for personal or team-level projects, accommodating roughly 50-200 source documents where maintenance overhead remains manageable. In contrast, for larger-scale systems managing thousands of sources, **RAG (Retrieval-Augmented Generation)** might be more appropriate due to its sophisticated retrieval mechanisms necessary for complex, multi-agent environments.

However, the adoption of LLM Wikis is not without challenges and tradeoffs. While the system reduces cognitive load by automating many maintenance tasks, it introduces complexities as projects scale. Beyond a certain token threshold (approximately 200K-300K tokens), users may encounter quality degradation due to the context window limitations of [[large-language-models]]. Regular linting and the use of an immutable `raw` directory are strategies employed to mitigate such issues, ensuring information integrity over repeated rewrites.

Tracing its lineage back to Vannevar Bush's visionary concept of the Memex from his 1945 essay "As We May Think," the LLM Wiki automates what was once a manual process of maintenance and cross-referencing using AI-driven tools. This automation raises some criticisms, including concerns about **lack of internalization**—the idea that humans may not deeply understand content they rely on AIs to manage—and the **complexity ceiling**, where managing growing systems could necessitate more sophisticated solutions like RAG.

Community projects and research continue to evolve this space. Notable contributions include Lucas Astorian’s [llmwiki](https://github.com/lucasastorian/llmwiki) and Nicholas Spisak's [second-brain](https://github.com/NicholasSpisak/second-brain), alongside tools like the Obsidian plugin by Ar9av ([obsidian-wiki](https://github.com/Ar9av/obsidian-wiki)). Research papers such as "A-MEM: Agentic Memory for LLM Agents" and studies on knowledge-oriented RAG provide further insights into enhancing these systems.

In sum, LLM Knowledge Bases like the LLM Wiki represent a significant advancement in personal knowledge management, blending structured data organization with AI-driven automation to foster more efficient and scalable information synthesis. As users navigate the tradeoffs between complexity and functionality, ongoing research and community contributions continue to refine these tools for broader applications.

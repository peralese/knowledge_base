---
title: "How to Build Karpathy's LLM Wiki The Complete Guide to AI-Maintained Knowledge Bases Synthesis"
note_type: "source_summary"
compiled_from: 
  - "how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases"
date_compiled: "2026-04-18"
date_updated: "2026-04-18"
topics: []
tags: 
  - "source_summary"
  - "how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases"
confidence: "medium"
confidence_score: 0.75
generation_method: "ollama_local"
approved: true
---

Here's a summary of the key points and setup instructions for creating an LLM Wiki using Claude Code, based on Andrej Karpathy's pattern:

### Key Points

1. **Immutable Raw Layer**: Store original sources in an immutable `raw` directory. This ensures that every claim in your wiki can be traced back to its source.

2. **Automated Maintenance**: The cost of maintaining cross-references and summaries is near zero because the LLM handles this automatically on each ingest.

3. **Three Operations**:
   - **Ingest**: Import new sources and generate concept pages.
   - **Query**: Ask questions about your knowledge base, which the LLM will navigate based on the index.
   - **Lint**: Regularly check for consistency and drift in your wiki.

4. **Obsidian Frontend**: Use Obsidian to visualize and interact with your wiki. It provides a user-friendly interface for exploring cross-references.

5. **Schema File (`CLAUDE.md`)**: Define prompts, templates, and metadata structure for how the LLM should process sources.

6. **Context Navigation Pattern**: Instead of loading the entire wiki into context, load only relevant parts based on an index file. This avoids degradation from large context windows.

### Setting Up Your LLM Wiki with Claude Code

#### Step 1: Set Up Directory Structure
```sh
mkdir -p my-wiki/raw
mkdir -p my-wiki/wiki
touch my-wiki/CLAUDE.md
```

#### Step 2: Define Schema (`my-wiki/CLAUDE.md`)
Create a schema file that defines how your LLM should process new sources. This includes templates for concept pages and metadata.

Example `CLAUDE.md`:
```yaml
---
version: "1.0"
templates:
  - name: concept_page_template
    prompt: |
      Create a concise summary of the given text, highlighting key points and relevant connections.
      Summary should be in markdown format with headers for each major topic.
```

#### Step 3: Ingest New Sources
Place new sources into the `raw` directory. Then run Claude Code to generate corresponding wiki pages.

```sh
claudectl ingest my-wiki/raw/source1.txt --schema=CLAUDE.md
```

#### Step 4: Query Your Wiki
Ask questions or make queries about your knowledge base, which the LLM will process based on the generated index and schema.

Example query:
```sh
claudectl query "What are the main points from source1.txt?"
```

#### Step 5: Regularly Lint Your Wiki
Periodically run linting operations to ensure consistency and accuracy of your wiki content.

```sh
claudectl lint my-wiki/wiki
```

### Using Obsidian as the Frontend

- **Install Obsidian**: Download and install Obsidian from their official website.
- **Import Files**: Import your `my-wiki/wiki` directory into Obsidian to visualize cross-references and explore concepts.

### Criticisms and Limitations

1. **Learning vs Maintenance**: Some argue that the grunt work of maintaining a knowledge base is where deep understanding forms. However, proponents claim this system aids in comprehension rather than replacing it.
2. **Context Window Degradation**: Quality may degrade as the wiki grows beyond what fits into context windows (around 200K-300K tokens).
3. **Model Collapse Risk**: Repeated rewriting by LLMs might introduce subtle errors over time, but having an immutable raw layer mitigates this risk.
4. **Complexity Ceiling**: The pattern works best for personal/team knowledge at the 50-200 source scale.

### Community Resources

Explore open-source projects and discussions to further enhance your LLM Wiki:
- [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki)
- [Ar9av/obsidian-wiki](https://github.com/Ar9av/obsidian-wiki)

This setup provides a solid foundation for building an intelligent and maintainable knowledge base using LLMs.

# Source Notes

- [[how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases]]


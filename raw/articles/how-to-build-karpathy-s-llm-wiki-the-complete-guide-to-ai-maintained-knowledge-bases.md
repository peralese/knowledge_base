---
title: "How to Build Karpathy's LLM Wiki: The Complete Guide to AI-Maintained Knowledge Bases"
source_type: "article"
origin: "web"
date_ingested: "2026-04-19"
status: "raw"
topics: 
  - "llm-knowledge-bases"
tags: 
  - "Karpathy"
  - "Knowledge Base"
author: "Dylan Boudro"
date_published: "2026-04-09"
source_id: "SRC-20260419-0006"
canonical_url: "https://blog.starmorph.com/blog/karpathy-llm-wiki-knowledge-base-guide"
related_sources: []
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

---
title: How to Build Karpathy's LLM Wiki: The Complete Guide to AI-Maintained Knowledge Bases
source_type: article
origin: url
canonical_url: https://blog.starmorph.com/blog/karpathy-llm-wiki-knowledge-base-guide
topics:
  - llm-knowledge-bases
author: Dylan Boudro
date_published: 2026-04-09
tags:
  - Karpathy
  - Knowledge Base
---

<!-- topic_slug: llm-knowledge-bases -->

Starmorph
articlestopicsmermaideditor.io↗starmorph↗YouTube
Dark

Published onThursday, April 9, 202619 min read

How to Build Karpathy's LLM Wiki: The Complete Guide to AI-Maintained Knowledge Bases

Authors
NameDylan BoudroTwitterhttps://x.com/StarmorphAI

TL;DR: Andrej Karpathy's LLM Wiki is a pattern — not a product — where an LLM agent builds and maintains a structured markdown knowledge base from your raw sources. Three-layer architecture: raw/ (immutable sources), wiki/ (LLM-generated pages), and CLAUDE.md (schema). Three operations: ingest (process new sources), query (ask questions), lint (health checks). It replaces RAG with plain markdown for personal/team-scale knowledge. This guide covers the complete setup with Claude Code and Obsidian.

In April 2026, Andrej Karpathy posted on X about a workflow shift: instead of using LLMs primarily for code generation, he had been using them to build personal knowledge bases. The post went viral — 16+ million views — and the follow-up GitHub Gist hit 5,000+ stars within days. It touched a nerve because it solved a problem every knowledge worker has: knowledge bases that collapse under their own maintenance weight.

This guide breaks down the pattern, shows you how to build one from scratch with Claude Code and Obsidian, compares it to RAG, and surveys the community implementations that emerged within a week.

Table of Contents

Why Knowledge Bases Collapse

The Three-Layer Architecture

The Three Operations: Ingest, Query, Lint

Setting Up Your LLM Wiki with Claude Code

The Schema: Your Most Important File

Using Obsidian as the Frontend

LLM Wiki vs RAG: When to Use Which

Tooling and Infrastructure

Community Implementations

The Intellectual Lineage

Criticisms and Limitations

Sources

Why Knowledge Bases Collapse

Every developer has a graveyard of abandoned knowledge systems. Notion databases with 200 pages and no updates since month three. Bookmarks folders with 500 links and no summaries. Obsidian vaults with promising graphs that went stale. The problem isn't the tools — it's the maintenance cost.

Building a knowledge base has three steps: collect (easy), organize (hard), maintain (impossible at scale). The grunt work of filing, cross-referencing, summarizing, and updating is where systems die. Adding a single new article means reading it, creating a summary, linking it to existing concepts, updating related pages, and checking for contradictions with existing knowledge. Nobody does this consistently.

Karpathy's insight is simple: LLMs are uniquely good at exactly this kind of bookkeeping. They can read a document, identify key concepts, create structured summaries, generate cross-references, update indexes, and flag contradictions — tirelessly, consistently, at near-zero marginal cost. The human curates what goes in; the LLM does everything else.

"The LLM writes and maintains all of the data of the wiki. I rarely touch it directly." — Andrej Karpathy

At the time of the post, Karpathy's wiki on a single research topic had grown to approximately 100 articles and 400,000 words — longer than most PhD dissertations — without him writing any of it directly.

The Three-Layer Architecture

The LLM Wiki has a deliberately simple structure:

my-research/
├── raw/                    # Layer 1: Immutable source documents
│   ├── articles/
│   ├── papers/
│   ├── repos/
│   ├── data/
│   ├── images/
│   └── assets/
├── wiki/                   # Layer 2: LLM-generated markdown
│   ├── index.md            # Content catalog (updated on every ingest)
│   ├── log.md              # Append-only chronological record
│   ├── overview.md
│   ├── concepts/           # Concept pages
│   ├── entities/           # Entity pages
│   ├── sources/            # Source summaries
│   └── comparisons/        # Comparison pages
├── outputs/                # Dated reports, presentations
├── CLAUDE.md               # Layer 3: Schema configuration
└── .gitignore

Layer 1: Raw Sources (raw/)

Your curated collection of source documents — articles, papers, code repos, datasets, images. The LLM reads these but never modifies them. They serve as the verification baseline: every claim in the wiki traces back to a file in raw/.

Think of raw/ as immutable input. You can use the Obsidian Web Clipper browser extension to convert web articles to markdown and drop them directly into raw/articles/.

Layer 2: The Wiki (wiki/)

LLM-generated markdown pages organized by type:

concepts/ — Concept pages (e.g., attention-mechanism.md, rag.md)

entities/ — Entity pages (e.g., openai.md, anthropic.md)

sources/ — Source summaries (one per ingested document)

comparisons/ — Comparison pages (e.g., rag-vs-fine-tuning.md)

Two structural files are critical:

index.md — Content catalog. Updated on every ingest. The LLM reads this first to navigate the wiki.

log.md — Append-only operation log. Records every ingest, every page update, every contradiction found.

The LLM maintains everything in this directory. Humans mostly read; the LLM mostly writes.

Layer 3: The Schema (CLAUDE.md)

The most important file in the system. It defines the wiki's structure, naming conventions, page templates, and operational workflows. It transforms a generic LLM into a disciplined knowledge worker.

Named CLAUDE.md because Karpathy uses Claude Code as his primary agent, but the concept applies to any LLM agent with file access.

related
Obsidian + Claude Code: The Complete Integration Guide
5 strategies for connecting Obsidian with Claude Code — symlinks, MCP bridges, vault organization, and community workflows.

The Three Operations: Ingest, Query, Lint

The LLM Wiki pattern defines three core operations. Karpathy frames the system using a compiler analogy: raw/ is source code, the LLM is the compiler, wiki/ is the executable output, lint is tests, and queries are runtime.

Ingest

You drop a new source into raw/ and tell the LLM to process it.

> I added a new article to raw/articles/. Please ingest it.

The LLM:

Reads the document and discusses key takeaways

Creates a summary page in wiki/sources/

Cascades updates across 10-15 related wiki pages

Creates new concept or entity pages if needed

Updates index.md with new entries

Appends to log.md with affected pages and noteworthy findings

A single ingest operation can touch dozens of wiki pages as the LLM traces implications across the knowledge graph.

Query

You ask questions against the wiki. The LLM searches index.md, reads relevant pages, and synthesizes answers with citations.

> What are the key differences between sparse and dense retrieval?

The LLM navigates via the index instead of brute-force loading all documents into context. Valuable answers optionally get filed as permanent wiki pages — knowledge compounds.

Lint

Periodic health checks. The LLM scans for:

Contradictions — claims that conflict between pages

Orphan pages — wiki pages with no incoming links

Missing concepts — topics referenced but not yet given their own page

Stale claims — assertions superseded by newer sources

Investigation gaps — areas where more research is needed

Think of it as eslint for knowledge. You can schedule lint operations (daily, weekly) or run them ad hoc.

> Please lint the wiki. Focus on contradictions and stale claims.

Setting Up Your LLM Wiki with Claude Code

Step 1: Create the directory structure

mkdir -p ~/research/my-topic/{raw/{articles,papers,repos,data,images},wiki/{concepts,entities,sources,comparisons},outputs}
touch ~/research/my-topic/wiki/index.md
touch ~/research/my-topic/wiki/log.md

Step 2: Initialize Git

cd ~/research/my-topic
git init
echo "outputs/*.pdf" >> .gitignore

Version control is essential. Every wiki update becomes a trackable diff. You can revert bad ingests, review how concepts evolved, and use git log as an audit trail.

Step 3: Create the CLAUDE.md schema

This is the critical step. See the full schema section below for a complete template.

Step 4: Add your first sources

Drop markdown files, PDFs, or code into raw/. Use the Obsidian Web Clipper or a tool like Markdownload to convert web articles.

Step 5: Run Claude Code and ingest

cd ~/research/my-topic
claude

> I've added 3 articles to raw/articles/. Please ingest them all,
> create wiki pages, and update the index.

Claude Code will read each source, create structured wiki pages, establish cross-references, and update the index — all in a single operation.

The Schema: Your Most Important File

The schema file (CLAUDE.md) is what makes the pattern work. Without it, the LLM produces inconsistent output. With it, the LLM becomes a reliable knowledge worker. Here is a production-ready template:

# Research Wiki: [Your Topic]

## Project Structure

- `raw/` — Immutable source documents. Never modify files here.
- `wiki/` — LLM-generated and maintained markdown pages.
- `wiki/index.md` — Master content catalog. Update on every operation.
- `wiki/log.md` — Append-only operation log.
- `outputs/` — Generated reports, presentations, lint results.

## Page Types and Conventions

Every wiki page must have YAML frontmatter:

    ---
    title: Page Title
    type: concept | entity | source-summary | comparison
    sources:
      - raw/papers/filename.md
    related:
      - "[[related-concept]]"
    created: YYYY-MM-DD
    updated: YYYY-MM-DD
    confidence: high | medium | low
    ---

### Naming

- Filenames: kebab-case matching the concept (e.g., attention-mechanism.md)
- Cross-references: use for all internal links
- Source references: always link back to raw/ file paths

## Workflows

### Ingest

1. Read the source document in raw/
2. Discuss key takeaways with the user
3. Create wiki/sources/[source-name].md summary
4. Update or create concept/entity pages as needed
5. Update wiki/index.md with new entries
6. Append to wiki/log.md

### Query

1. Read wiki/index.md to identify relevant pages
2. Read those pages and synthesize an answer
3. Cite sources 
4. If the answer is novel and valuable, offer to save it as a new wiki page

### Lint

1. Scan all wiki pages for contradictions
2. Identify orphan pages (no incoming links)
3. Flag missing concepts referenced but not created
4. Find stale claims superseded by newer sources
5. Save results to outputs/lint-YYYY-MM-DD.md

Customize this template for your domain. A machine learning wiki might add conventions for tracking paper citations and benchmark results. A competitive intelligence wiki might add conventions for confidence levels and source freshness.

Using Obsidian as the Frontend

Obsidian is the recommended frontend for viewing and navigating the wiki. Open the wiki/ directory as an Obsidian vault and you get:

Graph View

Every wikilink the LLM creates becomes a visible connection in Obsidian's graph view. As the wiki grows, the graph reveals natural knowledge clusters — which concepts are central, which are isolated, where the gaps are.

Backlinks

Click any wiki page and see every other page that references it. This is enormously valuable for understanding how concepts connect without having to manually maintain relationship lists.

Dataview Queries

If you install the Dataview plugin, you can query across all wiki pages:

```dataview
TABLE type, confidence, updated
FROM "concepts"
WHERE confidence = "low"
SORT updated ASC
```

This query surfaces your least-confident knowledge — the areas where more research is needed.

QMD for Search

Tobi Lutke (Shopify CEO) built QMD, a local search engine for markdown files. It uses hybrid BM25/vector search with LLM re-ranking. Karpathy recommends it as the search layer for LLM Wikis. It's available as both a CLI and an MCP server, so Claude Code can use it to navigate large wikis efficiently.

related
Local LLM Inference in 2026: The Complete Guide
Run models locally for Obsidian AI plugins and local LLM Wiki agents — Ollama, LM Studio, vLLM, and more.

LLM Wiki vs RAG: When to Use Which

This is the biggest conceptual distinction in the pattern. Karpathy positions the LLM Wiki as a simpler alternative to RAG for personal and team-scale knowledge.

DimensionRAGLLM Wiki

StateStateless — each query is independentStateful — knowledge compounds over time

InfrastructureVector DB, embedding pipeline, retrieval logicFolder of .md files

Cross-referencesDiscovered ad-hoc per queryPre-built by the LLM, always available

MaintenanceEmbedding updates, index rebuildsLLM updates pages on every ingest

Token cost per queryHigh (retrieve + re-rank + generate)Low (read index + targeted pages)

TraceabilityChunk-level citations (often lossy)Source-level citations back to raw/

Scale sweet spotEnterprise (millions of documents)Personal/team (sub-100K tokens of wiki)

ContradictionsUndetected — conflicting chunks coexistFlagged during lint operations

When RAG wins

You have millions of documents and can't pre-compile them all

Documents change frequently and re-ingesting the entire wiki is impractical

You need sub-second query latency at scale

Your knowledge base is shared across many teams with different access levels

When LLM Wiki wins

You have fewer than ~100-200 source documents

You want knowledge to compound — each ingested source improves all future queries

You care about traceability (every claim links to a raw source)

You want zero infrastructure beyond a folder and an LLM

You value consistency checks (lint) over raw retrieval speed

The LLM Wiki is essentially a manual, traceable implementation of Graph RAG — each claim links back to sources, relationships are explicit, and the structure is human-readable. But unlike Graph RAG, it requires no graph database, no entity extraction pipeline, and no ontology engineering.

> Mermaid Editor

Visualize your LLM Wiki's knowledge graph structure with interactive Mermaid diagrams — export them as SVGs for documentation or presentations.
[Try Free]

Tooling and Infrastructure

Minimum Viable Stack

ToolPurposeRequired?

Claude Code (or any LLM agent)Wiki compiler — reads sources, generates pagesYes

A folderStorage for raw/, wiki/, CLAUDE.mdYes

GitVersion control for the entire knowledge baseRecommended

That's it. No vector database, no embedding pipeline, no cloud service. The entire system runs on markdown files and an LLM.

Recommended Stack

ToolPurposeLink

Claude CodePrimary LLM agentclaude.ai

ObsidianWiki frontend — graph view, backlinks, searchobsidian.md

QMDSemantic search over markdown (BM25 + vector + LLM re-rank)github.com/tobi/qmd

Obsidian Web ClipperConvert web articles to markdown for raw/obsidian.md/clipper

DataviewStructured queries across wiki frontmatterObsidian plugin

MarpConvert markdown wiki pages to presentation slidesmarp.app

GitVersion control and change trackingBuilt-in

Claude Code Skills for Wiki Management

You can create Claude Code skills to standardize wiki operations:

# /wiki-ingest skill

Read all new files in raw/ that aren't already in wiki/sources/.
For each new file:

1. Create a summary in wiki/sources/
2. Update or create concept and entity pages
3. Update wiki/index.md
4. Append to wiki/log.md
   Report what changed.

# /wiki-lint skill

Scan the entire wiki/ directory.
Check for:

- Contradictions between pages
- Orphan pages (no incoming wikilinks)
- Missing concepts (referenced but no page exists)
- Low-confidence pages that haven't been updated recently
  Save results to outputs/lint-[today's date].md

The community has already built several skill packages. wiki-skills and karpathy-llm-wiki both provide drop-in Claude Code skills implementing the pattern.

Community Implementations

Within a week of Karpathy's post, the community built multiple implementations. Here are the most notable:

ProjectDescriptionLink

llmwikiUpload docs, connect Claude via MCP, have it write your wikigithub.com/lucasastorian/llmwiki

obsidian-wikiFramework for AI agents to build Obsidian wikis using the Karpathy patterngithub.com/Ar9av/obsidian-wiki

second-brainLLM-maintained personal knowledge base for Obsidiangithub.com/NicholasSpisak/second-brain

llm-wiki-compilerCompiles markdown knowledge files into topic-based wikisgithub.com/ussumant/llm-wiki-compiler

CacheZeroOne npm install implementation of the patternHacker News

wiki-skillsClaude Code skills implementing the Karpathy patterngithub.com/kfchou/wiki-skills

LLM Wiki v2Extended pattern with memory lifecycle and confidence scoringGist

Real-World Results

User vbarsoum on Hacker News shared results from applying the pattern to three business books (~155K words): chapter-level granularity produced 210 concept pages with approximately 4,600 cross-references and unprompted synthesis across sources. The system wasn't just summarizing — it was identifying patterns and connections across books that the user hadn't seen.

LLM Wiki v2: Extended Pattern

Developer rohitg00 extended the pattern with lessons from building an agent memory system. Key additions:

Memory lifecycle: Confidence scoring, supersession tracking, retention decay (Ebbinghaus forgetting curve)

Consolidation tiers: Working memory → episodic memory → semantic memory → procedural memory

Knowledge graph structure: Typed entities and relationship categories ("uses," "depends on," "contradicts," "supersedes")

Multi-agent governance: Shared vs private knowledge scoping for parallel agents

These extensions become relevant as wikis grow beyond ~100-200 pages, where simple index navigation starts to degrade.

related
Best Mac Mini for Running Local LLMs in 2026
The hardware side — which Mac Mini to buy for running local models that can power your LLM Wiki agent.

The Intellectual Lineage

Karpathy's Gist explicitly references Vannevar Bush's 1945 essay "As We May Think", which described a hypothetical device called the Memex — a mechanical desk that would store and cross-reference all of a person's books, records, and communications with associative trails between related items.

The Memex never worked because maintenance was manual. Every cross-reference had to be created by hand. Bush imagined operators building "trails" through knowledge, but nobody actually does this at scale.

The LLM Wiki solves the maintenance problem: "The wiki stays maintained because the cost of maintenance is near zero." The LLM creates and updates cross-references automatically on every ingest. The human focuses on what matters — deciding what to read and what questions to ask.

Karpathy's Evolution

The LLM Wiki represents the third phase of Karpathy's thinking about human-AI collaboration:

Vibe Coding (Feb 2025) — Accept AI-generated code without reviewing it line-by-line. Trust the model, test the output.

Agentic Engineering (Jan 2026) — Humans orchestrate AI agents rather than writing code directly.

LLM Knowledge Bases (Apr 2026) — AI manages knowledge, not just code. The human is a curator, not a writer.

Each phase shifts more cognitive labor to the LLM while keeping humans in the loop for judgment and direction.

Related Efforts

Jeremy Howard's llms.txt — A website-level standard for helping external LLMs understand your site. Outward-facing (help LLMs understand you) vs the LLM Wiki's inward-facing (use LLMs to understand your domain). Both share the philosophy that markdown is the ideal format for LLM consumption.

Simon Willison's docs-for-llms — Build scripts to create LLM-friendly concatenated documentation. Focused on making existing docs consumable rather than having the LLM generate new knowledge.

Tobi Lutke's QMD — The local search engine Karpathy recommends. Built by the Shopify CEO, which signals adoption at the highest levels of tech leadership.

Criticisms and Limitations

The pattern is not without critics. Key concerns from the Hacker News discussion:

"The grunt work IS the learning"

User qaadika argued that the bookkeeping Karpathy outsources — filing, cross-referencing, summarizing — is where genuine understanding forms. By handing this to an LLM, you surrender the cognitive process that creates deep knowledge. You end up with a comprehensive wiki you haven't actually internalized.

Counter: The wiki is a reference system, not a replacement for thinking. Karpathy still reads sources, discusses takeaways with the LLM, and makes judgment calls about what to include. The LLM handles logistics, not insight.

Context window degradation

Multiple users reported that quality degrades when the wiki grows beyond what fits in context. Despite 1M+ token context windows, practical degradation starts around 200K-300K tokens. The LLM starts missing connections or producing inconsistent pages.

Mitigation: This is why the index/navigation pattern matters. Instead of loading the entire wiki, the LLM reads index.md (a few thousand tokens), identifies relevant pages, and reads only those. Hierarchical navigation sidesteps brute-force context stuffing.

Model collapse risk

devnullbrain raised concerns about information degradation through repeated LLM rewriting — the wiki version of model collapse. Each rewrite potentially introduces subtle errors that compound over time.

Mitigation: The immutable raw/ layer is the safeguard. Every claim in the wiki should trace back to a source in raw/. Lint operations check for drift. And Git provides full history to identify when claims changed.

Complexity ceiling

kubb warned that these systems collapse beyond certain complexity thresholds when neither the agent nor the developer maintains sufficient comprehension of the whole.

Mitigation: This is a real constraint. The pattern works best for personal/team knowledge at the 50-200 source scale. Beyond that, you likely need the extensions from LLM Wiki v2 (hybrid search, multi-agent governance) or a proper RAG pipeline.

> StarMorph Config

Managing CLAUDE.md schemas, dotfiles, and AI agent configs across projects? StarMorph Config keeps everything versioned and in sync.
[Browse Configs]

Sources

Research Papers
arXivA-MEM: Agentic Memory for LLM Agents (2025)arXivAgentic Retrieval-Augmented Generation: A Survey (2025)arXivSurvey on Knowledge-Oriented RAG (2025)arXivPersonalAI: Knowledge Graph Storage for LLM Agents (2025)arXivLLM-Empowered Knowledge Graph Construction Survey (2025)arXivDeep Research: A Survey of Autonomous Research Agents (2025)arXivIntegrating LLMs with Knowledge-Based Methods Survey (2025)
Primary Sources
Karpathy's LLM Wiki Gistllms.txt SpecificationQMD — Local Markdown Searchdocs-for-llms (Simon Willison)
Articles and Coverage

VentureBeat — Karpathy shares LLM Knowledge Base architecture

Analytics India Magazine — Karpathy Moves Beyond RAG

DAIR.AI Academy — LLM Knowledge Bases

MindStudio — How to Build a Personal Knowledge Base

MindStudio — LLM Wiki vs RAG Comparison

Analytics Vidhya — LLM Wiki Revolution

Community Projects

lucasastorian/llmwiki — Open-source LLM Wiki implementation

Ar9av/obsidian-wiki — Obsidian + LLM Wiki framework

NicholasSpisak/second-brain — LLM-maintained second brain

kfchou/wiki-skills — Claude Code wiki skills

Astro-Han/karpathy-llm-wiki — One-skill LLM Wiki

Hacker News Discussions

LLM Wiki — example of an "idea file"

Show HN: LLM Wiki Open-Source Implementation

Show HN: CacheZero — Karpathy's idea as one NPM install

View on GitHub
Share:

← Previous

LLM Model Names Decoded: A Developer's Guide to Parameters, Quantization & Formats

Next →

Apple Silicon LLM Inference Optimization: The Complete Guide to Maximum Performance

You might also like

Obsidian + Claude Code: The Complete Integration Guide

March 10, 2026 · 14 min read

obsidianclaude-codedeveloper-tools

AI Token Throughput Tracking Tools: The Complete Guide for Developers (2026)

March 27, 2026 · 22 min read

aideveloper-toolsclaude-code

10 More CLI Tools for AI Coding: Part 2 Terminal Workflow Guide

March 8, 2026 · 13 min read

cliterminaldeveloper-tools

On This Page

Table of Contents

Why Knowledge Bases Collapse

The Three-Layer Architecture

The Three Operations: Ingest, Query, Lint

Setting Up Your LLM Wiki with Claude Code

The Schema: Your Most Important File

Using Obsidian as the Frontend

LLM Wiki vs RAG: When to Use Which

Tooling and Infrastructure

Community Implementations

The Intellectual Lineage

Criticisms and Limitations

Sources

Tags

llm-wikiknowledge-baseclaude-codeobsidianai-toolsproductivitymarkdownkarpathyragdeveloper-tools

← Back to Blog

:github:twitter:youtube:linkedin:mail

© 2026 Starmorph AI> pixelmuse.studio

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260419-0006
- Source path: /home/peralese/Projects/Knowledge_Base/raw/inbox/browser/how-to-build-karpathy-s-llm-wiki-the-complete-guide-to-ai-maintained-knowledge-bases.md
- Canonical URL: https://blog.starmorph.com/blog/karpathy-llm-wiki-knowledge-base-guide


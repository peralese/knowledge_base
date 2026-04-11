---
title: "Karpathy's LLM Knowledge Base: Build an AI Second Brain"
source_type: "article"
origin: "local-markdown"
date_ingested: "2026-04-11"
status: "raw"
topics: []
tags: []
author: ""
date_created: ""
date_published: ""
language: "en"
summary: ""
source_id: "SRC-20260411-0001"
canonical_url: ""
related_sources: []
confidence: ""
license: ""
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

# Karpathy's LLM Knowledge Base: Build an AI Second Brain
On April 3, 2026, Andrej Karpathy posted something on X that resonated well beyond the usual AI news cycle. He wasn't announcing a new model or a benchmark result. He was describing a change in how he personally uses LLMs — a shift from generating code to generating _knowledge structure_. He called it the **Karpathy LLM knowledge base**, a form of AI-powered personal knowledge management that builds a self-maintaining wiki from raw research material. Within days the post had spawned a GitHub Gist, a wave of community implementations, and serious debate about whether this approach makes RAG pipelines obsolete for personal use.

This article breaks down exactly how Karpathy's system works, why he made the design choices he did, and how you can build an identical setup for your own research or engineering work.

What Karpathy's LLM Knowledge Base Actually Is
----------------------------------------------

Karpathy's framing is precise: he is spending a large fraction of his LLM token budget not on code generation but on _knowledge manipulation_. The system is a personal wiki — a collection of interlinked Markdown files — that an LLM writes and maintains autonomously as new source material is added.

The result at the time of posting: a single research topic had grown to roughly 100 articles and 400,000 words — longer than most PhD dissertations — without Karpathy writing a single word of it directly. The LLM does the writing, the linking, the categorizing, and the consistency checking.

What makes this different from AI-assisted note-taking tools like Notion AI or standard summary bots is the _active maintenance loop_. The LLM isn't just summarizing documents once. It is incrementally compiling a structured knowledge base, running "health checks" to detect inconsistencies, and generating backlinks as new concepts appear. It behaves less like a chatbot and more like a diligent research librarian who never sleeps.

The Three-Folder Architecture Behind Karpathy's Second Brain
------------------------------------------------------------

The entire system rests on three directories. The simplicity is intentional — Karpathy chose a structure that any LLM agent can navigate without custom tooling.

### raw/ — Ingesting Sources Without Friction

Raw source material goes directly into a folder called `raw/`. This includes research papers (PDFs converted to Markdown), GitHub repositories, web articles clipped via the Obsidian Web Clipper, datasets, meeting notes, and screenshots. The Obsidian Web Clipper converts web pages to `.md` files and saves images locally so the LLM can reference them through its vision capabilities — no external URLs, no link rot.

The raw folder is append-only. Nothing is edited here. It is the single source of truth for everything the LLM has ever read.

### wiki/ — Where the LLM Writes and Interlinks

The `wiki/` directory is where the LLM outputs structured knowledge. It writes encyclopedia-style articles for each concept it identifies across the raw material, creates backlinks between related articles, and maintains an index file that summarizes the entire wiki at a glance. When a new source is added to raw/, the LLM reads the existing index, identifies which wiki articles need to be updated or created, and runs a targeted update — it does not rewrite everything from scratch.

The format is pure Markdown throughout. This is deliberate: Markdown is the most compact, LLM-readable, and human-auditable structured format that exists. No proprietary schema, no vector embeddings — just files a human can open and read in any text editor or view through Obsidian's graph view.

### outputs/ — Derived Answers and Reports

The `outputs/` folder stores query responses, synthesized reports, and analysis results. When Karpathy asks a question — "what are the three most promising architectures for long-context reasoning?" — the LLM reads the wiki index, drills into relevant articles, and writes the answer to `outputs/` as a Markdown document. This gives every query a persistent, auditable record.

The Compilation Step and Linting Passes
---------------------------------------

Karpathy describes two modes of LLM operation in the system: the **compilation step** and the **linting pass**.

The **compilation step** happens when new material arrives in `raw/`. The LLM reads the new source, extracts key concepts, checks whether those concepts already exist as wiki articles, and either creates new articles or appends to existing ones. It then updates the index file and generates backlinks. At ~100 articles and 400,000 words, the entire wiki index fits comfortably within a modern LLM's context window, which means the LLM can check for duplicates and contradictions without any retrieval system.

The **linting pass** is a periodic "health check" that runs independently of new ingestion. The LLM scans the entire wiki for inconsistencies — articles that contradict each other, concepts mentioned in one article but lacking their own entry, index entries that are stale or missing. It can also identify gaps: topics that appear multiple times in the raw material but have no dedicated wiki article yet. These gaps become prompts for the LLM to author new content or flag the gap for human review.

The Schema Layer: AGENTS.md and CLAUDE.md
-----------------------------------------

The system has a third critical component that receives less attention than the three folders: the **schema configuration file**. In Karpathy's GitHub Gist "idea file," this is a `CLAUDE.md` file (for Claude Code) or `AGENTS.md` file (for Codex) that defines the rules the LLM must follow when operating the knowledge base.

The schema file specifies:

*   How to ingest different source types (papers vs. repos vs. web clips)
*   What the index file format looks like and how to update it
*   How to generate backlinks and what naming conventions to use for articles
*   What a linting pass should check for
*   How to handle conflicting information from multiple sources
*   Which queries go to `outputs/` and which are inline responses

Karpathy describes this schema as _co-evolved_ — he refines it over time based on how the wiki develops. The human's primary editorial role is not writing articles but writing and refining the schema that instructs the LLM on how to write them. If you think about it this way, the knowledge base is less a product of the LLM and more a product of Karpathy's instruction-writing — the LLM just executes at scale.

Why Karpathy's LLM Knowledge Base Skips RAG
-------------------------------------------

The standard enterprise answer to personal knowledge management at scale is a [RAG pipeline](https://ghost.codersera.com/blog/cag-vs-rag-which-augmented-generation-is-better/) — chunk your documents, embed them into a vector database, run similarity search at query time, and inject the retrieved chunks into the LLM context. Karpathy's approach deliberately skips this for personal use, and the reasoning is technically sound.

RAG's core problem is chunking: documents are split into fragments that lose their surrounding context. A paragraph from a research paper might be retrieved without the paragraph that defines the key term it uses. The LLM then has to work around that gap, which introduces retrieval noise and hallucination risk.

The Karpathy approach sidesteps chunking entirely. The wiki articles are already human-readable summaries of the raw material, written by an LLM that has read the full context. At query time, the LLM reads the wiki index — a compact summary of all 100+ articles — and pulls in the specific articles it needs. This is context-loading, not retrieval, and it works because modern LLMs have context windows large enough to hold the index plus several full articles simultaneously.

**When does RAG still win?** At scale beyond a few hundred articles or millions of words, the index itself becomes too large to fit in context, and retrieval becomes necessary again. Karpathy's approach is explicitly positioned for personal and small-team use — a single researcher's knowledge base, not a company-wide document store.

Karpathy's tool choices are minimal and pragmatic:

*   **Obsidian**: The "IDE frontend" for the knowledge base. Obsidian's graph view renders the backlinks between wiki articles as a visual network, making structural gaps and over-dense clusters visible at a glance. It also handles local file storage, which keeps the entire system portable and offline.
*   **Obsidian Web Clipper**: Converts web pages to Markdown and saves them to `raw/` with images stored locally. One-click ingestion from the browser into the knowledge base.
*   [**Claude Code**](https://ghost.codersera.com/blog/run-install-and-benchmark-qwen35-claude-code-free-local-ai-coding-agent/) **or Codex**: The LLM agent that reads the schema file, processes new sources, writes wiki articles, and runs linting passes. Karpathy published a GitHub Gist as an "idea file" designed to be pasted directly into Claude Code or a similar agent to bootstrap the system instantly.

The idea file is available at [gist.github.com/karpathy/442a6bf555914893e9891c11519de94f](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f?ref=ghost.codersera.com). It is designed to be copied, pasted, and adapted — not forked and compiled. This is itself a statement about the LLM agent era: instead of sharing a codebase, you share the _concept_, and the recipient's agent builds the implementation for their specific setup.

How to Build Your Own LLM Knowledge Base
----------------------------------------

Here is the minimum viable setup for replicating Karpathy's approach for your own personal knowledge management with AI.

**Step 1: Create the directory structure**

```
mkdir -p ~/knowledge/raw
mkdir -p ~/knowledge/wiki
mkdir -p ~/knowledge/outputs

```


**Step 2: Create your schema file**

Create `~/knowledge/CLAUDE.md` (or `AGENTS.md` for Codex). The schema file should define at minimum:

```
# Knowledge Base Schema

## Directories
- raw/: Source documents. Append-only. Never edit.
- wiki/: LLM-authored articles. One .md file per concept.
- outputs/: Query responses and reports.

## On ingesting a new source in raw/:
1. Read wiki/INDEX.md to understand existing articles.
2. Identify new concepts in the source not yet in the wiki.
3. Create or update articles in wiki/ for each concept.
4. Add backlinks to existing related articles.
5. Update wiki/INDEX.md with any new entries.

## Index format (wiki/INDEX.md):
- One line per article: [Article Title](filename.md) - one-sentence summary

## On answering a query:
1. Read wiki/INDEX.md.
2. Identify relevant articles and read them.
3. Write answer to outputs/YYYY-MM-DD-query-slug.md.

## On a linting pass:
1. Read all wiki articles.
2. Flag contradictions, missing backlinks, and referenced concepts lacking articles.
3. Create stubs for missing articles.

```


**Step 3: Ingest your first source**

Drop a research paper or article into `raw/`. Then open [your preferred AI coding agent](https://ghost.codersera.com/blog/top-10-best-ai-coding-tools-2026/) in `~/knowledge/` and run:

```
Process the new file in raw/ according to CLAUDE.md.

```


The LLM reads the schema, reads the new source, creates wiki articles, and updates the index. Your first knowledge base entry is done.

**Step 4: Run a linting pass periodically**

```
Run a linting pass on wiki/ according to CLAUDE.md.

```


Schedule this weekly or after every ten new sources. The LLM will fill gaps, fix stale links, and suggest new articles. For developers interested in how LLM-optimized metadata works at web scale, the [llms.txt specification](https://ghost.codersera.com/blog/how-to-create-llms-txt-a-comprehensive-guide/) applies a similar philosophy to public websites.

Limitations and Honest Trade-offs
---------------------------------

This system is not a replacement for every knowledge management scenario. Be clear-eyed about the constraints:

*   **Context window ceiling**: Once your wiki grows past a few hundred articles, the index file may exceed comfortable context window limits. At that point, you need either smarter indexing strategies or a lightweight retrieval layer on top of your Markdown files.
*   **Cost at scale**: Every compilation step and linting pass consumes tokens. At 400,000 words and growing, token costs for a full linting pass are non-trivial. Karpathy has not published cost figures; assume this is a premium workflow.
*   **LLM accuracy**: The wiki is only as accurate as the LLM's reading of the source material. Errors in article generation compound — a mistake in an early article gets backlinked into later ones. Human review of the linting output is not optional for research where factual accuracy matters.
*   **No real-time retrieval**: Unlike a search engine or properly indexed RAG system, answering a query means the LLM reads the full index and multiple articles at inference time. Fast for personal use, not suitable for shared systems with concurrent queries.
*   **Obsidian is optional**: Any Markdown editor works. VS Code with a Markdown preview extension is sufficient for most developers.

> The system works because Karpathy inverted the usual human-LLM dynamic: instead of asking the LLM questions, he trained the LLM to ask _itself_ what's missing. Karpathy's core insight isn't about folders or Obsidian — it's that LLMs are increasingly capable enough to act as knowledge compilers, not just query responders.

For teams evaluating whether to build this or invest in a proper RAG pipeline, the honest answer is: start with this approach, and only move to RAG when the context window becomes a genuine bottleneck rather than a hypothetical one. You'll likely be surprised how far structured Markdown takes you.

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260411-0001
- Source path: /home/peralese/Projects/Knowledge_Base/raw/inbox/LLM_Knowledge_Base.md
- Canonical URL: 


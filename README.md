# Local-First LLM Knowledge Base MVP

This repository is an MVP setup for a markdown-based knowledge base designed to be edited locally, viewed in Obsidian, and versioned with Git. The goal is to keep the structure simple and readable while preserving strong lineage between raw source material, compiled notes, and generated outputs.

The repository is intentionally local-first. Markdown files are the primary interface, Git provides change history, and automation can be added later with Python scripts without changing the core content model.

## What This Project Is

This project is a starter environment for collecting source material, writing source notes, compiling higher-level knowledge, and producing answer or report artifacts without losing where information came from.

The MVP is built around a few principles:

- Local-first: the knowledge base lives in ordinary files on disk.
- Strong data lineage: every compiled or generated artifact should point back to its inputs.
- Git-friendly: plain text files, stable paths, and readable diffs.
- Obsidian-friendly: markdown files, folders, and wikilinks work well in a vault.
- MVP first: start with a clear structure before adding automation.
- No overwriting of raw content: generated artifacts must never replace source truth.

## Top-Level Folder Purpose

### `raw/`

This is the source-truth layer. Use it for notes derived from articles, PDFs, manual research, copied references, or other ingested material.

- `raw/inbox/`: temporary landing area for uncategorized incoming notes.
- `raw/articles/`: markdown notes derived from articles, docs, blog posts, or webpages.
- `raw/notes/`: manual research notes, meeting notes, or analyst notes that are still considered raw inputs.
- `raw/pdfs/`: PDF files or PDF-related source notes.

Raw notes should preserve provenance and should not be overwritten by compiled or generated content.

### `compiled/`

This is the synthesis layer. Use it for notes that combine, summarize, reorganize, or normalize raw material into reusable internal knowledge.

- `compiled/source_summaries/`: concise summaries of individual raw sources.
- `compiled/concepts/`: concept-centric notes that explain a specific idea across sources.
- `compiled/topics/`: broader topic notes that combine multiple concepts or sources.

Compiled notes must always point back to the raw notes they were derived from.

### `outputs/`

This is the artifact layer. Use it for generated or manually drafted deliverables such as answers, reports, summaries for stakeholders, and other task-specific outputs.

- `outputs/reports/`: report-style deliverables.
- `outputs/answers/`: question-and-answer artifacts or response drafts.

Outputs should record the prompt or query used and list the compiled notes and raw notes that informed the result.

### `templates/`

This folder contains reusable markdown templates for raw notes, compiled notes, and generated outputs. The templates are intentionally minimal so that the workflow stays readable and easy to follow.

### `metadata/`

This folder holds lightweight structured metadata such as manifests, indexes, or lookup files. In the MVP, this is a simple place to keep source tracking data without adding a database.

### `scripts/`

This folder holds Python utilities for repository setup and later automation. The MVP includes a safe, idempotent setup script that can create the directory layout and optional starter files.

## MVP Workflow

The intended MVP workflow is:

1. Add or capture source material in `raw/`.
2. Create a raw note using `templates/raw-note-template.md`.
3. Compile higher-level notes in `compiled/` using one or more raw notes as inputs.
4. Produce answers or reports in `outputs/` using compiled notes and, when needed, the original raw notes.
5. Commit meaningful changes with Git so history remains readable and attributable.

This keeps the system understandable:

- `raw/` is where information enters the knowledge base.
- `compiled/` is where information is interpreted and organized.
- `outputs/` is where task-specific deliverables are produced.

## Lineage Rules

These rules are the core of the repository:

1. Raw notes are source truth.
2. Compiled notes must point back to raw notes.
3. Outputs must record the query or prompt and the sources used.
4. Generated content must not overwrite raw content.

In practice, that means:

- A raw note should include source metadata and provenance.
- A compiled note should list the raw notes it was compiled from.
- An output should include both the prompt and the notes used to produce it.
- If a generated answer changes, it should be saved as a new artifact or edited in `outputs/`, not written back into `raw/`.

## How Obsidian Fits In

Obsidian is the main reading and navigation layer for this MVP. This repository can be opened as an Obsidian vault so you can browse folders, open markdown files, and use wikilinks between notes.

For a user new to Obsidian, the practical fit is simple:

- Open the repository folder as a vault.
- Use folder structure to separate raw, compiled, and output material.
- Use wikilinks like `[[aws-patch-manager-basics]]` to connect notes.
- Use YAML frontmatter for metadata that remains readable in plain text.

Obsidian is helpful here because it makes the markdown corpus easy to navigate without forcing a database, proprietary format, or remote service.

## How Git Fits In

Git is the versioning layer for the knowledge base. Because everything is stored as ordinary files, Git can track:

- changes to source notes
- changes to compiled notes
- changes to generated outputs
- changes to metadata and scripts

Git is especially useful for this project because it preserves history and supports inspection of how a note evolved over time. It also reinforces the lineage model by making edits visible and reviewable.

This MVP keeps Git usage simple:

- initialize the repository
- make small, logical commits
- use meaningful commit messages
- avoid forceful rewrites of source-truth material

## Bootstrap

Example shell commands for getting started:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 scripts/setup_project.py --with-templates --with-starters
git init
git add .
git commit -m "Initialize local-first knowledge base MVP"
```

If you are on a shell that does not use `source`, activate the virtual environment using the equivalent command for your shell.

## Included MVP Files

The repository includes:

- starter templates under `templates/`
- sample raw notes under `raw/articles/`
- a sample compiled topic note under `compiled/topics/`
- a sample answer artifact under `outputs/answers/`
- a minimal source manifest under `metadata/`
- a safe setup script under `scripts/setup_project.py`

## Notes on Scope

This MVP intentionally does not include:

- vector databases
- web frameworks
- cloud services
- RAG orchestration frameworks
- heavy ingestion pipelines
- automatic note rewriting

Those can be added later if they are justified, but the starting point should remain a clean, inspectable markdown repository with explicit lineage.

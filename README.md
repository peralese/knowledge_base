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

## Phase 2 Ingestion Workflow

Phase 2 adds the first ingestion script: `scripts/ingest.py`. Its job is to take a source input, normalize it into a standardized raw markdown note, place that note in the correct `raw/` subfolder, and update `metadata/source-manifest.json`.

This phase is intentionally narrow. It is only about ingestion and provenance capture. It does not compile notes, answer queries, generate reports, summarize with an LLM, scrape websites, or parse PDFs beyond creating a placeholder note.

### What the ingestion script does

The ingestion script:

- accepts source input from a file or direct CLI text
- normalizes the content into a raw markdown note
- adds the standard raw-note YAML frontmatter
- chooses the destination folder based on `source_type`
- generates a safe slug-based filename from the title
- creates or updates a manifest entry in `metadata/source-manifest.json`
- refuses to overwrite an existing note unless `--force` is explicitly passed

### Supported input modes

The script supports these modes in Phase 2:

1. Plain text file input
2. Existing markdown file input
3. Direct text passed on the command line
4. Copied web article content plus URL metadata
5. PDF placeholder ingestion without PDF parsing

### Destination behavior

The destination folder is selected from `source_type`:

- `article` -> `raw/articles/`
- `note` -> `raw/notes/`
- `pdf` -> `raw/pdfs/`
- anything else -> `raw/inbox/`

### Example commands

Ingest a plain text file:

```bash
python3 scripts/ingest.py \
  --input-file ./inbox/example.txt \
  --title "Example Note" \
  --source-type note \
  --origin local-file
```

Ingest an existing markdown file:

```bash
python3 scripts/ingest.py \
  --input-file ./inbox/example.md \
  --title "Existing Markdown Note" \
  --source-type article \
  --origin local-markdown
```

Ingest direct text from the CLI:

```bash
python3 scripts/ingest.py \
  --text "AWS Patch Manager automates patching..." \
  --title "Patch Manager Snippet" \
  --source-type note \
  --origin manual-entry
```

Ingest copied web article content with URL metadata:

```bash
python3 scripts/ingest.py \
  --input-file ./inbox/article.txt \
  --title "Interesting Article" \
  --source-type article \
  --origin web \
  --canonical-url "https://example.com/article"
```

Create a PDF placeholder note:

```bash
python3 scripts/ingest.py \
  --input-file ./inbox/reference.pdf \
  --title "Reference PDF" \
  --source-type pdf \
  --origin local-file
```

Overwrite an existing ingested note only when explicit replacement is intended:

```bash
python3 scripts/ingest.py \
  --input-file ./inbox/example.txt \
  --title "Example Note" \
  --source-type note \
  --origin local-file \
  --force
```

### What gets created

For each ingestion run, the script creates or updates:

- one raw markdown note in the correct `raw/` subfolder
- one manifest entry in `metadata/source-manifest.json`

Each raw note includes:

- standard YAML frontmatter
- normalized source content
- a simple lineage section
- a generated `source_id`

Each manifest entry includes at least:

- `source_id`
- `title`
- `filename`
- `path`
- `source_type`
- `origin`
- `date_ingested`
- `canonical_url`
- `input_path`
- `status`

### Note format created by ingestion

The ingested raw note body uses this structure:

```md
# Overview

Brief description of what this source is and why it matters.

# Source Content

[normalized ingested content]

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry:
- Source path:
- Canonical URL:
```

### Manifest and source IDs

The ingestion script updates `metadata/source-manifest.json` in place and avoids duplicate entries for the same output path. For newly ingested notes, it generates source IDs in a simple sequential format such as:

```text
SRC-20260403-0001
```

If a note already has a manifest entry for the same output path, the script reuses that `source_id` instead of creating a duplicate.

### What is out of scope in Phase 2

This phase does not include:

- note compilation
- querying
- report or answer generation
- browser automation
- website scraping frameworks
- PDF parsing or OCR
- LLM summarization
- automatic tagging
- concept extraction
- raw-note mutation beyond explicit `--force` replacement during ingestion

The purpose of Phase 2 is to make ingestion reliable, inspectable, and safe to re-run without introducing hidden automation.

## Phase 3 Compilation Workflow

Phase 3 adds the first compilation script: `scripts/compile_notes.py`. In this project, compilation means taking one or more selected raw notes and turning them into a reusable synthesized markdown note in `compiled/` without changing the raw sources.

This keeps the workflow layered:

- ingestion creates normalized raw notes in `raw/`
- compilation turns selected raw notes into reusable synthesized notes in `compiled/`
- later phases can use compiled notes to support outputs, answers, or optional LLM-assisted workflows

Compilation is intentionally inspectable and safe in this phase. Raw notes remain source truth, compiled notes must point back to raw notes, and the script does not require a live LLM API.

### What the compilation script does

The script:

- reads one or more selected raw markdown notes
- parses YAML frontmatter when present
- extracts source metadata and body content
- generates a compiled markdown scaffold and/or a prompt-pack
- preserves lineage with `compiled_from` metadata and Obsidian wikilinks
- refuses to overwrite existing outputs unless `--force` is explicitly passed

### Supported compilation categories

The compiled destination folder depends on the selected category:

- `source_summary` -> `compiled/source_summaries/`
- `concept` -> `compiled/concepts/`
- `topic` -> `compiled/topics/`

If no category flag is passed, the script defaults to `topic`.

### Supported modes

Phase 3 supports two primary modes and one combined mode:

1. `scaffold`

This is the default mode. It creates a compiled note shell with:

- YAML frontmatter
- placeholder summary and insight sections
- source wikilinks
- short source metadata callouts
- short source excerpts
- explicit lineage back to the raw notes

2. `prompt-pack`

This mode creates a markdown prompt file under `metadata/prompts/` that can later be pasted into Codex, OpenAI, Ollama, or another local workflow. The prompt-pack includes:

- the requested compiled note title
- the note category
- the desired output template
- the selected source note metadata
- the selected source note bodies
- instructions to preserve lineage
- instructions not to invent unsupported claims

3. `both`

This mode creates both the compiled scaffold note and the prompt-pack in one run.

### Example commands

Create a compiled topic scaffold from two raw article notes:

```bash
python3 scripts/compile_notes.py \
  --sources raw/articles/aws-patch-manager-basics.md raw/articles/aws-inspector-overview.md \
  --title "AWS Patching and Vulnerability Management Overview" \
  --topic
```

Create only a prompt-pack:

```bash
python3 scripts/compile_notes.py \
  --sources raw/articles/aws-patch-manager-basics.md raw/articles/aws-inspector-overview.md \
  --title "AWS Patching and Vulnerability Management Overview" \
  --topic \
  --mode prompt-pack
```

Create both outputs:

```bash
python3 scripts/compile_notes.py \
  --sources raw/articles/aws-patch-manager-basics.md raw/articles/aws-inspector-overview.md \
  --title "AWS Patching and Vulnerability Management Overview" \
  --topic \
  --mode both
```

Overwrite an existing compiled note or prompt-pack only when explicit replacement is intended:

```bash
python3 scripts/compile_notes.py \
  --sources raw/articles/aws-patch-manager-basics.md \
  --title "AWS Patch Manager Summary" \
  --source-summary \
  --force
```

### What gets created

Depending on the selected mode, the script creates:

- one compiled markdown note under the appropriate `compiled/` subfolder
- one prompt-pack markdown file under `metadata/prompts/`

Compiled note filenames are generated from the title using a lowercase hyphenated slug. For example:

```text
AWS Patching and Vulnerability Management Overview
-> aws-patching-and-vulnerability-management-overview.md
```

Each compiled scaffold note includes frontmatter with:

- `title`
- `note_type`
- `compiled_from`
- `date_compiled`
- `topics`
- `tags`
- `confidence`
- `generation_method`

In scaffold mode, `generation_method` is `manual_scaffold`. In prompt-pack mode, the generated prompt instructs the later synthesis step to use `prompt_pack`.

### What remains out of scope in Phase 3

This phase does not include:

- live API-dependent LLM synthesis as a required step
- querying or retrieval workflows
- automated answer generation in `outputs/`
- linting or repo-wide note rewriting
- embeddings or vector search
- graph databases
- web frameworks or cloud services
- hidden automation that mutates raw notes in place

The purpose of Phase 3 is to create a practical bridge between raw notes and later synthesis workflows while keeping compilation deterministic, readable, and easy to inspect.

## Phase 4 Controlled Synthesis Workflow

Phase 4 adds the first controlled synthesis script: `scripts/apply_synthesis.py`. In this project, controlled synthesis means taking a prompt-pack created in Phase 3, supplying synthesized markdown yourself, and saving the result as a durable repository artifact without requiring direct model execution inside the repo.

This keeps synthesis explicit and user-invoked:

- Phase 3 creates scaffold notes and/or prompt-packs
- Phase 4 applies synthesized model output into durable repository artifacts
- the user decides when synthesis happens and what content gets written

This phase is intentionally safe. It does not require a live LLM API, does not autonomously call remote services, and does not rewrite raw notes.

### What the synthesis application script does

The script:

- reads a Phase 3 prompt-pack from `metadata/prompts/`
- extracts simple metadata such as the requested title, note category, and source note names
- accepts synthesized markdown from a file or direct CLI text
- sanitizes synthesized markdown before writing it to disk
- writes the result to `compiled/` or `outputs/`
- injects or repairs required frontmatter fields when they are missing
- preserves the synthesized markdown body as much as possible
- refuses to overwrite an existing artifact unless `--force` is explicitly passed

### Sanitization behavior

Before Phase 4 writes synthesized output, it applies a conservative sanitization pass intended to keep the repository and Obsidian graph clean.

The sanitization layer:

- removes malformed citation placeholders such as `[oaicite:...]` and `:contentReference[...]`
- filters suspicious shell fragments such as `$(...)` when they appear as stray prose
- filters suspicious path-like fragments such as `github/repo/blob/main/...`
- drops symbol-heavy junk lines that look like regex or script debris rather than knowledge content
- preserves valid intended wikilinks such as `[[real-source-note]]`

The goal is not to rewrite valid technical content. It is to prevent malformed synthesized output from creating accidental graph noise, junk note names, or meaningless path-like nodes in durable artifacts.

### Supported input modes

Phase 4 supports these user-controlled input modes:

1. Synthesized markdown from an input file

```bash
python3 scripts/apply_synthesis.py \
  --prompt-pack metadata/prompts/compile-aws-patching-and-vulnerability-management-overview.md \
  --synthesized-file ./tmp/synthesized-note.md
```

2. Synthesized markdown passed directly on the command line

```bash
python3 scripts/apply_synthesis.py \
  --prompt-pack metadata/prompts/compile-aws-patching-and-vulnerability-management-overview.md \
  --text "# Summary\n\nAWS patching and vulnerability management work together..."
```

3. Reserved placeholder adapter flag

The script includes an optional `--adapter` flag as a future-friendly placeholder, but Phase 4 does not implement direct model execution yet. If the flag is used, the script fails clearly instead of attempting hidden automation.

### Output routing

The default output type is `compiled`.

If `--output-type compiled` is used:

- the script saves to the appropriate `compiled/` subfolder when the prompt-pack category is clear
- if the category is unclear, it defaults to `compiled/topics/`

If `--output-type answer` is used:

- the script saves to `outputs/answers/`

If `--output-type report` is used:

- the script saves to `outputs/reports/`

### Example commands

Apply synthesized markdown from a file into a compiled note:

```bash
python3 scripts/apply_synthesis.py \
  --prompt-pack metadata/prompts/compile-aws-patching-strategy.md \
  --synthesized-file ./tmp/synthesized-note.md
```

Apply synthesized markdown from direct CLI text into an answer artifact:

```bash
python3 scripts/apply_synthesis.py \
  --prompt-pack metadata/prompts/compile-aws-patching-strategy.md \
  --output-type answer \
  --text "# Prompt\n\nWhat is the relationship between Patch Manager and Inspector?\n\n# Answer\n\nPatch Manager executes remediation while Inspector helps identify and prioritize it."
```

Override the title when saving:

```bash
python3 scripts/apply_synthesis.py \
  --prompt-pack metadata/prompts/compile-aws-patching-strategy.md \
  --title "AWS Patching Strategy Executive Summary" \
  --output-type report \
  --synthesized-file ./tmp/report.md
```

Overwrite an existing artifact only when explicit replacement is intended:

```bash
python3 scripts/apply_synthesis.py \
  --prompt-pack metadata/prompts/compile-aws-patching-strategy.md \
  --synthesized-file ./tmp/synthesized-note.md \
  --force
```

### What gets created

Depending on `--output-type`, the script creates one of the following:

- a compiled note under `compiled/source_summaries/`, `compiled/concepts/`, or `compiled/topics/`
- an answer artifact under `outputs/answers/`
- a report artifact under `outputs/reports/`

The output filename is derived from the resolved title using a lowercase hyphenated slug.

For compiled outputs, the script ensures frontmatter includes at least:

- `title`
- `note_type`
- `compiled_from`
- `date_compiled`
- `topics`
- `tags`
- `confidence`
- `generation_method`

For answer or report outputs, the script ensures frontmatter includes at least:

- `title`
- `output_type`
- `generated_from_query`
- `generated_on`
- `sources_used`
- `compiled_notes_used`
- `generation_method`

In this phase, `generation_method` defaults to `manual_paste` for file-based or CLI-text synthesis input.

### What remains out of scope in Phase 4

This phase does not include:

- direct live model invocation as the default workflow
- repo-wide autonomous synthesis
- querying workflows
- linting or automated repo-wide rewrites
- embeddings or vector search
- graph databases
- web frameworks or cloud services
- autonomous multi-step orchestration

The purpose of Phase 4 is to create a practical bridge between prompt-packs and durable markdown artifacts while keeping synthesis explicit, user-controlled, and easy to inspect.

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

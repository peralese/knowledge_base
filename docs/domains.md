# Domain-Aware Knowledge Bases

This project now supports multiple local knowledge-base domains in one shared app and repository.

## Architecture

The implementation uses a hybrid model: one shared application and codebase, with domain-aware namespaces for major artifacts. Domain is not only metadata; it routes storage, queues, compiled outputs, indexes, answers, and default query scope.

Domain records live in `metadata/domains.json`:

```json
{
  "display_name": "AI",
  "slug": "ai",
  "description": "Default domain for the original single-domain knowledge base.",
  "created_at": "2026-05-15T00:00:00+00:00",
  "active": true
}
```

## Layout

New domain-scoped artifacts use:

```text
raw/domains/<domain>/inbox/<adapter>/
raw/domains/<domain>/articles/
metadata/domains/<domain>/review-queue.json
metadata/domains/<domain>/topic-registry.json
metadata/domains/<domain>/prompts/
compiled/domains/<domain>/topics/
compiled/domains/<domain>/concepts/
compiled/domains/<domain>/entities/
compiled/domains/<domain>/source_summaries/
compiled/domains/<domain>/index.md
outputs/domains/<domain>/answers/
indexes/domains/<domain>/vector_index.db
```

The legacy paths still work for direct script calls that do not pass a domain.

## Dashboard Usage

The ingest screen has a required Domain selector. You can choose an existing domain or add one inline. The dashboard remembers the last selected domain in local storage and sends it through ingest, query, queue, and recent answer APIs.

Queries default to the selected domain. Cross-domain querying requires the explicit “Search all domains” checkbox.

## CLI Usage

Examples:

```bash
python3 scripts/stage_to_inbox.py clipboard --domain civil-war-history --title "Antietam" --text "..."
python3 scripts/inbox_watcher.py --domain civil-war-history --once
python3 scripts/ingest.py --domain civil-war-history --title "Antietam" --source-type article --origin manual-entry --text "..."
python3 scripts/compile_notes.py --domain civil-war-history --sources raw/domains/civil-war-history/articles/antietam.md --title "Antietam" --topic
python3 scripts/index_notes.py --domain civil-war-history
python3 scripts/query.py --domain civil-war-history "What sources discuss Antietam?"
python3 scripts/query.py --all-domains "Compare agent security and Civil War logistics"
python3 scripts/vector_index.py --domain civil-war-history build
```

## Migration

The current corpus can be copied into the default `ai` domain without deleting or overwriting legacy files:

```bash
python3 scripts/migrate_to_domains.py --domain ai
python3 scripts/migrate_to_domains.py --domain ai --apply
```

The migration helper copies existing single-domain artifacts into `*/domains/ai/*`. It intentionally leaves the original layout in place for backward compatibility and inspection.

## Tradeoffs

This keeps one local-first app and shared codebase, but avoids one mixed reasoning space. The main tradeoff is temporary dual-layout support: legacy paths are still readable while domain paths become the production-minded default for dashboard and domain-aware CLI flows.

## Follow-Ups

- Extend every maintenance command with a `--domain` flag where it is still implicit.
- Add a dashboard domain management tab for descriptions, active/inactive state, and migration status.
- Add cross-domain comparison views that show provenance from each domain instead of merging context silently.

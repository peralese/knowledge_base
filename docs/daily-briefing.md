# Perales Lab Daily Briefing

Phase 2A implements story discovery and editorial selection. Phase 2B turns a selected edition into a validated, contextual written narrative. Both layers keep RSS candidates completely separate from durable knowledge-base ingestion.

## Architecture

```text
metadata/feeds.json
        ↓
hourly feed_poller.py --once
        ↓
RSS/Atom parse + provenance normalization
        ↓
deterministic identity + duplicate-story checks
        ↓
metadata/briefing/candidates.db
        ↓
briefing.py evaluate (local Ollama)
        ↓
score + inspectable why-it-matters reasoning
        ↓
briefing.py build (novelty + diversity selection)
        ↓
outputs/briefing/editions/YYYY-MM-DD.md
        ↓
deterministic topic-group proposal + briefing.py narrative (local Ollama)
        ↓
schema/provenance validation + append-only attempt record
        ↓
outputs/briefing/narratives/YYYY-MM-DD-narrative.md
        ↓
explicit human retention decision
        ├── discard: audit only
        ├── reference: outputs/briefing/references/YYYY-MM-DD/BFC-….md
        └── promote: raw/domains/<domain>/inbox/feeds/briefing-BFC-….json
                         ↓ existing inbox watcher / review queue / approval controls
```

The poller does not write briefing candidates to `raw/domains/<domain>/inbox/`. Ordinary candidates cannot trigger KB synthesis, confidence scoring, approval, topic/concept/entity aggregation, or permanent indexing. The only exception is a later explicit human Phase 2C `promote` action.

## Feed configuration

`metadata/feeds.json` is human-readable configuration. The tracked production file remains empty. Do not commit credentials; use only public URLs or a future secret-loading mechanism.

```json
{
  "feeds": [
    {
      "id": "example-ai-feed",
      "name": "Example AI Feed",
      "url": "https://example.com/feed.xml",
      "enabled": true,
      "domain": "ai",
      "priority": 5,
      "tags": ["ai", "agents"]
    }
  ]
}
```

`id`, `name`, and an HTTP(S) `url` are required. IDs must be stable lowercase identifiers and unique. Invalid entries are reported and skipped independently; disabled feeds are ignored. An absent or empty configuration exits successfully without creating the candidate database.

## Candidate storage and states

The SQLite database is `metadata/briefing/candidates.db` and is ignored by Git as Mac mini runtime state. SQLite WAL mode, a 30-second busy timeout, transactions, and advisory stage locks make polling, evaluation, and edition writes safe on the single authoritative host.

Candidate fields include:

- identity: `candidate_id`, feed ID/name/URL, GUID/Atom ID, identity kind/value
- provenance: article URL, normalized URL, author, categories, feed tags/domain/priority
- source data: title, normalized title, feed summary/content, published/updated/discovered timestamps
- dedupe: `duplicate_of` and inspectable `dedupe_reason`
- editorial data: score, reasoning, validated evaluation JSON, model, prompt version, evaluation/error timestamps
- selection data: state, selection reason, and edition association

States are:

- `new`: safely stored and awaiting evaluation
- `evaluated`: validated editorial score and reasoning are available
- `selected`: included in an edition
- `not_selected`: suppressed by recent-history or same-edition repetition rules
- `duplicate`: same URL or nearly identical story points to the original candidate
- `error`: evaluation failed and can be retried

Discard, Reference, and Promote are intentionally absent.

## Identity and deduplication

Identity uses the first available value in this order:

1. RSS GUID or Atom ID
2. normalized canonical article URL
3. SHA-256 of normalized title, publication date, and available content

The candidate ID is a deterministic hash of feed ID plus identity. A repeated item from the same feed is not inserted twice. Cross-feed canonical URL matches and titles with at least 92% similarity are retained as `duplicate` rows with a reason and pointer to the first candidate. Selection also suppresses similar stories within an edition and items similar to recently selected history.

## Editorial evaluation

The profile is `metadata/briefing/editorial-profile.json`. It configures interests, noise categories, model, prompt version, target edition size, history window, and retention window. Source content is explicitly delimited as untrusted data and cannot override editorial instructions.

Ollama returns validated JSON with six 0–100 dimensions:

- relevance: 30%
- technical significance: 20%
- novelty: 15%
- likely usefulness: 20%
- connection to configured interests: 15%
- marketing/noise penalty: up to 20 points

The final editorial score is clamped to 0–100. It measures attention value, not KB synthesis confidence. `why_it_matters`, the raw dimensions, model, and prompt version are persisted. Malformed output or Ollama failure moves the candidate to retryable `error`; source data is preserved.

## Edition selection

An edition has a deterministic ID (`BFE-YYYY-MM-DD`) and `ready` state. Generation is idempotent: a second build for the same date returns the existing edition unless a future regeneration feature is explicitly added.

Candidates rank by editorial score, feed priority, and publication time. Selection excludes duplicate states and recent repetitions, suppresses near-identical stories in the same edition, and ordinarily caps one feed at two stories when alternatives exist. The default target is five items and is configurable in the profile or with `--target`.

The Phase 2A Markdown output remains an independent editorial review artifact. It retains the feed, article link, publication date, score, why-it-matters reasoning, and source summary.

## Contextual narrative generation

`briefing.py narrative` reads only the already-selected edition. Before synthesis it proposes groups using strong overlap in meaningful title/category terms; unmatched stories stay standalone. These groups guide, but do not force, the model's structure. The prompt asks for one connected, concise technical briefing, distinguishes source facts from labeled analysis, treats feed content as untrusted data, and prohibits invented sources.

The local Ollama response must be a JSON object containing the edition date, headline, opening, one or more sections, section narratives, supporting candidate IDs, key takeaways, and what-to-watch items. Validation rejects missing fields, malformed types, date mismatches, empty support lists, unknown IDs, or omission of any selected item. Titles, URLs, source names, timestamps, categories, and editorial scores are never accepted from the model: they are joined back from SQLite after validation.

Every successful stored narrative includes the immutable source snapshot and the topic groups/relationship explanations used for construction. The Markdown artifact cites its supporting articles per section and includes a compact source appendix.

Generation attempts are append-only in `narrative_generations`. By default, an existing valid narrative is returned without another model call. `--regenerate` performs a new attempt and makes it current only after successful schema and provenance validation. Attempt time, completion time, model, schema/prompt versions, original-versus-regeneration status, artifact path, and failures are recorded. A failed initial attempt leaves the Phase 2A edition usable; a failed regeneration also leaves the prior valid narrative current.

Empty editions fail cleanly without calling Ollama. A single-item/undersized edition is supported and produces a concise narrative when the model response validates.

## CLI

```bash
# Hourly-safe ingestion stage; production LaunchAgent already runs this form
.venv/bin/python scripts/feed_poller.py --once

# Evaluate new and retryable-error candidates
.venv/bin/python scripts/briefing.py evaluate

# Inspect candidates; optional --state, --domain, --feed, and --limit filters
.venv/bin/python scripts/briefing.py candidates

# Build or return today's idempotent edition
.venv/bin/python scripts/briefing.py build

# Build another date or override the target
.venv/bin/python scripts/briefing.py build --date 2026-08-09 --target 3

# Show an edition as structured Markdown
.venv/bin/python scripts/briefing.py show --date 2026-08-09

# Generate or reuse the validated Phase 2B narrative
.venv/bin/python scripts/briefing.py narrative --date 2026-08-09

# Intentionally create and replace it with a newly validated generation
.venv/bin/python scripts/briefing.py narrative --date 2026-08-09 --regenerate

# Safely remove old unselected/duplicate/error candidates not used by editions
.venv/bin/python scripts/briefing.py prune
```

Each poll reports fetched, new, duplicate, and error counts. Evaluation reports successes/errors; build reports selected count and artifact path.

## Scheduling, retry, and retention

The existing macOS LaunchAgent remains an hourly one-shot poller using `feed_poller.py --once`. Evaluation and edition generation are manual in Phase 2A, preventing hourly duplicate editions and allowing editorial quality to be validated before daily scheduling.

Evaluation errors are retryable on the next `evaluate` command. Edition creation is atomic and idempotent. The manual `prune` command defaults to 30 days and removes only old `not_selected`, `duplicate`, or `error` candidates that are not associated with an edition. Selected history is preserved. There is no automatic destructive pruning.

## Testing

```bash
make test-briefing
make test
```

Tests use local XML fixtures, temporary SQLite databases, temporary output roots, and mocked Ollama calls. Phase 2B coverage includes grouping boundaries, provenance, schema/ID rejection, failure isolation, idempotency, regeneration, empty/undersized editions, and deterministic artifact naming. They do not fetch arbitrary feeds, write to the live KB, or require runtime services.

Phase 2B itself remains text-only. Audio/TTS, publishing, dashboards, delivery/notifications, KB entity/topic generation, new feeds, scraping, and cloud LLMs remain explicitly out of scope across the briefing phases.

## Retention review and controlled promotion

Phase 2C adds a human-only decision gate for selected edition items. Scores and models never choose retention. SQLite remains authoritative through three tables:

- `retention_decisions`: current decision and downstream state for an edition item
- `retention_history`: append-only human decision changes, including reviewer, note, timestamp, and previous decision
- `retention_attempts`: append-only completed/failed downstream action attempts

An item with no row is `pending`. `discard` records the decision while preserving the candidate, evaluation, edition, narrative linkage, and provenance. It never deletes briefing history or creates another artifact. `reference` atomically creates a deterministic metadata-only artifact under `outputs/briefing/references/<date>/<candidate-id>.md`; it includes source and briefing provenance plus existing editorial context, but no copied full article or newly generated knowledge. It is explicitly not approved KB knowledge.

`promote` atomically writes the existing feed-inbox JSON format at `raw/domains/<domain>/inbox/feeds/briefing-<candidate-id>.json`. That is the only Phase 2C boundary crossing. The normal inbox watcher subsequently creates the raw source note and pending review-queue entry. Promotion does not run the watcher, synthesis, approval, topic aggregation, or concept/entity generation, and the payload contains no approval state. Its embedded `briefing_provenance` preserves the candidate, edition, feed identity, source identity, reviewer decision, note, and narrative-section linkage.

Promotion checks all source manifests for the same normalized canonical URL. An existing source records `already_present` and its source ID/path without creating an inbox artifact. A pre-existing deterministic inbox artifact is also reconciled as already present. After the watcher ingests a queued artifact, repeating the same idempotent `promote` command reconciles the resulting manifest `source_id` back into retention state. Malformed manifests fail conservatively rather than risk duplicate ingestion.

Identical completed decisions are idempotent. Failed actions retain the human decision and error and may be retried safely. Deliberate changes such as discard → reference, discard → promote, and reference → promote append history rather than overwriting it. References and KB intake artifacts already created are not silently removed when a later decision changes; previously promoted material must be managed through the permanent KB's own review and purge controls.

The structured edition Markdown displays the current SQLite-derived retention marker, but editing Markdown never changes retention state.

### Retention CLI

```bash
# Review today's selected items, or filter the report
.venv/bin/python scripts/briefing.py retention list
.venv/bin/python scripts/briefing.py retention list --date 2026-08-09 --status pending
.venv/bin/python scripts/briefing.py retention list --date 2026-08-09 --status failed

# Inspect current state and full decision history
.venv/bin/python scripts/briefing.py retention show BFC-… --date 2026-08-09

# Make an explicit human decision
.venv/bin/python scripts/briefing.py retention discard BFC-… --date 2026-08-09 --reviewer erick --note "Briefing-only value"
.venv/bin/python scripts/briefing.py retention reference BFC-… --date 2026-08-09 --reviewer erick --note "Useful source pointer"
.venv/bin/python scripts/briefing.py retention promote BFC-… --date 2026-08-09 --reviewer erick --note "Send through normal KB review"

# Retry only the item's current failed downstream action
.venv/bin/python scripts/briefing.py retention retry BFC-… --date 2026-08-09
```

Phase 2C does not add automatic decisions, AI-selected promotion, bulk score-based retention, final KB approval, deletion/retraction, audio, publishing, UI, notifications, scraping, feeds, or external models.

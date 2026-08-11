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

## Two-stage contextual narrative generation

`briefing.py narrative` reads only the already-selected edition. Before synthesis it proposes groups using strong overlap in meaningful title/category terms; unmatched stories stay standalone. These groups guide, but do not force, structure and carry explicit thematic, integration, and causality semantics.

### Phase 2B1: Narrative Synthesis

The synthesis model creates a structured draft with the opening, ordered sections, supporting candidate IDs, takeaways, and what-to-watch entries. It is responsible for architectural coherence and flow, but its draft is neither canonical nor audio-eligible. Schema and selected-item linkage are checked and authoritative provenance is restored from SQLite before cleanup.

### Phase 2B2: Evidence-Bounded Editorial Cleanup

Validation identifies the exact prose unit and sentence for localized unsupported absolutes, integration implications, vague or unattributed performance claims, and over-certain projections. Cleanup receives only that sentence, its violation classes, group relationship context, supporting selected IDs, stored source material, and vendor identity. It may weaken, qualify, attribute, replace with supported wording, or remove the claim. It cannot add sources, strengthen the claim, alter grouping/selection/order, or rewrite unrelated prose.

Each flagged prose unit gets at most two cleanup attempts. The exact original, response action, replacement, source IDs, and validation result are appended to `narrative_cleanup_attempts`. Criticality is deterministic: the opening, titles, and substantive section narratives are `core`; what-to-watch entries and optional takeaways are `nonessential`. The model does not choose this classification.

After both model attempts fail, an eligible unresolved nonessential unit is removed without another model call. The fallback adds no filler and is recorded separately in `narrative_cleanup_fallbacks` with the original text, violation types, exhausted-attempt count, reason, timestamp, and validation state. An unresolved core unit always fails the generation and is never deleted. Empty what-to-watch lists and omitted takeaways are valid; openings and section bodies must remain substantive, every selected item must retain a source-linked section, provenance must remain unchanged, and the complete result must pass final validation.

Before core failure or nonessential removal, an attribution-only performance comparison gets one deterministic normalization opportunity. It makes no model call and only prepends `According to <canonical publisher>,` to the existing sentence. Eligibility requires exactly one selected supporting item, a publisher derived from its stored feed identity, every percentage/multiplier present in stored title/summary/content, a supported comparison baseline, and no second violation. Wrong publishers, invented metrics, vague performance praise, unsupported relationships, and absolutes are ineligible. Successful or failed final validation is appended to `narrative_attribution_normalizations`; prior model attempts remain unchanged.

When the cleanup sentence altered or omitted evidence-bearing components, attribution-only normalization is skipped. A narrow comparative reconstruction extractor may identify exactly one explicit stored-source clause containing a product, numeric metric, supported dimension (`performance`, `price-performance`, latency/throughput/efficiency/cost where explicit), and exact `compared to/with` baseline. It then renders only `According to <publisher>, <product> provide <metric> <comparison phrase> compared with <baseline>.` These factual fields are immutable and come exclusively from the selected SQLite source. Ambiguous/conflicting clauses, unsupported original metrics, multiple sources, vague claims, and unrelated violations fail conservatively. The original synthesis sentence, latest cleanup sentence, structured components, reconstructed text, source IDs, action, and validation result are appended to `narrative_comparative_reconstructions`.

The localized wording validator treats grammatical forms of `eliminat* … the need` as the same risky absolute construction while allowing cautious `may/can reduce the need` language. A small scoped pattern also rejects exceptional, superior, outstanding, remarkable, unmatched, or unparalleled when those adjectives characterize measurable performance, ratings, benchmarks, latency, throughput, efficiency, price-performance, or bandwidth. These rules do not ban the words globally. Phase 2B2 receives the same stored evidence and is instructed to replace promotional measurement language with an exact sourced value or neutral capability statement when possible.

The local Ollama response must be a JSON object containing the edition date, headline, opening, one or more sections, section narratives, supporting candidate IDs, key takeaways, and what-to-watch items. Validation rejects missing fields, malformed types, date mismatches, empty support lists, unknown IDs, or omission of any selected item. Titles, URLs, source names, timestamps, categories, and editorial scores are never accepted from the model: they are joined back from SQLite after validation.

Every successful stored narrative includes the immutable source snapshot and the topic groups/relationship explanations used for construction. The Markdown artifact cites its supporting articles per section and includes a compact source appendix.

Generation attempts are append-only in `narrative_generations`. Generations created before the split remain legacy single-stage records and are not migrated. New attempts reserve one generation ID, store the 2B1 draft and detected violations in `narrative_pipeline_runs`, and append each 2B2 action separately. States distinguish synthesis in progress, draft created, cleanup required/in progress, final validation, ready, and failed. By default, an existing ready current narrative is reused; `--regenerate` creates a new two-stage attempt. Only final validation marks it current and atomically renders the canonical Markdown. Failure preserves the draft, edition, previous current narrative, retention/KB state, and audio artifacts.

Phase 2D reads only `current_narrative`, whose query requires both `status='ready'` and `is_current=1`; it therefore cannot consume an uncleaned draft.

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

## Local audio generation

Phase 2D treats audio as a derived presentation layer:

```text
current validated narrative generation
        ↓ deterministic speech preparation
outputs/briefing/audio/YYYY-MM-DD-script.txt
        ↓ local macOS Speech Synthesis Manager
temporary validated PCM WAV
        ↓ atomic replacement
outputs/briefing/audio/YYYY-MM-DD-briefing.wav
        + YYYY-MM-DD-audio.json
```

### Local engine choice

The authoritative Mac mini has Python 3.9.6, `/usr/bin/say`, `/usr/bin/afconvert`, and `/usr/bin/afinfo`; it does not have FFmpeg or a Python TTS package. A synthetic environment smoke test confirmed that `say` produces valid local audio. Although the installed conversion tooling advertises MP3 and AAC containers, actual MP3/AAC encoding fails on this host. Direct `say` output as 22.05 kHz, mono, 16-bit PCM WAV succeeds and is broadly playable, so Phase 2D uses WAV without adding a large framework or cloud dependency.

The small `macos_say_tts` adapter isolates subprocess execution from preparation, persistence, idempotency, and CLI logic. Tests substitute this adapter and never use speakers or real TTS hardware.

### Speech preparation

The TTS engine never receives raw Markdown. Speech preparation reads only the validated structured narrative and:

- preserves the headline, opening, section order, narrative text, takeaways, and what-to-watch order
- turns section titles into natural transitions
- removes Markdown markers, inline citation links, HTML, bullets, and raw URLs
- omits source provenance/source appendices from spoken output
- conservatively expands AI, AWS, API, CLI, GPU, LLM, and IaC for reliable pronunciation
- rejects missing, empty, mismatched, or sectionless narratives rather than generating silence or filler

The exact prepared text remains inspectable at `outputs/briefing/audio/YYYY-MM-DD-script.txt`. The Phase 2B Markdown and SQLite narrative remain unchanged.

### Configuration and CLI

Defaults are explicit in `metadata/briefing/editorial-profile.json`:

```json
"audio": {
  "voice": "Samantha",
  "rate": 185,
  "format": "wav"
}
```

The voice and rate may be overridden per generation. Rate must be 80–450 words per minute. WAV is the only verified format in this phase.

```bash
# Today's inspectable script, without TTS
.venv/bin/python scripts/briefing.py audio script

# Generate/reuse today's audio
.venv/bin/python scripts/briefing.py audio generate

# Another date or configuration
.venv/bin/python scripts/briefing.py audio generate --date 2026-08-09 --voice Samantha --rate 185 --format wav

# Force a new auditable attempt at the deterministic path
.venv/bin/python scripts/briefing.py audio generate --date 2026-08-09 --regenerate

# Inspect current state and whether the narrative has changed
.venv/bin/python scripts/briefing.py audio status --date 2026-08-09

# Listen locally on macOS
afplay outputs/briefing/audio/2026-08-09-briefing.wav
```

### Metadata, idempotency, and failures

`audio_generations` is an append-only SQLite attempt table. Every attempt records the edition, narrative generation ID and SHA-256 fingerprint, configuration fingerprint, engine/version, voice, rate, format, timestamps, generation kind, script/narrative/audio/metadata paths, byte size, duration, result, and error. Only a successful generation becomes current.

Default generation reuses a readable artifact only when both the current narrative fingerprint and relevant TTS configuration match. A new Phase 2B generation changes the narrative identity—even if similar in wording—so `audio status` reports the old audio as stale and the next ordinary generation replaces it. `--regenerate` intentionally creates another attempt for the same inputs.

TTS writes inside a temporary directory under the audio output filesystem. WAV headers, channels, sample rate, frame count, byte size, and positive duration are validated before atomic replacement. Temporary files are automatically cleaned. TTS failure, invalid/zero-byte output, or validation failure records a failed attempt without changing the prior current generation or audio artifact. Missing narratives produce an actionable error and are never generated as a hidden side effect.

The provenance chain remains source → candidate → edition → narrative generation → speech script → audio generation. Audio never changes editorial content, retention state, or KB semantics.

Troubleshooting:

- List installed voices with `say -v '?'`.
- Verify an artifact with `afinfo outputs/briefing/audio/YYYY-MM-DD-briefing.wav`.
- If `say` fails from a restricted shell, run the command from the authoritative Mac mini user session.
- If status is stale, run `audio generate`; use `--regenerate` only when intentionally recreating the same version.

Phase 2D does not publish or distribute audio and adds no RSS, Apple Podcasts, Spotify, YouTube, hosting, upload, notifications, dashboard UI, music, multiple hosts, conversational simulation, voice cloning, or cloud TTS.

# Phase 1.5 test-suite triage

Date: 2026-08-08
Host: authoritative Mac mini
Repository: `/Users/erickperales/Projects/knowledge_base`

## Baseline before remediation

The documented canonical command is `make test`, which expands to `.venv/bin/python -m pytest tests/ -q`. Pytest was absent from the existing virtual environment, so pytest 8.4.2 was installed locally and pinned in `requirements-dev.txt`.

| Item | Result |
|---|---:|
| Python | 3.9.6 |
| pytest | 8.4.2 |
| Discovered | 1,082 |
| Passed | 1,019 |
| Failed | 63 |
| Errors | 0 |
| Skipped / xfail | 0 / 0 |
| Warnings | 0 |
| Runtime | 2.92 seconds |

The earlier `unittest`-based figure of 1,079 tests, 27 failures, and 37 errors was not authoritative because it did not use the repository's canonical runner. All 63 pytest failures reproduced when the 12 affected modules ran independently (63 failed, 378 passed), so none was order-dependent. The first run did reveal an independent isolation defect: direct pipeline-item execution with a temporary root still wrote legacy `metadata/review-queue.{json,md}` files into the live tree. Those generated artifacts were removed, `run_for_item` now binds queue I/O to its supplied root/domain, and two clean full runs confirmed that they do not recur.

## Root-cause summary

| Root cause | Original failures | Classification | Resolution |
|---|---:|---|---|
| Legacy paths in domain-aware fixtures and assertions | 46 | D | Moved fixtures/assertions to `domains/ai`; created real source-note fixtures for wikilink validation. |
| Removed module-global test hooks | 10 | F | Used supported root parameters and domain paths instead of obsolete constants. |
| Intentional intake/review behavior changed | 4 | B | Updated share response/storage and pending-review expectations without weakening production. |
| Domain root ignored by active endpoints/commands | 3 | A | Fixed dashboard feedback lookup and review purge queue selection; retained Phase 1 gates and locking. |
| Direct pipeline-item root isolation (not one of the 63 failures) | 1 leak | C | Configure queue paths from the item/root before any pipeline write. |

## Full triage table

Every original failure is listed below. Final status for every row is **passed**.

| Tests | Class | Root cause and remediation |
|---|---|---|
| `ApplySynthesisTests::{test_citation_junk_is_removed,test_complete_source_notes_section_is_not_duplicated,test_destination_uses_canonical_slug_not_model_drifted_slug,test_duplicate_inner_frontmatter_is_handled_correctly,test_generation_method_becomes_manual_paste,test_mismatched_title_gets_patched_to_canonical_title,test_missing_source_notes_section_is_injected,test_no_overwrite_by_default,test_partial_source_notes_section_gets_missing_links_appended,test_source_wikilinks_from_prompt_pack_are_recognized_correctly,test_truncated_fence_no_closing_backticks_still_stripped,test_wrapping_fence_with_trailing_llm_junk_is_removed,test_wrapping_markdown_fences_are_removed}` | D | Source-note fixtures were legacy-scoped and invisible to domain wikilink validation; created domain source fixtures and updated the output assertion. |
| `IngestURLMetadataTests::{test_all_optional_fields_written_to_frontmatter,test_blank_language_not_written,test_no_optional_fields_writes_only_source_type,test_tags_written_as_yaml_list}` | D | Assertions searched legacy raw paths; now inspect `raw/domains/ai/articles`. |
| `IngestURLTitleTests::{test_conflicting_title_returns_409,test_slug_from_title_drives_filename,test_title_in_frontmatter,test_url_slug_from_title_not_url_path}` | D | Conflict fixtures and output discovery now use the domain article directory. |
| `IngestFileTitleTests::{test_conflicting_title_returns_409,test_no_suffix_appended_on_conflict,test_slug_from_title_not_original_filename}` | D | Direct calls now pass the domain explicitly and use domain-scoped fixtures. |
| `IngestEndpointRawArticleTests::{test_file_ingest_omits_empty_optional_fields,test_file_ingest_uses_title_for_filename,test_file_ingest_writes_optional_metadata,test_url_ingest_uses_title_for_filename}` | D | Endpoint assertions and manifest lookup now use domain-scoped storage. |
| `QueryEndpointTests::test_feedback_endpoint_marks_answer` | A | The endpoint hard-coded legacy `outputs/answers`; production now resolves `outputs/domains/<domain>/answers`. |
| `ResolveAnswerPathTests::{test_missing_raises,test_resolves_by_stem,test_resolves_with_md_suffix}`, `StatsAggregationTests::test_counts_good_bad_unrated` | F | Tests patched removed `ANSWERS_DIR`; they now patch the supported module root and create domain answers. |
| `SnapshotTests::{test_load_most_recent_returns_none_when_empty,test_load_prior_snapshot_finds_earlier,test_load_prior_snapshot_normalises_legacy_date_filenames,test_load_prior_snapshot_returns_none_when_only_one,test_save_uses_timestamp_filename}` | F | Tests patched removed `SNAPSHOTS_DIR`; they now pass an explicit temporary root. |
| `FileReportTests::{test_creates_report_file,test_force_overwrites}`, `RunIntegrationTests::test_report_flag_creates_file`, `CheckMissingConceptsTests::test_fix_creates_stub` | D | Expected report/concept files now use domain-scoped output paths. |
| `CrossTopicContradictionTests::test_output_file_written_to_contradictions_dir` | F | Removed obsolete `CONTRADICTIONS_DIR` patch and asserted the supported domain output path. |
| `RunTests::{test_run_creates_artifact,test_run_sets_generation_method_ollama_local}` | D | Expected LLM artifacts now use domain-scoped compiled topics. |
| `ReviewPurgeCommandTests::{test_all_rejected_purges_all_rejected_items,test_purge_proceeds_for_rejected_source}` | A | `cmd_purge(root=...)` incorrectly read the module-global live queue. It now resolves the requested domain/root, with intentional legacy fallback. Queue rewrites also use atomic JSON replacement. |
| `ResynthesizeTopicTests::{test_dry_run_returns_preview_without_writing_or_committing,test_insufficient_sources_raises_without_writing,test_resynthesize_updates_topic_note_and_version,test_status_counts_sources}` | D | Topic, registry, and summary fixtures now mirror domain storage and lineage paths. |
| `ReviewableItemsTests::test_excludes_pending_review_items` | B | Pending-review items intentionally remain visible for manual review; renamed and strengthened the assertion to require both eligible states. |
| `ShareEndpointTests::{test_share_writes_json_file_with_correct_content,test_successful_share_queues_and_returns_inbox_id,test_x_share_uses_handle_when_title_is_generic}` | B | Share now uses the intake-only ingestion path and returns filename/domain, not legacy feed JSON/inbox IDs. Tests verify the resulting domain raw note and attribution. |
| `SynthesizeItemTests::test_full_pipeline_success_with_mocked_llm` | D | Added a domain source-note fixture required by strict wikilink validation and asserted the domain summary destination. |
| `AggregateTopicTests::{test_creates_new_topic_note,test_topic_note_output_path_correct,test_updates_existing_topic_note}`, `AggregateForSourceTests::{test_creates_topic_note_on_match,test_explicit_topic_overrides_content_match}`, `FindSourceSummaryTests::test_finds_existing_summary`, `LoadTopicRegistryTests::test_loads_registry` | D | Registry, summaries, raw sources, existing topics, and output assertions now consistently use the `ai` domain. |

## Production changes

- `dashboard.py`: added a domain field to feedback requests and resolves the answer through `outputs_subdir`; corrected the share endpoint contract docstring.
- `scripts/review.py`: `load_queue` accepts an explicit path and `cmd_purge` selects the queue under its supplied root/domain rather than global runtime state.
- `scripts/purge_source.py`: queue updates use `atomic_write_json`, preserving Phase 1 atomic-write guarantees.
- `scripts/pipeline_run.py`: `run_for_item` configures queue paths for its supplied root/domain, preventing direct callers and tests from leaking writes into the authoritative repository.

No approval threshold, ownership boundary, locking behavior, scheduling, watcher processing, Git serialization, or Ollama serialization was weakened.

## Test and infrastructure changes

Modernized: `tests/test_apply_synthesis.py`, `tests/test_dashboard.py`, `tests/test_feedback.py`, `tests/test_graph_health.py`, `tests/test_lint.py`, `tests/test_llm_driver.py`, `tests/test_purge_source.py`, `tests/test_resynthesize_topic.py`, `tests/test_review.py`, `tests/test_share_endpoint.py`, `tests/test_synthesize.py`, and `tests/test_topic_aggregator.py`.

Added `requirements-dev.txt` and `docs/testing.md`. No tests were deleted, skipped, weakened, or excluded. External services remain mocked in the default suite.

## Final verification

- Focused Phase 1 safety suite: **201 passed in 1.07 seconds**.
- Consecutive canonical full run 1: **1,082 passed in 2.62 seconds**.
- Consecutive canonical full run 2: **1,082 passed in 2.42 seconds**.
- Skipped, xfail, errors, failures, and warnings: **0**.
- Dashboard: launchd running (PID 619), HTTP root returned 200.
- Inbox watcher: launchd running (PID 54900).
- Pipeline: scheduled one-shot, 60-second interval, last exit 0; read-only status found zero processable items.
- RSS poller: scheduled one-shot with `--once`, 3,600-second interval, last exit 0; no restart loop.
- Ollama: API reachable; `phi4:latest` and required embedding/query models are installed.
- Locks: lock files exist as expected; `lsof` reported no unexpected holder.
- Live artifacts: no test-generated queue, manifest, note, report, or index files remain.

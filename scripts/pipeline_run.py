"""Fix 2 — Synthesis Automation: run the full post-ingest pipeline for one or more articles.

Chains synthesize → score → topic-aggregate → index-rebuild so that no manual
intervention is needed after a file lands in raw/articles/.

Usage:
    # Process a single article
    python3 scripts/pipeline_run.py SRC-20260418-0001

    # Process all articles with status "pending" in the review queue
    python3 scripts/pipeline_run.py --all

    # Drain the queue continuously (poll every N seconds)
    python3 scripts/pipeline_run.py --watch --interval 30
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).parent))

from git_ops import commit_pipeline_stage  # noqa: E402
from index_notes import run as rebuild_index  # noqa: E402
from score_synthesis import (  # noqa: E402
    ScoreRequest,
    _find_compiled_note,
    score_synthesis,
    update_queue_with_score,
)
from synthesize import (  # noqa: E402
    DEFAULT_MODEL,
    load_queue,
    save_queue,
    synthesize_item,
)
from topic_aggregator import _find_source_summary, aggregate_for_source  # noqa: E402

DEFAULT_THRESHOLD = 0.85
DEFAULT_INTERVAL = 30


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(source_id: str, step: str, msg: str) -> None:
    sid = source_id if source_id else " " * len("SRC-20260418-0001")
    print(f"[{_ts()}] {sid:<22} — {step:<18} {msg}", flush=True)


# ---------------------------------------------------------------------------
# Per-article pipeline
# ---------------------------------------------------------------------------

def run_for_item(
    item: dict[str, object],
    *,
    model: str = DEFAULT_MODEL,
    threshold: float = DEFAULT_THRESHOLD,
    root: Path = ROOT,
    no_commit: bool = False,
) -> bool:
    """Run the full pipeline for one queue item. Returns True on success."""
    source_id = str(item.get("source_id", ""))
    title = str(item.get("title", ""))
    slug = Path(str(item.get("source_note_path", ""))).stem

    # ---- 1. Synthesize -------------------------------------------------------
    t0 = time.monotonic()
    try:
        ok = synthesize_item(
            item,
            title_override="",
            model=model,
            force=False,
            root=root,
        )
    except Exception as exc:
        _log(source_id, "synthesize", f"ERROR  {exc}")
        return False

    elapsed = time.monotonic() - t0
    if not ok:
        _log(source_id, "synthesize", "FAILED (see above)")
        return False
    _log(source_id, "synthesize", f"OK     ({elapsed:.1f}s)")

    commit_pipeline_stage(
        message=f"synth: {source_id} — {title} (confidence pending)",
        paths=[root / "compiled" / "source_summaries" / f"{slug}-synthesis.md"],
        no_commit=no_commit,
    )

    # ---- 2. Score ------------------------------------------------------------
    # Re-load the queue to get the updated entry (synthesize_item writes to it)
    queue = load_queue()
    updated_item = next((e for e in queue if e.get("source_id") == source_id), item)

    compiled_path = _find_compiled_note(updated_item, root)
    if compiled_path is None:
        _log(source_id, "score", "SKIP   compiled note not found")
    else:
        try:
            result = score_synthesis(ScoreRequest(
                source_id=source_id,
                compiled_note_path=compiled_path,
                model=model,
                auto_approve_threshold=threshold,
                root=root,
            ))
            update_queue_with_score(result, no_commit=no_commit)
            _log(source_id, "score", f"OK     confidence={result.score:.2f} ({result.band})")

            if result.auto_approved:
                _log(source_id, "auto-approved", "")
        except Exception as exc:
            _log(source_id, "score", f"ERROR  {exc}")
            # Non-fatal — continue to aggregation

    # ---- 3. Topic aggregation ------------------------------------------------
    queue = load_queue()
    updated_item = next((e for e in queue if e.get("source_id") == source_id), item)
    source_summary_path = _find_source_summary(updated_item, root)

    if source_summary_path is None:
        _log(source_id, "topic_aggregate", "SKIP   source summary not found")
    else:
        try:
            aggregate_for_source(updated_item, source_summary_path, model=model, root=root, no_commit=no_commit)
            _log(source_id, "topic_aggregate", "OK")
        except Exception as exc:
            _log(source_id, "topic_aggregate", f"ERROR  {exc}")
            # Non-fatal

    return True


# ---------------------------------------------------------------------------
# Index rebuild (shared across all processed items)
# ---------------------------------------------------------------------------

def run_index_rebuild(root: Path, no_commit: bool = False) -> None:
    try:
        rc = rebuild_index(root, no_commit=no_commit)
        compiled = root / "compiled"
        n = sum(1 for _ in compiled.rglob("*.md")) if compiled.exists() else 0
        status = f"OK     ({n} notes)" if rc == 0 else "FAILED"
        _log("", "index_rebuild", status)
    except Exception as exc:
        _log("", "index_rebuild", f"ERROR  {exc}")


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_run_one(source_id: str, *, model: str, threshold: float, root: Path, no_commit: bool = False) -> int:
    queue = load_queue()
    item = next((e for e in queue if e.get("source_id") == source_id), None)
    if item is None:
        print(f"Error: '{source_id}' not found in review queue.", file=sys.stderr)
        return 1

    status = str(item.get("review_status", ""))
    if status != "pending_review":
        print(
            f"Error: '{source_id}' has status '{status}' — only 'pending_review' items can be processed.",
            file=sys.stderr,
        )
        return 1

    run_for_item(item, model=model, threshold=threshold, root=root, no_commit=no_commit)
    run_index_rebuild(root, no_commit=no_commit)
    return 0


def _pending_items(queue: list[dict[str, object]]) -> list[dict[str, object]]:
    return [e for e in queue if e.get("review_status") == "pending_review"]


def cmd_run_all(*, model: str, threshold: float, root: Path, no_commit: bool = False) -> int:
    queue = load_queue()
    items = _pending_items(queue)
    if not items:
        print("No pending items to process.")
        return 0

    print(f"Processing {len(items)} item(s)...\n")
    failed = 0
    for item in items:
        success = run_for_item(item, model=model, threshold=threshold, root=root, no_commit=no_commit)
        if not success:
            failed += 1

    run_index_rebuild(root, no_commit=no_commit)

    passed = len(items) - failed
    print(f"\nDone: {passed}/{len(items)} succeeded.")
    return 0 if failed == 0 else 1


def cmd_watch(*, interval: int, model: str, threshold: float, root: Path, no_commit: bool = False) -> int:
    print(f"Watching queue every {interval}s (Ctrl-C to stop)…")
    try:
        while True:
            queue = load_queue()
            items = _pending_items(queue)
            if items:
                print(f"\n[{_ts()}] Found {len(items)} pending item(s).")
                for item in items:
                    run_for_item(item, model=model, threshold=threshold, root=root, no_commit=no_commit)
                run_index_rebuild(root, no_commit=no_commit)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full post-ingest pipeline (synthesize → score → aggregate → index)\n"
            "for one or more articles without manual intervention."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source_id",
        nargs="?",
        help="Source ID to process (e.g. SRC-20260418-0001).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all pending items in the review queue.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll the queue continuously and process new items as they arrive.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Polling interval in seconds for --watch. Default: {DEFAULT_INTERVAL}",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Auto-approve threshold (0.0–1.0). Default: {DEFAULT_THRESHOLD}",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        dest="no_commit",
        help="Skip git auto-commits for all pipeline steps.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.watch:
        return cmd_watch(
            interval=args.interval,
            model=args.model,
            threshold=args.threshold,
            root=ROOT,
            no_commit=args.no_commit,
        )

    if args.all:
        return cmd_run_all(model=args.model, threshold=args.threshold, root=ROOT, no_commit=args.no_commit)

    if not args.source_id:
        parser.print_help()
        return 1

    return cmd_run_one(args.source_id, model=args.model, threshold=args.threshold, root=ROOT, no_commit=args.no_commit)


if __name__ == "__main__":
    sys.exit(main())

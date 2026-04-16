"""Phase 2 Synthesis: on-demand synthesis trigger from the review queue.

Reads pending items from metadata/review-queue.json, runs them through the
compile_notes → llm_driver → apply_synthesis pipeline, and updates the queue
status when complete.  Auto-synthesis is intentionally NOT triggered by the
inbox watcher — this command must be invoked explicitly for each queued item.

Usage:
    # Show pending review items
    python3 scripts/synthesize.py --list

    # Synthesize one item by source_id
    python3 scripts/synthesize.py SRC-20260412-0001

    # Override the compiled-note title (defaults to the raw note title)
    python3 scripts/synthesize.py SRC-20260412-0001 --title "Mac mini AI"

    # Force overwrite if a compiled note already exists
    python3 scripts/synthesize.py SRC-20260412-0001 --force

    # Synthesize all pending items in one pass
    python3 scripts/synthesize.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_QUEUE_PATH = ROOT / "metadata" / "review-queue.json"
REVIEW_QUEUE_REPORT_PATH = ROOT / "metadata" / "review-queue.md"
TMP_OUTPUT = ROOT / "tmp" / "synthesis-output.md"
DEFAULT_MODEL = "qwen2.5:14b"


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------

def load_queue() -> list[dict[str, object]]:
    if not REVIEW_QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(REVIEW_QUEUE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def save_queue(entries: list[dict[str, object]]) -> None:
    REVIEW_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE_PATH.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    _write_queue_report(entries)


def _write_queue_report(entries: list[dict[str, object]]) -> None:
    lines = [
        "# Review Queue",
        "",
        f"_Generated on {datetime.now().date().isoformat()}_",
        "",
    ]
    if not entries:
        lines.append("No items in queue.")
        REVIEW_QUEUE_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines.extend([
        "| Title | Source Note | Adapter | Validation | Confidence | Review |",
        "|---|---|---|---|---|---|",
    ])
    for entry in entries:
        conf_score = entry.get("confidence_score")
        conf_band = entry.get("confidence_band", "")
        conf_str = f"{conf_band} {conf_score:.2f}" if conf_score is not None else "—"
        action = entry.get("review_action") or entry.get("review_status", "")
        lines.append(
            f"| {entry.get('title', '')} | `{entry.get('source_note_path', '')}` | "
            f"{entry.get('adapter', '')} | {entry.get('validation_status', '')} | "
            f"{conf_str} | {action} |"
        )
        for issue in entry.get("validation_issues", []):
            lines.append(f"|  |  |  | issue: {issue} |  |  |")
    REVIEW_QUEUE_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_status(
    queue: list[dict[str, object]],
    source_id: str,
    status: str,
    extra: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    updated = []
    for entry in queue:
        if entry.get("source_id") == source_id:
            entry = {**entry, "review_status": status, **(extra or {})}
        updated.append(entry)
    return updated


def find_item(queue: list[dict[str, object]], source_id: str) -> dict[str, object] | None:
    return next((e for e in queue if e.get("source_id") == source_id), None)


def pending_items(queue: list[dict[str, object]]) -> list[dict[str, object]]:
    return [e for e in queue if e.get("review_status") == "pending_review"]


# ---------------------------------------------------------------------------
# List command
# ---------------------------------------------------------------------------

def cmd_list(queue: list[dict[str, object]]) -> int:
    items = pending_items(queue)
    if not items:
        print("No pending review items.")
        return 0

    print(f"Pending review items ({len(items)}):\n")
    for item in items:
        source_id = item.get("source_id", "")
        title = item.get("title", "(untitled)")
        note_path = item.get("source_note_path", "")
        queued_at = str(item.get("queued_at", ""))[:10]
        validation = item.get("validation_status", "unknown")
        issues = item.get("validation_issues", [])
        issue_flag = f"  [{len(issues)} issue(s)]" if issues else ""
        print(f"  {source_id}  {title}")
        print(f"             {note_path}")
        print(f"             Queued: {queued_at}  Validation: {validation}{issue_flag}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Synthesis pipeline
# ---------------------------------------------------------------------------

def _generate_prompt_pack(
    source_note_path: Path,
    title: str,
    force: bool,
    root: Path,
) -> Path | None:
    """Run compile_notes in prompt-pack mode and return the prompt-pack path."""
    sys.path.insert(0, str(Path(__file__).parent))
    from compile_notes import CompileRequest, compile_notes  # noqa: PLC0415

    try:
        created = compile_notes(
            CompileRequest(
                sources=[source_note_path],
                title=title,
                category="source_summary",
                mode="prompt-pack",
                force=force,
                root=root,
            )
        )
    except FileExistsError as exc:
        print(f"  Prompt-pack already exists: {exc}")
        print("  Use --force to regenerate it.")
        return None
    except (FileNotFoundError, ValueError) as exc:
        print(f"  Error generating prompt-pack: {exc}")
        return None

    return created.get("prompt-pack")


def _run_llm(prompt_pack_path: Path, model: str, force: bool, root: Path) -> Path | None:
    """Call Ollama with the prompt-pack and write raw output to tmp/. Returns output path or None."""
    from llm_driver import _check_model_available, call_ollama  # noqa: PLC0415
    from urllib.error import URLError  # noqa: PLC0415

    try:
        _check_model_available(model)
    except (ConnectionError, ValueError) as exc:
        print(f"  Ollama unavailable: {exc}")
        return None

    prompt = prompt_pack_path.read_text(encoding="utf-8")
    print(f"  Model       : {model}")
    print(f"  Prompt size : {len(prompt):,} chars")
    print("  Synthesizing (streaming)...")

    try:
        synthesized = call_ollama(prompt, model)
    except URLError as exc:
        print(f"  LLM call failed: {exc}")
        return None

    TMP_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TMP_OUTPUT.write_text(synthesized, encoding="utf-8")
    print(f"  Raw output  : {TMP_OUTPUT.relative_to(root)}")
    return TMP_OUTPUT


def _apply(
    prompt_pack_path: Path,
    synthesized_path: Path,
    title_override: str,
    force: bool,
    root: Path,
) -> Path | None:
    """Apply synthesized output and return the compiled note path."""
    from apply_synthesis import ApplySynthesisRequest, apply_synthesis  # noqa: PLC0415

    try:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=prompt_pack_path,
                synthesized_file=synthesized_path,
                output_type="compiled",
                title_override=title_override,
                force=force,
                generation_method="ollama_local",
                root=root,
            )
        )
    except FileExistsError as exc:
        print(f"  Compiled note already exists: {exc}")
        print("  Use --force to overwrite.")
        return None
    except (FileNotFoundError, ValueError) as exc:
        print(f"  Error applying synthesis: {exc}")
        return None

    return output_path


def synthesize_item(
    item: dict[str, object],
    *,
    title_override: str,
    model: str,
    force: bool,
    root: Path,
) -> bool:
    """Run the full pipeline for one queued item. Returns True on success."""
    source_id = str(item.get("source_id", ""))
    title = title_override.strip() or str(item.get("title", ""))
    # Append " Synthesis" so the compiled slug differs from the raw note slug,
    # preventing Obsidian wikilink ambiguity when both files share the same stem.
    compile_title = f"{title} Synthesis"
    raw_note_path = root / str(item.get("source_note_path", ""))

    print(f"Synthesizing: {title}  ({source_id})")
    print(f"  Source note : {raw_note_path.relative_to(root)}")

    if not raw_note_path.exists():
        print(f"  Error: source note not found: {raw_note_path}")
        return False

    # Step 1 — prompt-pack
    prompt_pack_path = _generate_prompt_pack(raw_note_path, compile_title, force, root)
    if prompt_pack_path is None:
        return False
    print(f"  Prompt-pack : {prompt_pack_path.relative_to(root)}")

    # Step 2 — LLM synthesis (with scaffold fallback)
    synthesized_path = _run_llm(prompt_pack_path, model, force, root)
    if synthesized_path is None:
        print("  Falling back to scaffold (no LLM output available).")
        from compile_notes import CompileRequest, compile_notes  # noqa: PLC0415
        try:
            scaffold_created = compile_notes(
                CompileRequest(
                    sources=[raw_note_path],
                    title=compile_title,
                    category="source_summary",
                    mode="scaffold",
                    force=force,
                    root=root,
                )
            )
        except (FileExistsError, FileNotFoundError, ValueError) as exc:
            print(f"  Scaffold fallback also failed: {exc}")
            return False
        compiled_path = scaffold_created.get("scaffold")
        if compiled_path:
            print(f"  Scaffold    : {compiled_path.relative_to(root)}")
        return compiled_path is not None

    # Step 3 — apply synthesis
    compiled_path = _apply(prompt_pack_path, synthesized_path, compile_title, force, root)
    if compiled_path is None:
        return False

    print(f"  Compiled    : {compiled_path.relative_to(root)}")
    return True


# ---------------------------------------------------------------------------
# Scoring integration (non-blocking — errors never fail synthesis)
# ---------------------------------------------------------------------------

def _run_scoring(item: dict[str, object], *, model: str, root: Path) -> None:
    """Call score_synthesis for one successfully synthesized item.

    Runs after the queue has been saved with 'synthesized' status so that
    score fields are layered on top (not overwritten by a subsequent save_queue call).
    """
    try:
        from score_synthesis import (  # noqa: PLC0415
            ScoreRequest,
            _find_compiled_note,
            score_synthesis,
            update_queue_with_score,
        )
        compiled_path = _find_compiled_note(item, root)
        if compiled_path is None:
            print("  Warning: compiled note not found for scoring — skipping.")
            return
        source_id = str(item.get("source_id", ""))
        result = score_synthesis(ScoreRequest(
            source_id=source_id,
            compiled_note_path=compiled_path,
            model=model,
            root=root,
        ))
        update_queue_with_score(result)
        label = "auto-approved" if result.auto_approved else "needs review"
        print(f"  Confidence  : {result.band} {result.score:.2f}  ({label})")
    except Exception as exc:  # noqa: BLE001
        print(f"  Warning: confidence scoring failed: {exc}")


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

def cmd_synthesize(
    source_id: str,
    *,
    title_override: str,
    model: str,
    force: bool,
    root: Path,
) -> int:
    queue = load_queue()
    item = find_item(queue, source_id)
    if item is None:
        print(f"Error: source_id '{source_id}' not found in review queue.", file=sys.stderr)
        return 1

    success = synthesize_item(
        item,
        title_override=title_override,
        model=model,
        force=force,
        root=root,
    )
    status = "synthesized" if success else "synthesis_failed"
    queue = _update_status(queue, source_id, status, {"synthesized_at": datetime.now().isoformat()})
    save_queue(queue)
    print(f"  Queue status: {status}")

    if success:
        _run_scoring(item, model=model, root=root)

    return 0 if success else 1


def cmd_all(*, title_override: str, model: str, force: bool, root: Path) -> int:
    queue = load_queue()
    items = pending_items(queue)
    if not items:
        print("No pending review items.")
        return 0

    print(f"Synthesizing {len(items)} pending item(s)...\n")
    failed = 0
    for item in items:
        source_id = str(item.get("source_id", ""))
        success = synthesize_item(
            item,
            title_override=title_override,
            model=model,
            force=force,
            root=root,
        )
        status = "synthesized" if success else "synthesis_failed"
        queue = _update_status(queue, source_id, status, {"synthesized_at": datetime.now().isoformat()})
        if not success:
            failed += 1
        print()

    save_queue(queue)

    # Score all successfully synthesized items (failed ones are skipped)
    failed_ids = {
        str(e.get("source_id")) for e in queue if e.get("review_status") == "synthesis_failed"
    }
    for item in items:
        if str(item.get("source_id", "")) not in failed_ids:
            _run_scoring(item, model=model, root=root)

    passed = len(items) - failed
    print(f"Done: {passed}/{len(items)} synthesized successfully.")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 Synthesis: trigger on-demand synthesis for a queued review item.\n"
            "Runs: compile_notes (prompt-pack) → llm_driver → apply_synthesis → queue update."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source_id",
        nargs="?",
        help="Source ID of the review queue item to synthesize (e.g. SRC-20260412-0001).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all pending review items and exit.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Synthesize all pending items in one pass.",
    )
    parser.add_argument(
        "--title",
        default="",
        dest="title_override",
        help="Override the compiled-note title (defaults to the raw note title).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing prompt-pack and compiled note if they already exist.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    queue = load_queue()

    if args.list:
        return cmd_list(queue)

    if args.all:
        return cmd_all(
            title_override=args.title_override,
            model=args.model,
            force=args.force,
            root=ROOT,
        )

    if not args.source_id:
        parser.print_help()
        return 1

    return cmd_synthesize(
        args.source_id,
        title_override=args.title_override,
        model=args.model,
        force=args.force,
        root=ROOT,
    )


if __name__ == "__main__":
    sys.exit(main())

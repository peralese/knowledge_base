"""Phase 4 Review CLI: approve or reject synthesized items in the review queue.

Operates on items with review_status == "synthesized".  Items are displayed sorted
by confidence (low first) so the ones needing most attention appear at the top.

Usage:
    # List synthesized items with confidence scores
    python3 scripts/review.py list

    # List with full synthesis content shown
    python3 scripts/review.py list --full

    # Show full detail for a single item
    python3 scripts/review.py show SRC-20260412-0001

    # Interactive session: walk through queue with single-keypress decisions
    python3 scripts/review.py session

    # Approve one item
    python3 scripts/review.py approve SRC-20260412-0001

    # Reject one item (optional reason)
    python3 scripts/review.py reject SRC-20260412-0001 --reason "off-topic content"

    # Approve all items scoring >= threshold (catches any the auto-approver missed)
    python3 scripts/review.py approve --all-high-confidence
    python3 scripts/review.py approve --all-high-confidence --threshold 0.80
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_QUEUE_PATH = ROOT / "metadata" / "review-queue.json"
REVIEW_QUEUE_REPORT_PATH = ROOT / "metadata" / "review-queue.md"

sys.path.insert(0, str(Path(__file__).parent))
from git_ops import commit_pipeline_stage  # noqa: E402
from purge_source import purge_source  # noqa: E402


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


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _set_frontmatter_field(text: str, key: str, value_str: str) -> str:
    """Set a scalar frontmatter field in note text. Replaces if present, inserts if absent."""
    pattern = rf"^{re.escape(key)}:.*$"
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, f"{key}: {value_str}", text, flags=re.MULTILINE)
    return re.sub(r"\n---\n", f"\n{key}: {value_str}\n---\n", text, count=1)


def _find_compiled_note(item: dict[str, object], root: Path) -> Path | None:
    """Derive the compiled note path from a queue entry's source_note_path."""
    note_path_str = str(item.get("source_note_path", ""))
    if not note_path_str:
        return None
    slug = Path(note_path_str).stem
    candidate = root / "compiled" / "source_summaries" / f"{slug}-synthesis.md"
    return candidate if candidate.exists() else None


def _patch_note_approved(path: Path, approved: bool) -> None:
    """Write approved field into the note's frontmatter."""
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
        text = _set_frontmatter_field(text, "approved", "true" if approved else "false")
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Review actions (pure functions — callers do load/save)
# ---------------------------------------------------------------------------

def approve(
    queue: list[dict[str, object]],
    source_id: str,
    *,
    method: str = "manual",
) -> tuple[list[dict[str, object]], bool]:
    """Return (updated_queue, found).  Sets review_action='approved' on matching entry."""
    now = datetime.now().isoformat()
    found = False
    updated = []
    for entry in queue:
        if entry.get("source_id") == source_id:
            found = True
            entry = {
                **entry,
                "review_action": "approved",
                "review_method": method,
                "reviewed_at": now,
            }
        updated.append(entry)
    return updated, found


def reject(
    queue: list[dict[str, object]],
    source_id: str,
    *,
    reason: str = "",
) -> tuple[list[dict[str, object]], bool]:
    """Return (updated_queue, found).  Sets review_action='rejected' on matching entry."""
    now = datetime.now().isoformat()
    found = False
    updated = []
    for entry in queue:
        if entry.get("source_id") == source_id:
            found = True
            extra: dict[str, object] = {
                "review_action": "rejected",
                "review_method": "manual",
                "reviewed_at": now,
            }
            if reason:
                extra["rejection_reason"] = reason
            entry = {**entry, **extra}
        updated.append(entry)
    return updated, found


def approve_all_high_confidence(
    queue: list[dict[str, object]],
    threshold: float = 0.85,
) -> tuple[list[dict[str, object]], int]:
    """Approve all unreviewed synthesized items scoring >= threshold.

    Returns (updated_queue, count_approved).
    """
    now = datetime.now().isoformat()
    count = 0
    updated = []
    for entry in queue:
        score = entry.get("confidence_score")
        already_reviewed = entry.get("review_action") is not None
        if (
            entry.get("review_status") == "synthesized"
            and score is not None
            and float(score) >= threshold
            and not already_reviewed
        ):
            entry = {
                **entry,
                "review_action": "approved",
                "review_method": "manual",
                "reviewed_at": now,
            }
            count += 1
        updated.append(entry)
    return updated, count


# ---------------------------------------------------------------------------
# Listing helpers
# ---------------------------------------------------------------------------

_BAND_ORDER = {"low": 0, "medium": 1, "high": 2}


def _reviewable_items(queue: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return synthesized items not yet manually reviewed, sorted low-confidence first."""
    items = [
        e for e in queue
        if e.get("review_status") == "synthesized"
        and e.get("review_action") != "approved"
        and e.get("review_action") != "rejected"
    ]
    items.sort(key=lambda e: _BAND_ORDER.get(str(e.get("confidence_band", "")), 1))
    return items


def list_pending_review(queue: list[dict[str, object]]) -> int:
    items = _reviewable_items(queue)
    if not items:
        print("No items awaiting review.")
        return 0

    print(f"\n{'ID':<22} {'Title':<30} {'Confidence':<16} {'Status'}")
    print("-" * 80)
    for entry in items:
        sid = str(entry.get("source_id", ""))
        title = str(entry.get("title", ""))[:30]
        score = entry.get("confidence_score")
        band = str(entry.get("confidence_band", "—"))
        score_str = f"{band} {score:.2f}" if score is not None else "unscored"
        review_status = str(entry.get("review_action") or "needs review")
        print(f"{sid:<22} {title:<30} {score_str:<16} {review_status}")
    print(f"\n{len(items)} item(s) awaiting review.")
    return 0


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def _read_compiled_content(item: dict, root: Path) -> str:
    """Return the full compiled synthesis text for a queue entry, or an explanatory message."""
    path = _find_compiled_note(item, root)
    if path is None:
        return "[No compiled synthesis path found for this item]"
    if not path.exists():
        return f"[Compiled note not found: {path}]"
    return path.read_text(encoding="utf-8")


def _read_canonical_url(item: dict, root: Path) -> str:
    """Extract canonical_url from the raw article frontmatter for a queue entry."""
    note_path_str = str(item.get("source_note_path", ""))
    if not note_path_str:
        return ""
    path = root / note_path_str
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        m = re.search(r'^canonical_url:\s*"?([^"\n]+)"?\s*$', text, re.MULTILINE)
        return m.group(1).strip() if m else ""
    except OSError:
        return ""


_SEP = "─" * 72


def _print_item_header(item: dict, root: Path) -> None:
    score = item.get("confidence_score")
    band = str(item.get("confidence_band", ""))
    confidence_str = f"{band} {score:.2f}" if score is not None else "unscored"
    url = _read_canonical_url(item, root)
    print(_SEP)
    print(f"ID:         {item.get('source_id', '')}")
    print(f"Title:      {item.get('title', '')}")
    print(f"Confidence: {confidence_str}")
    print(f"Status:     {item.get('review_action') or item.get('review_status', '')}")
    if url:
        print(f"URL:        {url}")
    print(f"Date:       {str(item.get('queued_at', ''))[:10]}")


def cmd_list(*, full: bool = False) -> int:
    queue = load_queue()
    items = _reviewable_items(queue)
    if not items:
        print("No items awaiting review.")
        return 0

    if not full:
        return list_pending_review(queue)

    for item in items:
        _print_item_header(item, ROOT)
        print(_SEP)
        print(_read_compiled_content(item, ROOT))
        print()
    print(f"{len(items)} item(s) awaiting review.")
    return 0


def cmd_show(source_id: str, *, root: Path = ROOT) -> int:
    queue = load_queue()
    item = next((e for e in queue if e.get("source_id") == source_id), None)
    if item is None:
        print(f"Error: '{source_id}' not found in review queue.", file=sys.stderr)
        return 1
    _print_item_header(item, root)
    print(_SEP)
    print(_read_compiled_content(item, root))
    print(_SEP)
    return 0


def _getch() -> str:
    """Read a single keypress from stdin without requiring Enter. Unix only."""
    import termios  # noqa: PLC0415
    import tty  # noqa: PLC0415
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def cmd_session(*, root: Path = ROOT, no_commit: bool = False) -> int:
    """Interactive review session: walks through synthesized items one at a time.

    Audit findings:
    - CLI list shows only metadata (ID, title, confidence, status) — no synthesis text.
    - It takes two separate commands to review one item: list then approve/reject.
    - No sequential mode exists; user must re-run list after each action.
    - Dashboard has a Preview button that lazily loads synthesis, but still requires
      separate clicks per item and does not auto-advance.
    - 9 items currently in queue at time of 2C implementation.
    Session addresses: full context per item + single-keypress flow + auto-advance.
    """
    queue = load_queue()
    items = _reviewable_items(queue)
    if not items:
        print("No items awaiting review. Queue is empty.")
        return 0

    total = len(items)
    approved_ids: list[str] = []
    rejected_ids: list[str] = []
    skipped_ids: list[str] = []

    print(f"\nReview session — {total} item(s) queued")
    print("Controls: [a] approve  [r] reject  [s] skip  [q] quit\n")

    try:
        for idx, item in enumerate(items, 1):
            source_id = str(item.get("source_id", ""))
            print(f"\n[{idx}/{total}]")
            _print_item_header(item, ROOT)
            print(_SEP)
            print(_read_compiled_content(item, ROOT))
            print()
            print(f"[{idx}/{total}] Action: [a]pprove / [r]eject / [s]kip / [q]uit  ", end="", flush=True)

            while True:
                ch = _getch().lower()
                if ch == "a":
                    print("approve")
                    approved_ids.append(source_id)
                    break
                if ch == "r":
                    print("reject")
                    rejected_ids.append(source_id)
                    break
                if ch == "s":
                    print("skip")
                    skipped_ids.append(source_id)
                    break
                if ch in ("q", "\x03"):  # q or Ctrl-C
                    print("quit")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print()

    # Apply decisions
    current_queue = load_queue()
    now = datetime.now().isoformat()
    updated: list[dict] = []
    note_paths: list[Path] = []
    for entry in current_queue:
        sid = entry.get("source_id")
        if sid in approved_ids:
            entry = {**entry, "review_action": "approved", "review_method": "manual", "reviewed_at": now}
            path = _find_compiled_note(entry, root)
            if path:
                _patch_note_approved(path, approved=True)
                note_paths.append(path)
        elif sid in rejected_ids:
            entry = {**entry, "review_action": "rejected", "review_method": "manual", "reviewed_at": now}
            path = _find_compiled_note(entry, root)
            if path:
                _patch_note_approved(path, approved=False)
                note_paths.append(path)
        updated.append(entry)
    save_queue(updated)

    if approved_ids or rejected_ids:
        commit_pipeline_stage(
            message=f"review: session — {len(approved_ids)} approved, {len(rejected_ids)} rejected",
            paths=[REVIEW_QUEUE_PATH, *note_paths],
            no_commit=no_commit,
        )

    print(f"\nSession complete — approved: {len(approved_ids)}  rejected: {len(rejected_ids)}  skipped: {len(skipped_ids)}")
    return 0


def cmd_approve(
    source_id: str | None,
    *,
    all_high: bool,
    threshold: float,
    root: Path = ROOT,
    no_commit: bool = False,
) -> int:
    queue = load_queue()

    if all_high:
        updated, count = approve_all_high_confidence(queue, threshold)
        save_queue(updated)
        if count == 0:
            print(f"No unreviewed items scoring >= {threshold}.")
        else:
            print(f"Approved {count} high-confidence item(s) (threshold: {threshold}).")
            note_paths = []
            for entry in updated:
                if entry.get("review_action") == "approved":
                    path = _find_compiled_note(entry, root)
                    if path:
                        _patch_note_approved(path, approved=True)
                        note_paths.append(path)
            commit_pipeline_stage(
                message=f"review: approved {count} high-confidence items",
                paths=[REVIEW_QUEUE_PATH, *note_paths],
                no_commit=no_commit,
            )
        return 0

    if not source_id:
        print("Error: provide a source_id or use --all-high-confidence.", file=sys.stderr)
        return 1

    updated, found = approve(queue, source_id)
    if not found:
        print(f"Error: '{source_id}' not found in review queue.", file=sys.stderr)
        return 1

    save_queue(updated)
    item = next((e for e in updated if e.get("source_id") == source_id), {})
    path = _find_compiled_note(item, root)
    if path:
        _patch_note_approved(path, approved=True)
    print(f"Approved: {item.get('title', source_id)}")
    commit_pipeline_stage(
        message=f"review: approved {source_id} — {item.get('title', '')}",
        paths=[REVIEW_QUEUE_PATH] + ([path] if path else []),
        no_commit=no_commit,
    )
    return 0


def cmd_reject(source_id: str, *, reason: str, root: Path = ROOT, no_commit: bool = False) -> int:
    queue = load_queue()
    updated, found = reject(queue, source_id, reason=reason)
    if not found:
        print(f"Error: '{source_id}' not found in review queue.", file=sys.stderr)
        return 1

    save_queue(updated)
    item = next((e for e in updated if e.get("source_id") == source_id), {})
    path = _find_compiled_note(item, root)
    if path:
        _patch_note_approved(path, approved=False)
    suffix = f" — reason: {reason}" if reason else ""
    print(f"Rejected: {item.get('title', source_id)}{suffix}")
    commit_pipeline_stage(
        message=f"review: rejected {source_id} — {item.get('title', '')}",
        paths=[REVIEW_QUEUE_PATH] + ([path] if path else []),
        no_commit=no_commit,
    )
    return 0


# ---------------------------------------------------------------------------
# Purge command
# ---------------------------------------------------------------------------

def _load_queue_from_root(root: Path) -> list[dict]:
    queue_path = root / "metadata" / "review-queue.json"
    if not queue_path.exists():
        return []
    try:
        data = json.loads(queue_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _purge_one(
    source_id: str,
    queue: list[dict],
    *,
    dry_run: bool,
    force: bool,
    root: Path,
) -> bool:
    """Purge a single source.  Returns True if the purge ran (or dry-ran)."""
    entry = next((e for e in queue if e.get("source_id") == source_id), None)

    if entry is None and not force:
        print(f"Error: '{source_id}' not found in review queue.", file=sys.stderr)
        return False

    action = str((entry or {}).get("review_action") or "pending")
    if action != "rejected" and not force:
        print(
            f"Error: {source_id} is not rejected (current state: {action}).\n"
            "Only rejected items can be purged. Use --force to override.",
            file=sys.stderr,
        )
        return False

    try:
        result = purge_source(source_id, root, dry_run=dry_run)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return False

    conf = (entry or {}).get("confidence_score")
    conf_str = f"{conf:.2f}" if conf is not None else "—"

    if dry_run:
        print(f'\n{source_id}  "{result["title"]}"')
        print(f"  State            : {action} (confidence: {conf_str})")
        print("  Will remove:")
        for item in result["removed"]:
            print(f"    ✓ {item}")
        for item in result["skipped"]:
            print(f"    ✗ {item}")
    else:
        print(f'\nPurging {source_id}  "{result["title"]}"')
        for item in result["removed"]:
            print(f"  Removed : {item}")
        for item in result["skipped"]:
            print(f"  Skipped : {item}")

    return True


def cmd_purge(
    source_id: str | None,
    *,
    all_rejected: bool,
    dry_run: bool,
    force: bool,
    root: Path = ROOT,
    no_commit: bool = False,
) -> int:
    queue = _load_queue_from_root(root)

    targets: list[str]
    if all_rejected:
        targets = [
            str(e["source_id"])
            for e in queue
            if e.get("review_action") == "rejected"
        ]
        if not targets:
            print("No rejected items found in review queue.")
            return 0
    elif source_id:
        targets = [source_id]
    else:
        print("Error: provide a source_id or use --all-rejected.", file=sys.stderr)
        return 1

    if dry_run:
        print("Dry run — no files will be deleted.")

    purged: list[str] = []
    for sid in targets:
        current_queue = _load_queue_from_root(root)
        ok = _purge_one(sid, current_queue, dry_run=dry_run, force=force, root=root)
        if ok and not dry_run:
            purged.append(sid)

    if dry_run:
        if targets:
            print(f"\n  Run without --dry-run to delete {len(targets)} item(s).")
        return 0

    if not purged:
        return 1

    n = len(purged)
    msg = (
        f"chore(purge): remove rejected source {purged[0]} [purge]"
        if n == 1
        else f"chore(purge): remove {n} rejected sources [purge]"
    )

    print(f"\nPurge complete ({n} source(s)). Run `python3 scripts/lint.py` to verify.")

    try:
        commit_pipeline_stage(
            message=msg,
            paths=["metadata/source-manifest.json", "metadata/review-queue.json",
                   "metadata/prompts", "compiled/source_summaries", "raw/articles"],
            no_commit=no_commit,
            root=root,
        )
    except RuntimeError as exc:
        print(f"Warning: git commit failed — {exc}", file=sys.stderr)

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 4 Review: approve or reject synthesized items in the review queue.\n"
            "Items are sorted by confidence (low first) so the riskiest outputs surface first."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # list
    list_p = subparsers.add_parser("list", help="List synthesized items awaiting review.")
    list_p.add_argument(
        "--full",
        action="store_true",
        help="Show full synthesis content for each queued item.",
    )

    # show
    show_p = subparsers.add_parser("show", help="Show full detail for a single queue item.")
    show_p.add_argument("source_id", help="Source ID to display (e.g. SRC-20260412-0001).")

    # session
    session_p = subparsers.add_parser(
        "session",
        help="Interactive review session: walk through queue items with single-keypress decisions.",
    )
    session_p.add_argument(
        "--no-commit",
        action="store_true",
        dest="no_commit",
        help="Skip git auto-commit after the session.",
    )

    # approve
    approve_p = subparsers.add_parser("approve", help="Approve one item or all high-confidence items.")
    approve_p.add_argument(
        "source_id",
        nargs="?",
        help="Source ID to approve (e.g. SRC-20260412-0001).",
    )
    approve_p.add_argument(
        "--all-high-confidence",
        action="store_true",
        help="Approve all unreviewed items scoring >= threshold.",
    )
    approve_p.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Confidence threshold for --all-high-confidence. Default: 0.85",
    )

    # reject
    reject_p = subparsers.add_parser("reject", help="Reject one item.")
    reject_p.add_argument(
        "source_id",
        help="Source ID to reject (e.g. SRC-20260412-0001).",
    )
    reject_p.add_argument(
        "--reason",
        default="",
        help="Optional reason for rejection.",
    )

    # --no-commit applies to approve and reject subcommands
    for sub in (approve_p, reject_p):
        sub.add_argument(
            "--no-commit",
            action="store_true",
            dest="no_commit",
            help="Skip git auto-commit after the review action.",
        )

    # purge
    purge_p = subparsers.add_parser(
        "purge",
        help="Remove all artifacts for one or all rejected sources.",
    )
    purge_p.add_argument(
        "source_id",
        nargs="?",
        help="Source ID to purge (e.g. SRC-20260425-0004).",
    )
    purge_p.add_argument(
        "--all-rejected",
        action="store_true",
        dest="all_rejected",
        help="Purge all sources with review_action='rejected'.",
    )
    purge_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show what would be deleted without making any changes.",
    )
    purge_p.add_argument(
        "--force",
        action="store_true",
        help="Override the rejected-only guard and purge any source.",
    )
    purge_p.add_argument(
        "--no-commit",
        action="store_true",
        dest="no_commit",
        help="Skip git auto-commit after purge.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list" or args.command is None:
        return cmd_list(full=getattr(args, "full", False))

    if args.command == "show":
        return cmd_show(args.source_id, root=ROOT)

    if args.command == "session":
        return cmd_session(root=ROOT, no_commit=getattr(args, "no_commit", False))

    if args.command == "approve":
        return cmd_approve(
            getattr(args, "source_id", None),
            all_high=args.all_high_confidence,
            threshold=args.threshold,
            root=ROOT,
            no_commit=getattr(args, "no_commit", False),
        )

    if args.command == "reject":
        return cmd_reject(args.source_id, reason=args.reason, root=ROOT, no_commit=getattr(args, "no_commit", False))

    if args.command == "purge":
        return cmd_purge(
            getattr(args, "source_id", None),
            all_rejected=args.all_rejected,
            dry_run=args.dry_run,
            force=args.force,
            root=ROOT,
            no_commit=args.no_commit,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Phase 4 Review CLI: approve or reject synthesized items in the review queue.

Operates on items with review_status == "synthesized".  Items are displayed sorted
by confidence (low first) so the ones needing most attention appear at the top.

Usage:
    # List synthesized items with confidence scores
    python3 scripts/review.py list

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

def cmd_list() -> int:
    return list_pending_review(load_queue())


def cmd_approve(source_id: str | None, *, all_high: bool, threshold: float, root: Path = ROOT) -> int:
    queue = load_queue()

    if all_high:
        updated, count = approve_all_high_confidence(queue, threshold)
        save_queue(updated)
        if count == 0:
            print(f"No unreviewed items scoring >= {threshold}.")
        else:
            print(f"Approved {count} high-confidence item(s) (threshold: {threshold}).")
            for entry in updated:
                if entry.get("review_action") == "approved":
                    path = _find_compiled_note(entry, root)
                    if path:
                        _patch_note_approved(path, approved=True)
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
    return 0


def cmd_reject(source_id: str, *, reason: str, root: Path = ROOT) -> int:
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
    subparsers.add_parser("list", help="List synthesized items awaiting review.")

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list" or args.command is None:
        return cmd_list()

    if args.command == "approve":
        return cmd_approve(
            getattr(args, "source_id", None),
            all_high=args.all_high_confidence,
            threshold=args.threshold,
            root=ROOT,
        )

    if args.command == "reject":
        return cmd_reject(args.source_id, reason=args.reason, root=ROOT)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

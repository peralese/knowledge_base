"""Phase 4 Confidence Scoring: self-critique pass through Ollama to score synthesis quality.

Reads synthesized items from metadata/review-queue.json, sends each compiled note
through an Ollama self-critique prompt, parses a 0.0–1.0 confidence score, and
updates the queue with the result.  Items scoring >= threshold (default 0.85) are
auto-approved without human review.

Usage:
    # Score one item by source_id
    python3 scripts/score_synthesis.py SRC-20260412-0001

    # Score all synthesized-but-unscored items
    python3 scripts/score_synthesis.py --all

    # Show scored items and their scores
    python3 scripts/score_synthesis.py --list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_QUEUE_PATH = ROOT / "metadata" / "review-queue.json"
REVIEW_QUEUE_REPORT_PATH = ROOT / "metadata" / "review-queue.md"
DEFAULT_MODEL = "qwen2.5:14b"
DEFAULT_AUTO_APPROVE_THRESHOLD = 0.85

# Import llm_driver functions at module level so tests can patch them on this module.
sys.path.insert(0, str(Path(__file__).parent))
from llm_driver import _check_model_available, call_ollama  # noqa: E402, PLC0415


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScoreRequest:
    source_id: str
    compiled_note_path: Path
    model: str = DEFAULT_MODEL
    auto_approve_threshold: float = DEFAULT_AUTO_APPROVE_THRESHOLD
    root: Path = field(default_factory=lambda: ROOT)


@dataclass
class ScoreResult:
    source_id: str
    score: float
    band: str           # "high" | "medium" | "low"
    reasoning: str
    auto_approved: bool


# ---------------------------------------------------------------------------
# Queue helpers (self-contained — keeps this script independent of synthesize.py)
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
# Scoring helpers
# ---------------------------------------------------------------------------

def band_from_score(score: float, threshold: float = DEFAULT_AUTO_APPROVE_THRESHOLD) -> str:
    """Map a 0.0–1.0 score to a confidence band label."""
    if score >= threshold:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


_CRITIQUE_TEMPLATE = """\
You are evaluating a synthesis note produced from a source document.
Rate the quality of this synthesis on a scale from 0.0 to 1.0.

Criteria:
- Accuracy: Does it faithfully represent the source material? (40%)
- Completeness: Are the key points captured? (30%)
- Clarity: Is it well-structured and readable? (30%)

Return ONLY valid JSON in this format:
{{"score": 0.87, "reasoning": "one or two sentences"}}

Synthesis note to evaluate:
---
{note_text}
---
"""


def _build_critique_prompt(note_text: str) -> str:
    return _CRITIQUE_TEMPLATE.format(note_text=note_text)


def _parse_score_response(raw: str) -> tuple[float, str]:
    """Extract (score, reasoning) from an LLM response.

    The model may wrap JSON in prose, so we search for the first JSON object
    that contains a "score" key.  Falls back to (0.5, "Score parse failed").
    """
    json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            score = float(data.get("score", -1))
            reasoning = str(data.get("reasoning", "")).strip()
            if 0.0 <= score <= 1.0 and reasoning:
                return score, reasoning
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return 0.5, "Score parse failed"


def score_synthesis(request: ScoreRequest) -> ScoreResult:
    """Run the self-critique prompt against a compiled note and return a ScoreResult.

    On any LLM/connectivity failure, falls back to score=0.5 so that synthesis
    status is never blocked by a scoring error.
    """
    from urllib.error import URLError  # noqa: PLC0415

    try:
        note_text = request.compiled_note_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ScoreResult(
            source_id=request.source_id,
            score=0.5,
            band=band_from_score(0.5, request.auto_approve_threshold),
            reasoning=f"Could not read compiled note: {exc}",
            auto_approved=False,
        )

    prompt = _build_critique_prompt(note_text)

    try:
        _check_model_available(request.model)
        raw_response = call_ollama(prompt, request.model)
        score, reasoning = _parse_score_response(raw_response)
    except (ConnectionError, ValueError, URLError, OSError):
        score, reasoning = 0.5, "Ollama unavailable — score defaulted to 0.5"

    band = band_from_score(score, request.auto_approve_threshold)
    auto_approved = score >= request.auto_approve_threshold

    _patch_note_with_score(request.compiled_note_path, score, auto_approved)

    return ScoreResult(
        source_id=request.source_id,
        score=score,
        band=band,
        reasoning=reasoning,
        auto_approved=auto_approved,
    )


def update_entry_with_score(entry: dict[str, object], result: ScoreResult) -> dict[str, object]:
    """Return a new entry dict with confidence and review fields applied (pure function)."""
    now = datetime.now().isoformat()
    extra: dict[str, object] = {
        "confidence_score": result.score,
        "confidence_band": result.band,
        "confidence_reasoning": result.reasoning,
        "scored_at": now,
        "review_action": None,
        "review_method": None,
        "reviewed_at": None,
    }
    if result.auto_approved:
        extra.update({
            "review_action": "approved",
            "review_method": "auto",
            "reviewed_at": now,
        })
    return {**entry, **extra}


def update_queue_with_score(result: ScoreResult) -> None:
    """Persist scoring result to review-queue.json and regenerate the markdown report."""
    queue = load_queue()
    updated = [
        update_entry_with_score(e, result) if e.get("source_id") == result.source_id else e
        for e in queue
    ]
    save_queue(updated)


# ---------------------------------------------------------------------------
# Helpers shared across CLI commands
# ---------------------------------------------------------------------------

def _synthesized_unscored(queue: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        e for e in queue
        if e.get("review_status") == "synthesized"
        and e.get("confidence_score") is None
    ]


def _find_compiled_note(item: dict[str, object], root: Path) -> Path | None:
    """Derive the compiled note path from a queue entry's source_note_path."""
    note_path_str = str(item.get("source_note_path", ""))
    if not note_path_str:
        return None
    slug = Path(note_path_str).stem
    candidate = root / "compiled" / "source_summaries" / f"{slug}-synthesis.md"
    return candidate if candidate.exists() else None


def _set_frontmatter_field(text: str, key: str, value_str: str) -> str:
    """Set a scalar frontmatter field in note text. Replaces if present, inserts if absent."""
    pattern = rf"^{re.escape(key)}:.*$"
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, f"{key}: {value_str}", text, flags=re.MULTILINE)
    return re.sub(r"\n---\n", f"\n{key}: {value_str}\n---\n", text, count=1)


def _patch_note_with_score(path: Path, score: float, auto_approved: bool) -> None:
    """Write confidence_score (and approved if auto-approved) into the note's frontmatter."""
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
        text = _set_frontmatter_field(text, "confidence_score", str(round(score, 4)))
        if auto_approved:
            text = _set_frontmatter_field(text, "approved", "true")
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_score_one(source_id: str, *, model: str, threshold: float, root: Path) -> int:
    queue = load_queue()
    item = next((e for e in queue if e.get("source_id") == source_id), None)
    if item is None:
        print(f"Error: '{source_id}' not found in review queue.", file=sys.stderr)
        return 1
    if item.get("review_status") != "synthesized":
        status = item.get("review_status")
        print(f"Error: '{source_id}' has status '{status}' — only 'synthesized' items can be scored.")
        return 1

    compiled_path = _find_compiled_note(item, root)
    if compiled_path is None:
        print(f"Error: compiled note not found for '{source_id}'.", file=sys.stderr)
        return 1

    print(f"Scoring: {item.get('title', source_id)}  ({source_id})")
    result = score_synthesis(ScoreRequest(
        source_id=source_id,
        compiled_note_path=compiled_path,
        model=model,
        auto_approve_threshold=threshold,
        root=root,
    ))
    update_queue_with_score(result)

    label = "auto-approved" if result.auto_approved else "needs review"
    print(f"  Confidence  : {result.band} {result.score:.2f}")
    print(f"  Reasoning   : {result.reasoning}")
    print(f"  Status      : {label}")
    return 0


def cmd_score_all(*, model: str, threshold: float, root: Path) -> int:
    queue = load_queue()
    items = _synthesized_unscored(queue)
    if not items:
        print("No synthesized items need scoring.")
        return 0

    print(f"Scoring {len(items)} item(s)...\n")
    failed = 0
    for item in items:
        source_id = str(item.get("source_id", ""))
        compiled_path = _find_compiled_note(item, root)
        if compiled_path is None:
            print(f"  Skipping {source_id}: compiled note not found.")
            failed += 1
            continue
        result = score_synthesis(ScoreRequest(
            source_id=source_id,
            compiled_note_path=compiled_path,
            model=model,
            auto_approve_threshold=threshold,
            root=root,
        ))
        update_queue_with_score(result)
        label = "auto-approved" if result.auto_approved else "needs review"
        print(f"  {source_id}  {result.band} {result.score:.2f}  {label}")

    passed = len(items) - failed
    print(f"\nDone: {passed}/{len(items)} scored.")
    return 0 if failed == 0 else 1


def cmd_list_scored() -> int:
    queue = load_queue()
    scored = [e for e in queue if e.get("confidence_score") is not None]
    if not scored:
        print("No scored items.")
        return 0

    # Sort: low confidence first, then medium, then high
    band_order = {"low": 0, "medium": 1, "high": 2}
    scored.sort(key=lambda e: band_order.get(str(e.get("confidence_band", "")), 1))

    print(f"\n{'ID':<22} {'Title':<30} {'Confidence':<16} {'Review'}")
    print("-" * 80)
    for entry in scored:
        sid = str(entry.get("source_id", ""))
        title = str(entry.get("title", ""))[:30]
        score = entry.get("confidence_score") or 0.0
        band = str(entry.get("confidence_band", "?"))
        action = str(entry.get("review_action") or "pending")
        method = str(entry.get("review_method") or "")
        label = f"{action} ({method})" if method and action != "pending" else action
        print(f"{sid:<22} {title:<30} {band:<8} {score:.2f}    {label}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 4 Scoring: self-critique pass through Ollama to score synthesis quality.\n"
            "Items scoring >= threshold are auto-approved; others surface for human review."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source_id",
        nargs="?",
        help="Source ID to score (e.g. SRC-20260412-0001).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Score all synthesized-but-unscored items.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show scored items and their confidence scores.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_AUTO_APPROVE_THRESHOLD,
        help=f"Auto-approve threshold (0.0–1.0). Default: {DEFAULT_AUTO_APPROVE_THRESHOLD}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        return cmd_list_scored()

    if args.all:
        return cmd_score_all(model=args.model, threshold=args.threshold, root=ROOT)

    if not args.source_id:
        parser.print_help()
        return 1

    return cmd_score_one(args.source_id, model=args.model, threshold=args.threshold, root=ROOT)


if __name__ == "__main__":
    sys.exit(main())

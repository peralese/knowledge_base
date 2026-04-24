"""Phase 6 Linting and Health Checks: scan the wiki for structural problems.

Runs a suite of health checks over compiled and raw notes, then optionally
files a report in outputs/reports/.

Pure-Python checks (always run, no Ollama required):
  wikilinks        — find [[wikilinks]] in compiled notes that point to missing files
  orphans          — find raw notes not referenced by any compiled note
  orphan_summaries — find source summaries not linked to any topic note
  unapproved       — find low/medium-confidence queue items never manually reviewed
  staleness        — flag topic notes with newer approved sources not yet synthesized

LLM-assisted checks (require --llm flag and a running Ollama instance):
  coverage          — ask the model to identify topic gaps based on the wiki index
  contradictions    — find conflicting claims across source summaries within a topic
  missing_concepts  — identify terms referenced across notes with no concept page

Phase 2B checks (dedicated flags):
  --contradictions  — cross-topic contradiction detection between topic notes (LLM)
  --staleness       — staleness detection: newer approved sources not synthesized (pure)
  --all             — run all checks including 2B checks

Usage:
    # Run all pure checks, print report to terminal
    python3 scripts/lint.py

    # Also run LLM-assisted checks
    python3 scripts/lint.py --llm

    # Run LLM checks and auto-create concept stubs for missing concepts
    python3 scripts/lint.py --llm --check missing_concepts --fix

    # File the report as an artifact in outputs/reports/
    python3 scripts/lint.py --report

    # Run only a specific check
    python3 scripts/lint.py --check wikilinks

    # Preview without filing
    python3 scripts/lint.py --llm --report --dry-run

    # 2B: cross-topic contradiction detection
    python3 scripts/lint.py --contradictions

    # 2B: staleness detection (only flag topics where newer source is >30 days newer)
    python3 scripts/lint.py --staleness --days 30

    # 2B: run everything
    python3 scripts/lint.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import URLError

# llm_driver lives alongside lint.py in scripts/
sys.path.insert(0, str(Path(__file__).parent))
from llm_driver import _check_model_available, call_ollama  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"

PURE_CHECKS = ["wikilinks", "orphans", "orphan_summaries", "unapproved"]
LLM_CHECKS  = ["coverage", "contradictions", "missing_concepts"]
PHASE_2B_CHECKS = ["cross_contradictions", "staleness"]
ALL_CHECKS  = PURE_CHECKS + LLM_CHECKS + PHASE_2B_CHECKS

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]+)?\]\]")

CONTRADICTIONS_DIR = ROOT / "outputs" / "contradictions"
STALENESS_DIR = ROOT / "outputs" / "staleness"

# Minimum claim sentences in a topic before including it in cross-topic comparison
MIN_CLAIMS_FOR_COMPARISON = 3
# Minimum confidence to surface a contradiction candidate
CONTRADICTION_CONFIDENCE_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class LintIssue:
    check: str        # "wikilinks" | "orphans" | "orphan_summaries" | ...
    severity: str     # "error" | "warning" | "info"
    message: str
    detail: str = ""  # e.g. the file path where the issue was found


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _strip_frontmatter(text: str) -> str:
    """Return body text with the first YAML frontmatter block removed."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return normalized.strip()
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return normalized.strip()
    return parts[1].strip()


def _parse_compiled_from(text: str) -> list[str]:
    """Extract the compiled_from list from a compiled note's frontmatter."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return []
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return []
    fm_lines = parts[0].splitlines()

    refs: list[str] = []
    in_list = False
    for line in fm_lines:
        if re.match(r"^compiled_from:\s*$", line):
            in_list = True
            continue
        if in_list:
            m = re.match(r'^\s+-\s+"?([^"]+)"?\s*$', line)
            if m:
                refs.append(m.group(1).strip())
            elif line.strip() and not line.startswith(" "):
                break
    return refs


def _parse_title(text: str) -> str | None:
    """Extract the title field from a note's YAML frontmatter."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return None
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return None
    for line in parts[0].splitlines():
        m = re.match(r'^title:\s*"?([^"]+?)"?\s*$', line)
        if m:
            return m.group(1).strip()
    return None


def _parse_json_array(text: str) -> list:
    """Extract and parse the first JSON array from LLM output. Returns [] on failure."""
    m = re.search(r"\[.*?\]", text, re.DOTALL)
    if not m:
        return []
    try:
        result = json.loads(m.group(0))
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Pure-Python checks
# ---------------------------------------------------------------------------

def _all_known_stems(root: Path) -> set[str]:
    """Return stems of every .md file in compiled/ and raw/."""
    stems: set[str] = set()
    for pattern in ["compiled/**/*.md", "raw/**/*.md"]:
        for p in root.glob(pattern):
            stems.add(p.stem)
    return stems


def check_dangling_wikilinks(root: Path) -> list[LintIssue]:
    """Find [[wikilinks]] in compiled notes that point to non-existent files."""
    known = _all_known_stems(root)
    issues: list[LintIssue] = []
    compiled_dir = root / "compiled"
    if not compiled_dir.exists():
        return issues
    for path in sorted(compiled_dir.rglob("*.md")):
        if path.stem == "index":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        body = _strip_frontmatter(text)
        seen: set[str] = set()
        for m in WIKILINK_RE.finditer(body):
            slug = m.group(1).strip()
            if slug in seen:
                continue
            seen.add(slug)
            if slug not in known:
                issues.append(LintIssue(
                    check="wikilinks",
                    severity="error",
                    message=f"`[[{slug}]]` — no matching note found",
                    detail=str(path.relative_to(root)),
                ))
    return issues


def check_orphaned_raw_notes(root: Path) -> list[LintIssue]:
    """Find raw notes not referenced by any compiled note's compiled_from list."""
    raw_dirs = [
        root / "raw" / "articles",
        root / "raw" / "notes",
        root / "raw" / "pdfs",
    ]
    raw_stems: dict[str, Path] = {}
    for d in raw_dirs:
        if d.exists():
            for p in sorted(d.glob("*.md")):
                raw_stems[p.stem] = p

    referenced: set[str] = set()
    compiled_dirs = [
        root / "compiled" / "topics",
        root / "compiled" / "concepts",
        root / "compiled" / "source_summaries",
    ]
    for d in compiled_dirs:
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            text = p.read_text(encoding="utf-8", errors="replace")
            referenced.update(_parse_compiled_from(text))

    issues: list[LintIssue] = []
    for stem, path in sorted(raw_stems.items()):
        if stem not in referenced:
            issues.append(LintIssue(
                check="orphans",
                severity="warning",
                message=f"`{path.relative_to(root)}` — not referenced by any compiled note",
                detail="",
            ))
    return issues


def check_orphan_summaries(root: Path) -> list[LintIssue]:
    """Find source summaries not linked to any topic note's compiled_from."""
    summaries_dir = root / "compiled" / "source_summaries"
    topics_dir = root / "compiled" / "topics"

    if not summaries_dir.exists():
        return []

    summary_stems = {p.stem for p in summaries_dir.glob("*.md")}

    referenced: set[str] = set()
    if topics_dir.exists():
        for topic_path in topics_dir.glob("*.md"):
            text = topic_path.read_text(encoding="utf-8", errors="replace")
            referenced.update(_parse_compiled_from(text))

    issues: list[LintIssue] = []
    for stem in sorted(summary_stems - referenced):
        issues.append(LintIssue(
            check="orphan_summaries",
            severity="warning",
            message=f"`compiled/source_summaries/{stem}.md` — not linked to any topic note",
        ))
    return issues


def check_unapproved(root: Path) -> list[LintIssue]:
    """Find low/medium-confidence queue items that were never manually reviewed."""
    queue_path = root / "metadata" / "review-queue.json"
    if not queue_path.exists():
        return []

    try:
        data = json.loads(queue_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(data, list):
        return []

    issues: list[LintIssue] = []
    for entry in data:
        band = entry.get("confidence_band", "")
        action = entry.get("review_action")
        if band in ("medium", "low") and not action:
            source_id = entry.get("source_id", "unknown")
            title = str(entry.get("title", ""))[:60]
            issues.append(LintIssue(
                check="unapproved",
                severity="warning",
                message=f"`{source_id}` — {band}-confidence item never manually reviewed",
                detail=title,
            ))
    return issues


# ---------------------------------------------------------------------------
# LLM-assisted checks
# ---------------------------------------------------------------------------

def check_coverage_gaps(root: Path, model: str) -> list[LintIssue]:
    """Ask the LLM to identify topic gaps based on the wiki index."""
    index_path = root / "compiled" / "index.md"
    if not index_path.exists():
        return [LintIssue(
            check="coverage",
            severity="info",
            message="compiled/index.md not found — run index_notes.py first",
        )]

    index_text = _strip_frontmatter(
        index_path.read_text(encoding="utf-8", errors="replace")
    )

    prompt = (
        "You are a knowledge base reviewer. Below is an index of compiled notes in a personal wiki.\n\n"
        "Identify:\n"
        "1. Topics that seem underrepresented or have only shallow coverage\n"
        "2. Obvious adjacent topics that are completely missing\n"
        "3. Any raw source notes that appear to lack compiled coverage\n\n"
        "Be specific — name the gaps, do not just describe categories. "
        "Keep your response concise: a numbered list of 3–8 specific gaps.\n\n"
        "## Wiki Index\n\n"
        f"{index_text}\n\n"
        "## Coverage Gaps\n\n"
    )

    print("Running LLM coverage check...")
    try:
        response = call_ollama(prompt, model)
    except URLError as exc:
        return [LintIssue(
            check="coverage",
            severity="info",
            message=f"LLM call failed: {exc}",
        )]

    issues: list[LintIssue] = []
    for line in response.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"^\d+\.\s+(.+)$", stripped)
        text = m.group(1) if m else stripped
        issues.append(LintIssue(
            check="coverage",
            severity="info",
            message=text,
        ))
    return issues


def check_contradictions(root: Path, model: str) -> list[LintIssue]:
    """For each topic with 2+ source summaries, identify contradicting claims."""
    topics_dir = root / "compiled" / "topics"
    summaries_dir = root / "compiled" / "source_summaries"

    if not topics_dir.exists() or not summaries_dir.exists():
        return []

    summary_files: dict[str, Path] = {p.stem: p for p in summaries_dir.glob("*.md")}

    issues: list[LintIssue] = []

    for topic_path in sorted(topics_dir.glob("*.md")):
        topic_text = topic_path.read_text(encoding="utf-8", errors="replace")
        topic_title = _parse_title(topic_text) or topic_path.stem
        source_stems = _parse_compiled_from(topic_text)

        matched: list[tuple[str, Path]] = [
            (stem, summary_files[stem])
            for stem in source_stems
            if stem in summary_files
        ]

        if len(matched) < 2:
            continue

        sources_block = ""
        for stem, path in matched:
            content = _strip_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            sources_block += f"\n## Source: {stem}\n{content}\n"

        prompt = (
            f'You are reviewing source summaries for the topic "{topic_title}".\n'
            "Identify direct contradictions — claims in one source that conflict with claims in another.\n"
            f"{sources_block}\n"
            "Return ONLY a JSON array of objects. Each object must have:\n"
            '  "claim_a": the claim from the first source\n'
            '  "claim_b": the conflicting claim from another source\n'
            '  "source_a": stem of the first source file\n'
            '  "source_b": stem of the second source file\n\n'
            "Return [] if no contradictions are found. No explanation outside the JSON array."
        )

        print(f"  Checking contradictions in: {topic_path.stem}...")
        try:
            response = call_ollama(prompt, model)
        except URLError as exc:
            issues.append(LintIssue(
                check="contradictions",
                severity="info",
                message=f"LLM call failed for topic `{topic_path.stem}`: {exc}",
            ))
            continue

        for item in _parse_json_array(response):
            if not isinstance(item, dict):
                continue
            claim_a = str(item.get("claim_a", "")).strip()
            claim_b = str(item.get("claim_b", "")).strip()
            src_a = str(item.get("source_a", "")).strip()
            src_b = str(item.get("source_b", "")).strip()
            if claim_a and claim_b:
                issues.append(LintIssue(
                    check="contradictions",
                    severity="warning",
                    message=f'"{claim_a}" vs "{claim_b}"',
                    detail=f"{topic_path.stem} ({src_a} ↔ {src_b})",
                ))

    return issues


# ---------------------------------------------------------------------------
# 2B-2 Cross-topic contradiction detection
# ---------------------------------------------------------------------------

def _extract_claim_sentences(body: str) -> list[str]:
    """Extract claim sentences from a note body.

    A claim sentence: non-question, non-heading, non-placeholder, > 8 words.
    Strips markdown markup before evaluating.
    """
    verb_re = re.compile(
        r"\b(is|are|was|were|be|being|been|has|have|had|must|should|can|cannot|"
        r"will|requires?|supports?|uses?|provides?|allows?|prevents?|includes?|"
        r"means|depends|contains|stores|runs|scopes?|grants?)\b",
        re.IGNORECASE,
    )
    claims: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        if stripped.startswith("_") and stripped.endswith("_"):
            continue
        # Strip markup
        text = re.sub(r"\*+", "", stripped)
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = text.strip()
        # Strip list prefix
        m = re.match(r"^[-*]\s+(.+)$", text)
        if m:
            text = m.group(1).strip()
        m = re.match(r"^\d+\.\s+(.+)$", text)
        if m:
            text = m.group(1).strip()
        # Apply claim filters
        if text.endswith("?"):
            continue
        if len(text.split()) <= 8:
            continue
        if not verb_re.search(text):
            continue
        claims.append(text)
    return claims


def check_cross_topic_contradictions(
    root: Path,
    model: str,
    since: str | None = None,
) -> list[LintIssue]:
    """Compare topic note claims pairwise to find cross-topic contradictions.

    Uses Ollama to compare claim sets. Returns candidate LintIssues and saves
    a JSON report to outputs/contradictions/YYYY-MM-DD-HHMMSS.json.
    Only compares topic notes (not concept or entity notes).
    Topics with fewer than MIN_CLAIMS_FOR_COMPARISON claims are skipped.
    Only surfaces candidates with confidence >= CONTRADICTION_CONFIDENCE_THRESHOLD.
    """
    topics_dir = root / "compiled" / "topics"
    if not topics_dir.exists():
        return []

    topic_files = sorted(topics_dir.glob("*.md"))
    topics: list[tuple[str, str, list[str]]] = []  # (stem, path_rel, claims)

    for path in topic_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        body = _strip_frontmatter(text)
        claims = _extract_claim_sentences(body)
        if len(claims) >= MIN_CLAIMS_FOR_COMPARISON:
            topics.append((path.stem, str(path.relative_to(root)), claims))

    if len(topics) < 2:
        return []

    all_candidates: list[dict] = []
    issues: list[LintIssue] = []
    now_ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")

    print(f"Cross-topic contradiction check: {len(topics)} topics with sufficient claims")

    for i in range(len(topics)):
        for j in range(i + 1, len(topics)):
            stem_a, rel_a, claims_a = topics[i]
            stem_b, rel_b, claims_b = topics[j]

            claims_a_text = "\n".join(f"  - {c}" for c in claims_a[:20])
            claims_b_text = "\n".join(f"  - {c}" for c in claims_b[:20])

            prompt = (
                "You are a knowledge integrity reviewer.\n"
                "Find claims that DIRECTLY CONTRADICT each other — claims that CANNOT BOTH BE TRUE.\n"
                "Surface tension, different levels of detail, or complementary perspectives are NOT contradictions.\n\n"
                f"Topic A: {stem_a}\nClaims:\n{claims_a_text}\n\n"
                f"Topic B: {stem_b}\nClaims:\n{claims_b_text}\n\n"
                "Return ONLY a JSON array. Each element must have exactly these fields:\n"
                f'  "topic_a": "{stem_a}",\n'
                f'  "topic_b": "{stem_b}",\n'
                '  "claim_a": <exact claim text from Topic A>,\n'
                '  "claim_b": <contradicting claim text from Topic B>,\n'
                '  "confidence": <float 0.0-1.0, where 1.0 = definitely a real contradiction>,\n'
                '  "reasoning": <one sentence explaining why these contradict>\n\n'
                "Return [] if no contradictions found. No prose outside the JSON array."
            )

            print(f"  Comparing: {stem_a} × {stem_b}...")
            try:
                response = call_ollama(prompt, model)
            except URLError as exc:
                issues.append(LintIssue(
                    check="cross_contradictions",
                    severity="info",
                    message=f"LLM call failed for {stem_a} × {stem_b}: {exc}",
                ))
                continue

            for item in _parse_json_array(response):
                if not isinstance(item, dict):
                    continue
                confidence = _safe_float(item.get("confidence"), 0.0)
                if confidence < CONTRADICTION_CONFIDENCE_THRESHOLD:
                    continue
                claim_a = str(item.get("claim_a", "")).strip()
                claim_b = str(item.get("claim_b", "")).strip()
                reasoning = str(item.get("reasoning", "")).strip()
                if not claim_a or not claim_b:
                    continue

                level = "HIGH" if confidence >= 0.85 else "MED" if confidence >= 0.70 else "LOW"
                candidate = {
                    "topic_a": stem_a,
                    "topic_b": stem_b,
                    "file_a": rel_a,
                    "file_b": rel_b,
                    "claim_a": claim_a,
                    "claim_b": claim_b,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "timestamp": now_ts,
                    "date": now_ts[:10],
                }
                all_candidates.append(candidate)

    # Save JSON report
    contradictions_dir = root / "outputs" / "contradictions"
    contradictions_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": now_ts,
        "date": now_ts[:10],
        "topics_compared": len(topics),
        "candidates": all_candidates,
    }
    snap_path = contradictions_dir / f"{now_ts}.json"
    snap_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    display_candidates = all_candidates
    if since:
        display_candidates = [c for c in all_candidates if str(c.get("date", "")) >= since]

    header = f"CONTRADICTION CANDIDATES ({len(display_candidates)} found — human review required)"
    print(f"\n{header}")
    if display_candidates:
        print()

    for candidate in display_candidates:
        confidence = _safe_float(candidate.get("confidence"), 0.0)
        level = "HIGH" if confidence >= 0.85 else "MED" if confidence >= 0.70 else "LOW"
        print(f"[{level} {confidence:.2f}] {candidate['file_a']} × {candidate['file_b']}")
        print(f'  Claim A : "{candidate["claim_a"]}"')
        print(f'  Claim B : "{candidate["claim_b"]}"')
        print("  → Flag for review: do these conflict or describe different contexts?")
        print()
        issues.append(LintIssue(
            check="cross_contradictions",
            severity="warning",
            message=f'[{level} {confidence:.2f}] "{candidate["claim_a"]}" vs "{candidate["claim_b"]}"',
            detail=f"{candidate['file_a']} × {candidate['file_b']}",
        ))
    return issues


# ---------------------------------------------------------------------------
# 2B-4 Staleness detection
# ---------------------------------------------------------------------------

def _parse_date_field(text: str, field: str) -> date | None:
    """Parse a date field from frontmatter. Returns None if absent or unparseable."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return None
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return None
    for line in normalized[4:end].splitlines():
        m = re.match(rf"^{re.escape(field)}:\s*[\"']?(\d{{4}}-\d{{2}}-\d{{2}})[\"']?", line)
        if m:
            try:
                return date.fromisoformat(m.group(1))
            except ValueError:
                return None
    return None


def _parse_yaml_bool_local(text: str, field: str) -> bool:
    """Parse a boolean frontmatter field."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return False
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return False
    for line in normalized[4:end].splitlines():
        m = re.match(rf"^{re.escape(field)}:\s*(.+)$", line)
        if m:
            return m.group(1).strip().lower() in {"true", "yes", "1"}
    return False


def _get_topic_date(text: str, path: Path) -> date | None:
    """Get the effective 'last synthesized' date for a topic note.

    Checks last_synthesized, then date_updated, then date_compiled, then file mtime.
    """
    for field in ("last_synthesized", "date_updated", "date_compiled"):
        d = _parse_date_field(text, field)
        if d is not None:
            return d
    # Fall back to file modification time
    try:
        mtime = path.stat().st_mtime
        return date.fromtimestamp(mtime)
    except OSError:
        return None


def check_staleness(
    root: Path,
    days: int = 0,
    fix: bool = False,
) -> list[LintIssue]:
    """Flag topic notes that have newer approved sources not yet synthesized.

    A topic is stale if:
    1. It has a resolvable last-synthesized date
    2. At least one approved source summary sharing wikilinks with the topic
       was created/updated AFTER that date (and more than `days` days after)
    3. That source is not already in the topic's compiled_from list

    No LLM calls — pure date and metadata comparison.
    Saves a JSON report to outputs/staleness/YYYY-MM-DD-HHMMSS.json.
    """
    topics_dir = root / "compiled" / "topics"
    summaries_dir = root / "compiled" / "source_summaries"
    if not topics_dir.exists():
        return []

    # Load all approved source summaries with their dates
    approved_sources: list[tuple[str, date, set[str]]] = []  # (stem, date, wikilink_stems)
    if summaries_dir.exists():
        for path in sorted(summaries_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if not _parse_yaml_bool_local(text, "approved"):
                continue
            src_date = (
                _parse_date_field(text, "approved_at")
                or _parse_date_field(text, "date_approved")
                or _parse_date_field(text, "date_updated")
                or _parse_date_field(text, "date_compiled")
                or _parse_date_field(text, "generated_on")
                or _parse_date_field(text, "date")
            )
            if src_date is None:
                continue
            body = _strip_frontmatter(text)
            link_stems = {m.group(1).strip() for m in WIKILINK_RE.finditer(body)}
            approved_sources.append((path.stem, src_date, link_stems))

    issues: list[LintIssue] = []
    now_ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    stale_topics: list[dict] = []

    for topic_path in sorted(topics_dir.glob("*.md")):
        text = topic_path.read_text(encoding="utf-8", errors="replace")
        topic_date = _get_topic_date(text, topic_path)
        if topic_date is None:
            continue

        # Stems already synthesized into this topic
        compiled_from: set[str] = set(_parse_compiled_from(text))

        # Wikilinks in this topic body
        body = _strip_frontmatter(text)
        topic_links = {m.group(1).strip() for m in WIKILINK_RE.finditer(body)}

        # Find newer approved sources not yet in compiled_from that share wikilinks
        newer_sources: list[tuple[str, date]] = []
        for src_stem, src_date, src_links in approved_sources:
            if src_stem in compiled_from:
                continue
            if src_date <= topic_date:
                continue
            delta_days = (src_date - topic_date).days
            if days > 0 and delta_days < days:
                continue
            # Must share at least one wikilink with the topic
            if not (topic_links & src_links):
                continue
            newer_sources.append((src_stem, src_date))

        if not newer_sources:
            continue

        rel = str(topic_path.relative_to(root))
        newer_sources.sort(key=lambda x: x[1], reverse=True)

        resynth_cmd = f"python3 scripts/resynthesize_topic.py {topic_path.stem}"

        issues.append(LintIssue(
            check="staleness",
            severity="warning",
            message=f"`{rel}` — {len(newer_sources)} newer approved source(s) since {topic_date}",
            detail=f"run: {resynth_cmd}",
        ))
        stale_topics.append({
            "topic": topic_path.stem,
            "file": rel,
            "last_synthesized": str(topic_date),
            "newer_sources": [{"stem": s, "date": str(d)} for s, d in newer_sources],
            "resynthesize_command": resynth_cmd,
        })

    print(f"\nSTALENESS WARNING ({len(stale_topics)} topic{'s' if len(stale_topics) != 1 else ''})")
    for stale in stale_topics:
        print()
        print(f"  {stale['file']}")
        print(f"    Last synthesized : {stale['last_synthesized']}")
        print(
            f"    Newer sources    : {len(stale['newer_sources'])} "
            f"approved sources since {stale['last_synthesized']}"
        )
        for source in stale["newer_sources"][:5]:
            print(f"      - {source['stem']}.md ({source['date']})")
        print(f"    Action           : run `{stale['resynthesize_command']}`")

    if fix and stale_topics:
        print()
        print("Queued re-synthesis commands:")
        for stale in stale_topics:
            print(f"  {stale['resynthesize_command']}")

    # Save JSON report
    staleness_dir = root / "outputs" / "staleness"
    staleness_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": now_ts,
        "date": now_ts[:10],
        "days_threshold": days,
        "fix": fix,
        "stale_topics": stale_topics,
    }
    snap_path = staleness_dir / f"{now_ts}.json"
    snap_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return issues


def _build_concept_stub(slug: str, today: str) -> str:
    """Build the content of a concept stub page."""
    title = slug.replace("-", " ").title()
    return (
        "---\n"
        f'title: "{title}"\n'
        "note_type: concept\n"
        f"slug: {slug}\n"
        f'date_compiled: "{today}"\n'
        f'date_updated: "{today}"\n'
        "sources: []\n"
        "approved: true\n"
        'generation_method: "stub"\n'
        "---\n\n"
        f"# {title}\n\n"
        "_Stub page — created by `lint --fix`. Add content from relevant source summaries._\n\n"
        "## Mentioned In\n\n"
        "## Related Concepts\n"
    )


def check_missing_concepts(root: Path, model: str, fix: bool = False) -> list[LintIssue]:
    """Ask the LLM to identify concepts referenced across notes with no concept page."""
    index_path = root / "compiled" / "index.md"
    if not index_path.exists():
        return [LintIssue(
            check="missing_concepts",
            severity="info",
            message="compiled/index.md not found — run index_notes.py first",
        )]

    index_text = _strip_frontmatter(
        index_path.read_text(encoding="utf-8", errors="replace")
    )

    prompt = (
        "You are reviewing a personal knowledge base wiki index.\n"
        "Identify specific terms, tools, or concepts that are referenced across the notes\n"
        "but have no dedicated concept page in compiled/concepts/.\n\n"
        "## Wiki Index\n\n"
        f"{index_text}\n\n"
        'Return ONLY a JSON array of lowercase hyphenated slugs:\n'
        '["vulnerability-scoring", "patch-cadence"]\n'
        "Return [] if no gaps found. No explanation outside the JSON array."
    )

    print("Running LLM missing-concepts check...")
    try:
        response = call_ollama(prompt, model)
    except URLError as exc:
        return [LintIssue(
            check="missing_concepts",
            severity="info",
            message=f"LLM call failed: {exc}",
        )]

    slugs = _parse_json_array(response)
    issues: list[LintIssue] = []
    today = date.today().isoformat()
    concepts_dir = root / "compiled" / "concepts"

    for slug in slugs:
        if not isinstance(slug, str) or not slug.strip():
            continue
        slug = slug.strip()
        issues.append(LintIssue(
            check="missing_concepts",
            severity="info",
            message=f"`{slug}` — no concept page in compiled/concepts/",
        ))
        if fix:
            stub_path = concepts_dir / f"{slug}.md"
            if not stub_path.exists():
                concepts_dir.mkdir(parents=True, exist_ok=True)
                stub_path.write_text(_build_concept_stub(slug, today), encoding="utf-8")
                print(f"  Created stub: compiled/concepts/{slug}.md")

    return issues


# ---------------------------------------------------------------------------
# Report building and filing
# ---------------------------------------------------------------------------

def build_report(
    issues: list[LintIssue],
    checks_run: list[str],
    today: str,
) -> str:
    """Render a lint report as markdown."""
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    checks_str = ", ".join(f'"{c}"' for c in checks_run)
    frontmatter = (
        "---\n"
        f'title: "Wiki Lint Report {today}"\n'
        f'output_type: "lint_report"\n'
        f'generated_on: "{today}"\n'
        f"checks_run: [{checks_str}]\n"
        f"total_issues: {len(issues)}\n"
        f"errors: {len(errors)}\n"
        f"warnings: {len(warnings)}\n"
        f"info: {len(infos)}\n"
        "---"
    )

    summary = (
        f"# Wiki Lint Report\n\n"
        f"_Generated on {today}_\n\n"
        f"## Summary\n\n"
        f"- Checks run: {', '.join(checks_run)}\n"
        f"- Total issues: {len(issues)} "
        f"({len(errors)} error{'s' if len(errors) != 1 else ''}, "
        f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}, "
        f"{len(infos)} info)\n"
    )

    def _section(label: str, severity_issues: list[LintIssue]) -> str:
        if not severity_issues:
            return f"## {label}\n\n_(none)_\n"
        by_check: dict[str, list[LintIssue]] = {}
        for issue in severity_issues:
            by_check.setdefault(issue.check, []).append(issue)
        lines = [f"## {label}\n"]
        for check, check_issues in by_check.items():
            heading = check.replace("_", " ").title()
            lines.append(f"### {heading}\n")
            for issue in check_issues:
                detail = f" _(in `{issue.detail}`)_" if issue.detail else ""
                lines.append(f"- {issue.message}{detail}")
            lines.append("")
        return "\n".join(lines)

    body = (
        f"{frontmatter}\n\n"
        f"{summary}\n"
        f"{_section('Errors', errors)}\n"
        f"{_section('Warnings', warnings)}\n"
        f"{_section('Info', infos)}\n"
    )
    return body


def file_report(report_text: str, root: Path, today: str, force: bool) -> Path:
    dest = root / "outputs" / "reports" / f"lint-{today}.md"
    if dest.exists() and not force:
        raise FileExistsError(
            f"Report already exists: {dest.relative_to(root)}. Use --force to overwrite."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(report_text, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run(
    root: Path,
    checks: list[str],
    use_llm: bool,
    model: str,
    report: bool,
    force: bool,
    dry_run: bool,
    fix: bool = False,
    cross_contradictions: bool = False,
    staleness: bool = False,
    all_checks: bool = False,
    since: str | None = None,
    days: int = 0,
) -> int:
    today = date.today().isoformat()

    dedicated_cross_only = cross_contradictions and not checks and not staleness and not all_checks
    if all_checks:
        checks_to_run = ALL_CHECKS.copy()
        use_llm = True
    elif dedicated_cross_only:
        checks_to_run = ["cross_contradictions"]
        use_llm = True
    elif staleness and not checks and not cross_contradictions:
        checks_to_run = ["staleness"]
    else:
        checks_to_run = checks if checks else PURE_CHECKS
        if cross_contradictions and "cross_contradictions" not in checks_to_run:
            checks_to_run = checks_to_run + ["cross_contradictions"]
            use_llm = True
        if staleness and "staleness" not in checks_to_run:
            checks_to_run = checks_to_run + ["staleness"]

    if use_llm and not dedicated_cross_only:
        for c in LLM_CHECKS:
            if c not in checks_to_run:
                checks_to_run = checks_to_run + [c]

    if use_llm and any(c in LLM_CHECKS + ["cross_contradictions"] for c in checks_to_run):
        try:
            _check_model_available(model)
        except (ConnectionError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    print(f"Checks        : {', '.join(checks_to_run)}")
    print("-" * 60)

    issues: list[LintIssue] = []

    if "wikilinks" in checks_to_run:
        found = check_dangling_wikilinks(root)
        issues.extend(found)
        print(f"wikilinks        : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "orphans" in checks_to_run:
        found = check_orphaned_raw_notes(root)
        issues.extend(found)
        print(f"orphans          : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "orphan_summaries" in checks_to_run:
        found = check_orphan_summaries(root)
        issues.extend(found)
        print(f"orphan_summaries : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "unapproved" in checks_to_run:
        found = check_unapproved(root)
        issues.extend(found)
        print(f"unapproved       : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "coverage" in checks_to_run:
        found = check_coverage_gaps(root, model)
        issues.extend(found)
        print(f"coverage         : {len(found)} gap{'s' if len(found) != 1 else ''} identified")

    if "contradictions" in checks_to_run:
        found = check_contradictions(root, model)
        issues.extend(found)
        print(f"contradictions   : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "missing_concepts" in checks_to_run:
        found = check_missing_concepts(root, model, fix=fix)
        issues.extend(found)
        print(f"missing_concepts : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "cross_contradictions" in checks_to_run:
        found = check_cross_topic_contradictions(root, model, since=since)
        issues.extend(found)
        print(f"cross_contradictions: {len(found)} candidate{'s' if len(found) != 1 else ''}")

    if "staleness" in checks_to_run:
        found = check_staleness(root, days=days, fix=fix)
        issues.extend(found)
        print(f"staleness        : {len(found)} topic{'s' if len(found) != 1 else ''}")

    print("-" * 60)
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    infos = sum(1 for i in issues if i.severity == "info")
    print(f"Total issues  : {len(issues)} ({errors} errors, {warnings} warnings, {infos} info)")

    report_text = build_report(issues, checks_to_run, today)

    if report or dry_run:
        print()

    if dry_run:
        print("--- REPORT PREVIEW ---\n")
        print(report_text)
        return 0

    if report:
        try:
            dest = file_report(report_text, root, today, force)
            print(f"Report filed  : {dest.relative_to(root)}")
        except FileExistsError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 6 Linting: scan the wiki for structural problems."
    )
    parser.add_argument(
        "--check",
        choices=ALL_CHECKS,
        dest="checks",
        action="append",
        default=[],
        help=(
            "Run a specific check. Repeatable. "
            f"Pure checks: {PURE_CHECKS}. LLM checks: {LLM_CHECKS}. "
            "Default: all pure checks."
        ),
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Also run LLM-assisted checks (requires Ollama).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model for LLM checks. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-create missing concept stubs, or print re-synthesis commands for staleness.",
    )
    parser.add_argument(
        "--contradictions",
        action="store_true",
        help="Run Phase 2B cross-topic contradiction detection only unless combined with other checks.",
    )
    parser.add_argument(
        "--staleness",
        action="store_true",
        help="Run Phase 2B staleness detection only unless combined with other checks.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all pure, LLM-assisted, and Phase 2B checks.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="For --contradictions, show candidates dated on or after YYYY-MM-DD.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="For --staleness, require newer sources to be at least this many days newer.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="File the report as an artifact in outputs/reports/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing report for today.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the report to stdout without filing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        root=ROOT,
        checks=args.checks,
        use_llm=args.llm,
        model=args.model,
        report=args.report,
        force=args.force,
        dry_run=args.dry_run,
        fix=args.fix,
        cross_contradictions=args.contradictions,
        staleness=args.staleness,
        all_checks=args.all,
        since=args.since,
        days=args.days,
    )


if __name__ == "__main__":
    sys.exit(main())

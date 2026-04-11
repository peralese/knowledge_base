"""Phase 9 Linting and Health Checks: scan the wiki for structural problems.

Runs a suite of health checks over compiled and raw notes, then optionally
files a report in outputs/reports/.

Pure-Python checks (always run):
  wikilinks  — find [[wikilinks]] in compiled notes that point to missing files
  orphans    — find raw notes not referenced by any compiled note

LLM-assisted checks (require --llm flag and a running Ollama instance):
  coverage   — ask the model to identify topic gaps based on the wiki index

Usage:
    # Run pure checks, print report to terminal
    python3 scripts/lint.py

    # Also run LLM coverage check
    python3 scripts/lint.py --llm

    # File the report as an artifact in outputs/reports/
    python3 scripts/lint.py --report

    # Run only a specific check
    python3 scripts/lint.py --check wikilinks

    # Preview without filing
    python3 scripts/lint.py --llm --report --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"
OLLAMA_BASE_URL = "http://localhost:11434"

PURE_CHECKS = ["wikilinks", "orphans"]
LLM_CHECKS = ["coverage"]
ALL_CHECKS = PURE_CHECKS + LLM_CHECKS

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]+)?\]\]")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class LintIssue:
    check: str        # "wikilinks" | "orphans" | "coverage"
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


# ---------------------------------------------------------------------------
# LLM-assisted checks
# ---------------------------------------------------------------------------

def _stream_ollama(prompt: str, model: str) -> str:
    """Stream a response from Ollama, return the full text."""
    payload = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[str] = []
    with urllib.request.urlopen(req) as resp:
        for raw_line in resp:
            line = raw_line.strip()
            if not line:
                continue
            data = json.loads(line)
            token = data.get("response", "")
            if token:
                print(token, end="", flush=True)
                chunks.append(token)
            if data.get("done"):
                break
    print()
    return "".join(chunks)


def _check_model_available(model: str) -> None:
    req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except URLError as exc:
        raise ConnectionError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. Is it running?\n"
            "  Start with: ollama serve"
        ) from exc
    available = [m.get("name", "") for m in data.get("models", [])]
    if model not in available:
        raise ValueError(
            f"Model '{model}' is not available in Ollama.\n"
            f"  Available: {', '.join(available) or '(none)'}\n"
            f"  Pull with: ollama pull {model}"
        )


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
        response = _stream_ollama(prompt, model)
    except URLError as exc:
        return [LintIssue(
            check="coverage",
            severity="info",
            message=f"LLM call failed: {exc}",
        )]

    # Each numbered line becomes one info issue
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
        # Group by check
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
) -> int:
    today = date.today().isoformat()

    # Determine which checks to run
    checks_to_run = checks if checks else PURE_CHECKS
    if use_llm:
        for c in LLM_CHECKS:
            if c not in checks_to_run:
                checks_to_run = checks_to_run + [c]

    # Validate LLM availability before running
    if use_llm and any(c in LLM_CHECKS for c in checks_to_run):
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
        print(f"wikilinks     : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "orphans" in checks_to_run:
        found = check_orphaned_raw_notes(root)
        issues.extend(found)
        print(f"orphans       : {len(found)} issue{'s' if len(found) != 1 else ''}")

    if "coverage" in checks_to_run:
        found = check_coverage_gaps(root, model)
        issues.extend(found)
        print(f"coverage      : {len(found)} gap{'s' if len(found) != 1 else ''} identified")

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
        description="Phase 9 Linting: scan the wiki for structural problems."
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
    )


if __name__ == "__main__":
    sys.exit(main())

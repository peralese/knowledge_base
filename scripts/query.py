"""Phase 7 Q&A Workflow: ask a natural language question against the compiled wiki.

Loads all compiled notes into context, sends the question to a local Ollama model,
streams the answer to the terminal, and files the result in outputs/answers/.

Usage:
    python3 scripts/query.py --question "What are the security tradeoffs between EKS and Fargate?"

    # Save with a custom title
    python3 scripts/query.py \\
        --question "What are the security tradeoffs between EKS and Fargate?" \\
        --title "EKS vs Fargate Security Tradeoffs"

    # Use a different model
    python3 scripts/query.py \\
        --question "How does Gemma 4 compare to other local models?" \\
        --model qwen2.5:7b

    # Preview the prompt without calling the model
    python3 scripts/query.py \\
        --question "What is OpenClaw?" \\
        --dry-run

    # Use BM25 to select only the top 5 most relevant notes (Phase 10)
    python3 scripts/query.py \\
        --question "What are Fargate security best practices?" \\
        --top-n 5
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"
OLLAMA_BASE_URL = "http://localhost:11434"

COMPILED_DIRS = [
    ROOT / "compiled" / "topics",
    ROOT / "compiled" / "concepts",
    ROOT / "compiled" / "source_summaries",
]

ANSWERS_DIR = ROOT / "outputs" / "answers"

# Rough token budget: qwen2.5:14b has a 128k context window.
# Reserve ~4k for the question + instructions + answer headroom.
MAX_CONTEXT_CHARS = 120_000


# ---------------------------------------------------------------------------
# Compiled note loading
# ---------------------------------------------------------------------------

@dataclass
class CompiledNote:
    path: Path
    title: str
    body: str

    @property
    def stem(self) -> str:
        return self.path.stem


def _parse_frontmatter_title(text: str) -> str:
    """Extract title from YAML frontmatter if present."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return ""
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return ""
    for line in parts[0].splitlines():
        m = re.match(r'^title:\s*"?([^"]+)"?\s*$', line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block, return body only."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return normalized.strip()
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return normalized.strip()
    return parts[1].strip()


def load_compiled_notes(root: Path) -> list[CompiledNote]:
    """Load all compiled notes from compiled/ subdirectories."""
    notes: list[CompiledNote] = []
    dirs = [
        root / "compiled" / "topics",
        root / "compiled" / "concepts",
        root / "compiled" / "source_summaries",
    ]
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            title = _parse_frontmatter_title(text) or path.stem.replace("-", " ").title()
            body = _strip_frontmatter(text)
            notes.append(CompiledNote(path=path, title=title, body=body))
    return notes


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_query_prompt(question: str, notes: list[CompiledNote]) -> tuple[str, list[CompiledNote]]:
    """Build the prompt from the question and compiled notes.

    Includes as many notes as fit within MAX_CONTEXT_CHARS. Returns the
    prompt and the list of notes actually included.
    """
    instructions = (
        "You are a knowledge base assistant. Answer the question below using only "
        "the compiled notes provided. Be specific and cite which notes support each "
        "claim. If the notes do not contain enough information to answer fully, say so "
        "clearly rather than inventing details.\n\n"
        "Format your answer in markdown with:\n"
        "- A brief direct answer at the top\n"
        "- Supporting details with note citations\n"
        "- A 'Sources Used' section at the end listing the note titles you drew from\n\n"
    )

    question_block = f"## Question\n\n{question.strip()}\n\n"
    header = instructions + question_block + "## Compiled Knowledge Base\n\n"

    budget = MAX_CONTEXT_CHARS - len(header)
    included: list[CompiledNote] = []
    blocks: list[str] = []

    for note in notes:
        block = f"### {note.title} ({note.stem})\n\n{note.body}\n\n---\n\n"
        if len("".join(blocks)) + len(block) > budget:
            break
        blocks.append(block)
        included.append(note)

    prompt = header + "".join(blocks) + "## Answer\n\n"
    return prompt, included


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def _check_model_available(model: str) -> None:
    """Raise a clear error if the requested model is not pulled in Ollama."""
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
        available_str = ", ".join(available) if available else "(none pulled)"
        raise ValueError(
            f"Model '{model}' is not available in Ollama.\n"
            f"  Available: {available_str}\n"
            f"  Pull with: ollama pull {model}"
        )


def call_ollama(prompt: str, model: str) -> str:
    """Stream a response from Ollama, printing tokens as they arrive."""
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


# ---------------------------------------------------------------------------
# Answer filing
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "answer"


def build_answer_frontmatter(
    title: str,
    question: str,
    notes_used: list[CompiledNote],
    model: str,
    today: str,
) -> str:
    def fmt_list(items: list[str]) -> str:
        if not items:
            return "[]"
        lines = "\n".join(f'  - "{item}"' for item in items)
        return f"\n{lines}"

    note_stems = [n.stem for n in notes_used]
    return (
        "---\n"
        f'title: "{title}"\n'
        f'output_type: "answer"\n'
        f'generated_from_query: "{question.strip().replace(chr(34), chr(39))}"\n'
        f'generated_on: "{today}"\n'
        f"compiled_notes_used: {fmt_list(note_stems)}\n"
        f'generation_method: "ollama_local"\n'
        f'model: "{model}"\n'
        "---"
    )


def file_answer(
    question: str,
    answer: str,
    notes_used: list[CompiledNote],
    title: str,
    model: str,
    force: bool,
    root: Path,
) -> Path:
    """Write the answer as a durable artifact in outputs/answers/."""
    today = date.today().isoformat()
    slug = slugify(title)
    dest = root / "outputs" / "answers" / f"{slug}.md"

    if dest.exists() and not force:
        raise FileExistsError(
            f"Answer already exists: {dest.relative_to(root)}. Use --force to overwrite."
        )

    frontmatter = build_answer_frontmatter(
        title=title,
        question=question,
        notes_used=notes_used,
        model=model,
        today=today,
    )

    note_links = "\n".join(f"- [[{n.stem}]]" for n in notes_used)
    body = (
        f"# Question\n\n{question.strip()}\n\n"
        f"# Answer\n\n{answer.strip()}\n\n"
        f"# Sources Used\n\n{note_links}\n\n"
        f"# Lineage\n\n"
        f"- Generated on: {today}\n"
        f"- Model: {model}\n"
        f"- Notes in context: {len(notes_used)}\n"
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"{frontmatter}\n\n{body}", encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def _bm25_select_notes(question: str, root: Path, top_n: int) -> list[CompiledNote]:
    """Use BM25 to select the top_n most relevant compiled notes for the question."""
    sys.path.insert(0, str(Path(__file__).parent))
    from search import load_documents, build_index, search as bm25_search  # noqa: PLC0415

    docs = load_documents(root, include_raw=False)
    if not docs:
        return []

    index = build_index(docs)
    results = bm25_search(question, index, top_n=top_n)

    # Convert search Documents back to CompiledNotes
    notes: list[CompiledNote] = []
    for r in results:
        text = r.document.path.read_text(encoding="utf-8", errors="replace")
        title = _parse_frontmatter_title(text) or r.document.path.stem.replace("-", " ").title()
        body = _strip_frontmatter(text)
        notes.append(CompiledNote(path=r.document.path, title=title, body=body))
    return notes


def run(
    question: str,
    title: str,
    model: str,
    force: bool,
    dry_run: bool,
    root: Path,
    top_n: int = 0,
) -> int:
    all_notes = load_compiled_notes(root)
    if not all_notes:
        print("Error: no compiled notes found. Run compile_notes.py first.", file=sys.stderr)
        return 1

    if top_n > 0:
        notes = _bm25_select_notes(question, root, top_n)
        retrieval_label = f"BM25 top-{top_n} of {len(all_notes)} notes → {len(notes)} selected"
    else:
        notes = all_notes
        retrieval_label = f"full context ({len(notes)} notes)"

    prompt, included = build_query_prompt(question, notes)

    print(f"Model         : {model}")
    print(f"Retrieval     : {retrieval_label}")
    print(f"Notes in ctx  : {len(included)}")
    print(f"Prompt size   : {len(prompt):,} chars")
    print(f"Question      : {question.strip()}")
    print("-" * 60)

    if dry_run:
        print("\n--- PROMPT PREVIEW ---\n")
        print(prompt[:3000] + ("\n... [truncated]" if len(prompt) > 3000 else ""))
        return 0

    try:
        _check_model_available(model)
    except (ConnectionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        answer = call_ollama(prompt, model)
    except URLError as exc:
        print(f"Error: Ollama request failed: {exc}", file=sys.stderr)
        return 1

    print("-" * 60)

    resolved_title = title or _derive_title(question)
    try:
        dest = file_answer(
            question=question,
            answer=answer,
            notes_used=included,
            title=resolved_title,
            model=model,
            force=force,
            root=root,
        )
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Answer filed  : {dest.relative_to(root)}")
    return 0


def _derive_title(question: str) -> str:
    """Turn the question into a reasonable title (first 60 chars, trimmed cleanly)."""
    stripped = question.strip().rstrip("?").strip()
    if len(stripped) <= 60:
        return stripped
    # Trim to last word boundary before 60 chars
    cut = stripped[:60]
    last_space = cut.rfind(" ")
    return cut[:last_space] if last_space > 20 else cut


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 7 Q&A: ask a question against the compiled knowledge base."
    )
    parser.add_argument(
        "--question", "-q",
        required=True,
        help="The question to ask.",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Title for the filed answer artifact. Derived from the question if omitted.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing answer artifact.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompt that would be sent without calling the model.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=0,
        dest="top_n",
        help=(
            "Use BM25 search to select only the top N most relevant notes as context. "
            "Default: 0 (include all notes up to the token budget)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        question=args.question,
        title=args.title,
        model=args.model,
        force=args.force,
        dry_run=args.dry_run,
        root=ROOT,
        top_n=args.top_n,
    )


if __name__ == "__main__":
    sys.exit(main())

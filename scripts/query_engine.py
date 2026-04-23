"""Shared query engine for CLI and dashboard Q&A."""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"
OLLAMA_BASE_URL = "http://localhost:11434"
MAX_CONTEXT_CHARS = 120_000


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized.strip()
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return {}, normalized.strip()

    fm_text = normalized[4:end]
    body = normalized[end + 5:].strip()
    data: dict[str, object] = {}
    current_key = ""
    for raw_line in fm_text.splitlines():
        stripped = raw_line.strip()
        if current_key and stripped.startswith("- "):
            values = data.setdefault(current_key, [])
            if isinstance(values, list):
                values.append(stripped[2:].strip().strip('"').strip("'"))
            continue
        current_key = ""
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", stripped)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if value == "":
            data[key] = []
            current_key = key
        elif value.startswith("[") and value.endswith("]"):
            data[key] = [
                item.strip().strip('"').strip("'")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        else:
            data[key] = value.strip('"').strip("'")
    return data, body


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "answer"


def _relative(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _wiki_targets(text: str) -> list[str]:
    seen: set[str] = set()
    targets: list[str] = []
    for match in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", text):
        target = match.group(1).strip()
        if target and target not in seen:
            targets.append(target)
            seen.add(target)
    return targets


def _source_summary_path(target: str, project_root: Path) -> Path | None:
    cleaned = target.strip()
    candidates = [
        project_root / cleaned,
        project_root / "compiled" / "source_summaries" / cleaned,
        project_root / "compiled" / "source_summaries" / f"{cleaned}.md",
    ]
    if cleaned.endswith(".md"):
        candidates.append(project_root / "compiled" / "source_summaries" / Path(cleaned).name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _topic_slugs_from_index(index_text: str) -> list[str]:
    slugs: list[str] = []
    seen: set[str] = set()
    for target in _wiki_targets(index_text):
        slug = Path(target).stem
        if slug and slug not in seen:
            slugs.append(slug)
            seen.add(slug)
    return slugs


def load_context(topic_slug: str | None, project_root: Path) -> tuple[str, list[str]]:
    """Load wiki context for a query.

    Returns (context_text, source_paths_used). Topic-scoped queries load the topic
    note and linked source summaries. Full-wiki queries load topic notes only.
    """
    notes: list[tuple[Path, str]] = []

    if topic_slug:
        topic_path = project_root / "compiled" / "topics" / f"{topic_slug}.md"
        if not topic_path.exists():
            return "", []
        topic_text = topic_path.read_text(encoding="utf-8", errors="replace")
        notes.append((topic_path, topic_text))

        linked_paths: list[Path] = []
        for target in _wiki_targets(topic_text):
            path = _source_summary_path(target, project_root)
            if path and path not in linked_paths:
                linked_paths.append(path)

        fm, _ = _split_frontmatter(topic_text)
        compiled_from = fm.get("compiled_from", [])
        if isinstance(compiled_from, str):
            compiled_from = [compiled_from]
        if isinstance(compiled_from, list):
            for stem in compiled_from:
                path = _source_summary_path(str(stem), project_root)
                if path and path not in linked_paths:
                    linked_paths.append(path)

        for path in linked_paths:
            notes.append((path, path.read_text(encoding="utf-8", errors="replace")))
    else:
        topics_dir = project_root / "compiled" / "topics"
        index_path = project_root / "compiled" / "index.md"
        topic_paths: list[Path] = []
        if index_path.exists():
            index_text = index_path.read_text(encoding="utf-8", errors="replace")
            for slug in _topic_slugs_from_index(index_text):
                path = topics_dir / f"{slug}.md"
                if path.exists() and path not in topic_paths:
                    topic_paths.append(path)
        if not topic_paths and topics_dir.exists():
            topic_paths = sorted(topics_dir.glob("*.md"))
        for path in topic_paths:
            notes.append((path, path.read_text(encoding="utf-8", errors="replace")))

    blocks: list[str] = []
    used_paths: list[str] = []
    total = 0
    for path, text in notes:
        fm, body = _split_frontmatter(text)
        title = str(fm.get("title") or path.stem.replace("-", " ").title())
        rel = _relative(path, project_root)
        block = f"### {title}\nSource: {rel}\n\n{body}\n\n---\n\n"
        if total + len(block) > MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        used_paths.append(rel)
        total += len(block)

    return "".join(blocks), used_paths


def build_query_prompt(question: str, context: str) -> str:
    """Build the full prompt string for Ollama."""
    return (
        "You are a research assistant with access to a personal knowledge base.\n"
        "Answer the following question based only on the provided context.\n"
        "Cite the specific notes you drew from in your answer.\n"
        "If the context does not contain enough information to answer, say so.\n\n"
        f"Context:\n{context.strip()}\n\n"
        f"Question: {question.strip()}\n"
    )


def parse_sources_from_response(response: str, context_paths: list[str]) -> list[str]:
    """Extract cited source names from Ollama's response."""
    cited: list[str] = []
    response_lower = response.lower()
    wiki_cites = {_slugify(target) for target in _wiki_targets(response)}
    for path_str in context_paths:
        stem = Path(path_str).stem
        if stem.lower() in response_lower or _slugify(stem) in wiki_cites:
            cited.append(stem)
    return cited or [Path(p).stem for p in context_paths]


def call_ollama(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 120) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return str(data.get("response", ""))


def save_answer(
    question: str,
    answer: str,
    sources: list[str],
    topic_slug: str | None,
    outputs_dir: Path,
) -> Path:
    """Save answer to outputs/answers/ and return the path."""
    today = date.today().isoformat()
    title = question.strip()
    slug = _slugify(title[:60])
    answers_dir = outputs_dir / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)
    dest = answers_dir / f"{today}-{slug}.md"

    source_paths = [
        source if source.endswith(".md") or "/" in source else f"compiled/source_summaries/{source}.md"
        for source in sources
    ]

    source_lines = "\n".join(f"  - {source}" for source in source_paths)
    topic = topic_slug or "all"
    frontmatter = (
        "---\n"
        f'question: "{question.strip().replace(chr(34), chr(39))}"\n'
        f"topic: {topic}\n"
        f"date: {today}\n"
        "feedback: null\n"
        "feedback_note: null\n"
        "feedback_at: null\n"
        "sources:\n"
        f"{source_lines if source_lines else '  []'}\n"
        "---"
    )
    body = (
        f"# {title}\n\n"
        f"{answer.strip()}\n\n"
        "---\n"
        f"*Queried on {today} against topic: {topic}*\n"
    )
    dest.write_text(f"{frontmatter}\n\n{body}", encoding="utf-8")
    return dest


def recent_answers(outputs_dir: Path, limit: int = 5) -> list[dict[str, object]]:
    answers_dir = outputs_dir / "answers"
    if not answers_dir.exists():
        return []
    rows: list[dict[str, object]] = []
    for path in answers_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = _split_frontmatter(text)
        feedback = str(fm.get("feedback", ""))
        if feedback == "null":
            feedback = ""
        rows.append({
            "filename": path.name,
            "question": str(fm.get("question", path.stem)),
            "topic": str(fm.get("topic", "all")),
            "date": str(fm.get("date", "")),
            "feedback": feedback,
            "path": f"outputs/answers/{path.name}",
            "_mtime": path.stat().st_mtime,
        })
    rows.sort(key=lambda row: (str(row["date"]), float(row["_mtime"])), reverse=True)
    return [{k: v for k, v in row.items() if k != "_mtime"} for row in rows[:limit]]


def read_answer(outputs_dir: Path, filename: str) -> dict[str, object]:
    if Path(filename).name != filename or not filename.endswith(".md"):
        raise FileNotFoundError(filename)
    path = outputs_dir / "answers" / filename
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _split_frontmatter(text)
    sources = fm.get("sources", [])
    if not isinstance(sources, list):
        sources = [str(sources)]
    feedback = str(fm.get("feedback", ""))
    if feedback == "null":
        feedback = ""
    feedback_note = str(fm.get("feedback_note", ""))
    if feedback_note == "null":
        feedback_note = ""
    return {
        "question": str(fm.get("question", "")),
        "topic": str(fm.get("topic", "all")),
        "date": str(fm.get("date", "")),
        "answer": body,
        "sources": [Path(str(source)).stem for source in sources],
        "feedback": feedback,
        "feedback_note": feedback_note,
    }

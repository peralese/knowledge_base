"""Phase 11 — Ingestion & Review Dashboard.

Lightweight FastAPI backend serving a single-page dashboard at localhost:7842.

Endpoints:
    GET  /                          Serve dashboard/index.html
    GET  /api/topics                List topics from topic-registry.json
    POST /api/topics                Add a new topic to the registry
    POST /api/ingest/url            Download a URL and stage it to inbox/
    POST /api/ingest/file           Accept a file upload and stage it to inbox/
    GET  /api/queue                 Return unreviewed synthesized items
    POST /api/queue/{id}/approve    Approve a queue item
    POST /api/queue/{id}/reject     Reject a queue item
    GET  /api/queue/{id}/preview    Return compiled note markdown for inline preview

Usage:
    python3 dashboard.py
    python3 dashboard.py --port 8080
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

import httpx
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = ROOT / "dashboard"
TOPIC_REGISTRY_PATH = ROOT / "metadata" / "topic-registry.json"
TMP_DIR = ROOT / "tmp"
ARTICLES_DIR = ROOT / "raw" / "articles"

# ---------------------------------------------------------------------------
# Import reusable pipeline modules
# ---------------------------------------------------------------------------

sys.path.insert(0, str(ROOT / "scripts"))

from ingest import html_to_text, normalize_text  # noqa: E402
from review import (  # noqa: E402
    _find_compiled_note,
    _patch_note_approved,
    approve,
    load_queue,
    reject,
    save_queue,
)
from query_engine import (  # noqa: E402
    DEFAULT_MODEL as QUERY_MODEL,
    build_query_prompt,
    call_ollama as call_query_ollama,
    load_context,
    parse_sources_from_response,
    read_answer,
    recent_answers,
    save_answer,
)
from resynthesize_topic import (  # noqa: E402
    DEFAULT_MODEL as RESYNTH_MODEL,
    InsufficientSourcesError,
    OllamaUnavailableError,
    ResynthesisError,
    TopicNotFoundError,
    resynthesize_topic,
    topic_status,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="KB Dashboard", version="1.0.0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_registry() -> dict:
    if not TOPIC_REGISTRY_PATH.exists():
        return {"topics": []}
    try:
        return json.loads(TOPIC_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"topics": []}


def _save_registry(data: dict) -> None:
    TOPIC_REGISTRY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _kebab(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "new-topic"


SOURCE_TYPE_OPTIONS = ["article", "blog", "paper", "documentation", "repo", "podcast", "video"]

_TITLE_SUFFIX_SEPS = [" | ", " — ", " - ", " · "]


def slugify(title: str) -> str:
    """Convert a title to a URL-safe slug. Consistent: same title always produces same slug."""
    slug = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "article"


def _extract_page_title(html: str) -> str | None:
    """Extract the best available title from an HTML string. Returns None if not found."""
    soup = BeautifulSoup(html, "html.parser")

    # og:title (most reliable)
    og = soup.find("meta", property="og:title")
    if og and og.get("content", "").strip():
        title = og["content"].strip()
    else:
        # twitter:title
        tw = soup.find("meta", attrs={"name": "twitter:title"})
        if tw and tw.get("content", "").strip():
            title = tw["content"].strip()
        else:
            tag = soup.find("title")
            title = tag.get_text().strip() if tag else None

    if not title:
        return None

    # Strip common site-name suffixes — last occurrence only
    for sep in _TITLE_SUFFIX_SEPS:
        idx = title.rfind(sep)
        if idx != -1:
            title = title[:idx].strip()
            break

    return title or None


def _inject_optional_frontmatter(path: Path, fields: dict) -> None:
    """Append optional key-value pairs into an existing YAML frontmatter block.

    Only writes keys whose values are non-empty. Skips empty strings, empty lists,
    and None. Must be called after the file has been staged (frontmatter block exists).
    """
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return
    end = text.find("\n---\n", 4)
    if end == -1:
        return

    additions: list[str] = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            # Inline YAML flow sequence: ["a", "b"]
            items_str = ", ".join(f'"{v}"' for v in value)
            additions.append(f"{key}: [{items_str}]")
        elif isinstance(value, str) and value.strip():
            safe = value.strip().replace('"', "'")
            additions.append(f'{key}: "{safe}"')

    if not additions:
        return

    body_after = text[end + 5:]  # text after the closing \n---\n
    fm_content = text[4:end]     # existing frontmatter lines (no leading ---)
    new_text = "---\n" + fm_content + "\n" + "\n".join(additions) + "\n---\n" + body_after
    path.write_text(new_text, encoding="utf-8")


def _parse_tags(raw: str) -> list[str]:
    """Split a comma-separated tag string into a clean list. Returns [] if blank."""
    return [t.strip() for t in raw.split(",") if t.strip()] if raw.strip() else []


def _extract_frontmatter_tags(text: str) -> list[str]:
    """Extract tags from a small YAML frontmatter subset."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return []
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return []

    tags: list[str] = []
    lines = normalized[4:end].splitlines()
    in_tags = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if in_tags:
            if stripped.startswith("- "):
                tag = stripped[2:].strip().strip('"').strip("'")
                if tag:
                    tags.append(tag)
                continue
            if raw_line and not raw_line.startswith((" ", "\t")):
                in_tags = False

        if stripped == "tags:":
            in_tags = True
            continue
        if stripped.startswith("tags:"):
            raw_value = stripped.split(":", 1)[1].strip()
            if raw_value.startswith("[") and raw_value.endswith("]"):
                for tag in raw_value[1:-1].split(","):
                    cleaned = tag.strip().strip('"').strip("'")
                    if cleaned:
                        tags.append(cleaned)
            elif raw_value and raw_value != "[]":
                cleaned = raw_value.strip().strip('"').strip("'")
                if cleaned:
                    tags.append(cleaned)
    return tags


def _used_tags() -> list[str]:
    search_dirs = [
        ROOT / "raw" / "articles",
        ROOT / "compiled" / "source_summaries",
        ROOT / "compiled" / "topics",
    ]
    tags: set[str] = set()
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            try:
                tags.update(_extract_frontmatter_tags(path.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return sorted(tags, key=str.lower)


def _yaml_scalar(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ").strip()


def _render_frontmatter(frontmatter: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {_yaml_scalar(str(item))}" for item in value)
            continue
        lines.append(f"{key}: {_yaml_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def _write_raw_article(
    *,
    title: str,
    text: str,
    origin: str,
    source_type: str = "article",
    author: str = "",
    date_published: str = "",
    tags: list[str] | None = None,
    language: str = "",
    license_: str = "",
    canonical_url: str = "",
    topic_slug: str = "",
) -> Path:
    slug = slugify(title)
    destination = ARTICLES_DIR / f"{slug}.md"
    if destination.exists():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict",
                "message": "An article with this title already exists.",
                "existing_path": str(destination.relative_to(ROOT)),
            },
        )

    source_id = f"DASH-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    frontmatter: dict[str, object] = {
        "title": title,
        "source_type": source_type.strip() or "article",
        "origin": origin,
        "date_ingested": str(date.today()),
        "status": "raw",
        "source_id": source_id,
    }
    if canonical_url.strip():
        frontmatter["canonical_url"] = canonical_url.strip()
    if topic_slug.strip():
        frontmatter["topics"] = [topic_slug.strip()]
    if author.strip():
        frontmatter["author"] = author.strip()
    if date_published.strip():
        frontmatter["date_published"] = date_published.strip()
    if tags:
        frontmatter["tags"] = tags
    if language.strip():
        frontmatter["language"] = language.strip()
    if license_.strip():
        frontmatter["license"] = license_.strip()

    print(f"frontmatter: {frontmatter}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    body = normalize_text(text) or "[no content provided]"
    destination.write_text(f"{_render_frontmatter(frontmatter)}\n\n{body}\n", encoding="utf-8")
    return destination


def _ingest_via_inbox(
    *,
    title: str,
    text: str,
    origin: str,
    source_type: str = "article",
    author: str = "",
    date_published: str = "",
    tags: list[str] | None = None,
    language: str = "",
    license_: str = "",
    canonical_url: str = "",
    topic_slug: str = "",
) -> Path:
    slug = slugify(title)
    destination = ARTICLES_DIR / f"{slug}.md"
    if destination.exists():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict",
                "message": "An article with this title already exists.",
                "existing_path": str(destination.relative_to(ROOT)),
            },
        )

    staged_dir = ROOT / "raw" / "inbox" / "browser"
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged_path = staged_dir / f"{slug}.md"
    if staged_path.exists():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict",
                "message": "A staged article with this title already exists.",
                "existing_path": str(staged_path.relative_to(ROOT)),
            },
        )

    frontmatter: dict[str, object] = {
        "title": title,
        "source_type": source_type.strip() or "article",
        "origin": origin,
    }
    if canonical_url.strip():
        frontmatter["canonical_url"] = canonical_url.strip()
    if topic_slug.strip():
        frontmatter["topics"] = [topic_slug.strip()]
    if author.strip():
        frontmatter["author"] = author.strip()
    if date_published.strip():
        frontmatter["date_published"] = date_published.strip()
    if tags:
        frontmatter["tags"] = tags
    if language.strip():
        frontmatter["language"] = language.strip()
    if license_.strip():
        frontmatter["license"] = license_.strip()

    print(f"frontmatter: {frontmatter}")

    body = normalize_text(text) or "[no content provided]"
    staged_path.write_text(f"{_render_frontmatter(frontmatter)}\n\n{body}\n", encoding="utf-8")

    import inbox_watcher  # noqa: PLC0415

    original_root = inbox_watcher.ROOT
    original_queue_path = inbox_watcher.REVIEW_QUEUE_PATH
    original_queue_report_path = inbox_watcher.REVIEW_QUEUE_REPORT_PATH
    try:
        inbox_watcher.ROOT = ROOT
        inbox_watcher.REVIEW_QUEUE_PATH = ROOT / "metadata" / "review-queue.json"
        inbox_watcher.REVIEW_QUEUE_REPORT_PATH = ROOT / "metadata" / "review-queue.md"
        outcome = inbox_watcher.ingest_file(staged_path, source_type.strip() or "article")
    finally:
        inbox_watcher.ROOT = original_root
        inbox_watcher.REVIEW_QUEUE_PATH = original_queue_path
        inbox_watcher.REVIEW_QUEUE_REPORT_PATH = original_queue_report_path

    if not outcome.output_path:
        raise HTTPException(status_code=500, detail="Failed to ingest staged article.")
    return outcome.output_path


def _reviewable_unscored_or_low(queue: list[dict]) -> list[dict]:
    """Items that are synthesized, not yet reviewed, and below auto-approve threshold."""
    return [
        e for e in queue
        if e.get("review_status") == "synthesized"
        and e.get("review_action") not in ("approved", "rejected")
    ]


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

@app.get("/api/fetch-title")
def fetch_title(url: str):
    """Fetch a URL and return the best title found in the HTML. Always returns HTTP 200."""
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (compatible; KBDashboard/1.0)"},
        )
        response.raise_for_status()
        title = _extract_page_title(response.text)
        return {"title": title}
    except Exception:
        return {"title": None}


@app.get("/")
def serve_index():
    index = DASHBOARD_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="dashboard/index.html not found")
    return FileResponse(index)


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

@app.get("/api/topics")
def get_topics():
    registry = _load_registry()
    topics = [
        {"slug": t.get("slug", ""), "display_name": t.get("title", t.get("slug", ""))}
        for t in registry.get("topics", [])
    ]
    return {"topics": topics}


@app.get("/api/topics/{slug}/status")
def get_topic_status(slug: str):
    try:
        return topic_status(slug, ROOT)
    except TopicNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/tags")
def get_tags():
    return {"tags": _used_tags()}


class NewTopicRequest(BaseModel):
    display_name: str
    slug: Optional[str] = None
    aliases: list[str] = []
    keywords: list[str] = []


@app.post("/api/topics", status_code=201)
def add_topic(body: NewTopicRequest):
    registry = _load_registry()
    topics = registry.setdefault("topics", [])

    slug = _kebab(body.slug or body.display_name)
    existing_slugs = {t.get("slug") for t in topics}
    if slug in existing_slugs:
        raise HTTPException(status_code=409, detail=f"Topic slug '{slug}' already exists.")

    new_topic: dict = {
        "slug": slug,
        "title": body.display_name.strip(),
        "aliases": body.aliases,
    }
    if body.keywords:
        new_topic["keywords"] = body.keywords

    topics.append(new_topic)
    _save_registry(registry)
    return {"topic": {"slug": slug, "display_name": body.display_name.strip()}}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str
    topic_slug: Optional[str] = None


@app.post("/api/query")
def query_wiki(body: QueryRequest):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required.")

    topic_slug = body.topic_slug.strip() if body.topic_slug else None
    context, context_paths = load_context(topic_slug, ROOT)
    if not context:
        raise HTTPException(status_code=404, detail="No compiled context found for this query.")

    prompt = build_query_prompt(question, context)
    try:
        answer = call_query_ollama(prompt, model=QUERY_MODEL, timeout=120)
    except (URLError, TimeoutError, OSError, ConnectionError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "ollama_unavailable",
                "message": "Ollama is not responding. Ensure it is running with: ollama serve",
            },
        )

    cited = parse_sources_from_response(answer, context_paths)
    used_paths = [path for path in context_paths if Path(path).stem in cited]
    if not used_paths:
        used_paths = context_paths
    saved = save_answer(question, answer, used_paths, topic_slug, ROOT / "outputs")
    return {
        "answer": answer,
        "sources": [Path(path).stem for path in used_paths],
        "saved_path": str(saved.relative_to(ROOT)),
    }


@app.get("/api/answers/recent")
def get_recent_answers():
    return {"answers": recent_answers(ROOT / "outputs", limit=5)}


@app.get("/api/answers/{filename}")
def get_answer(filename: str):
    try:
        return read_answer(ROOT / "outputs", filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Answer not found.")


class ResynthesizeRequest(BaseModel):
    topic_slug: str


@app.post("/api/resynthesize")
def post_resynthesize(body: ResynthesizeRequest):
    topic_slug = body.topic_slug.strip()
    if not topic_slug:
        raise HTTPException(status_code=400, detail="topic_slug is required.")
    try:
        result = resynthesize_topic(topic_slug, model=RESYNTH_MODEL, root=ROOT)
    except InsufficientSourcesError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "insufficient_sources", "message": str(exc)},
        )
    except OllamaUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "ollama_unavailable", "message": str(exc)},
        )
    except TopicNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={"error": "topic_not_found", "message": str(exc)},
        )
    except ResynthesisError as exc:
        return JSONResponse(
            status_code=500,
            content={"error": exc.error_code, "message": str(exc)},
        )
    return {
        "status": "ok",
        "topic_slug": result.topic_slug,
        "synthesis_version": result.synthesis_version,
        "sources_used": result.sources_used,
        "committed": result.committed,
    }


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

class IngestURLRequest(BaseModel):
    url: str
    title: str = ""
    topic_slug: str = ""
    notes: str = ""
    source_type: str = "article"
    author: Optional[str] = None
    date_published: Optional[str] = None
    tags: list[str] = []
    language: Optional[str] = None
    license: Optional[str] = None


@app.post("/api/ingest/url")
def ingest_url(body: IngestURLRequest):
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required.")

    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required.")

    # Download the page
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {exc}")

    content_type = response.headers.get("content-type", "")
    raw_content = response.text

    # Strip HTML if needed
    if "html" in content_type or raw_content.lstrip().startswith("<"):
        text = normalize_text(html_to_text(raw_content))
    else:
        text = normalize_text(raw_content)

    # Inject notes and topic into text
    if body.notes.strip():
        text = f"<!-- notes: {body.notes.strip()} -->\n\n{text}"
    if body.topic_slug.strip():
        text = f"<!-- topic_slug: {body.topic_slug.strip()} -->\n\n{text}"

    destination = _ingest_via_inbox(
        title=title,
        text=text,
        origin="url",
        source_type=body.source_type or "article",
        author=body.author or "",
        date_published=body.date_published or "",
        tags=body.tags or [],
        language=body.language or "",
        license_=body.license or "",
        canonical_url=url,
        topic_slug=body.topic_slug,
    )

    return {"status": "queued", "filename": destination.name}


@app.post("/api/ingest/file")
def ingest_file(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    topic_slug: str = Form(default=""),
    notes: str = Form(default=""),
    source_type: str = Form(default="article"),
    author: str = Form(default=""),
    canonical_url: str = Form(default=""),
    date_published: str = Form(default=""),
    tags: str = Form(default=""),
    language: str = Form(default=""),
    license: str = Form(default=""),
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="title is required.")

    suffix = Path(file.filename or "upload").suffix.lower()
    allowed = {".pdf", ".html", ".htm", ".md"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(allowed))}",
        )

    raw_bytes = file.file.read()
    if suffix in {".html", ".htm"}:
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        text = normalize_text(html_to_text(raw_text))
    elif suffix == ".pdf":
        text = f"PDF upload: {file.filename or 'upload.pdf'}"
    else:
        text = raw_bytes.decode("utf-8", errors="replace")

    if notes.strip():
        text = f"<!-- notes: {notes.strip()} -->\n\n{text}"
    if topic_slug.strip():
        text = f"<!-- topic_slug: {topic_slug.strip()} -->\n\n{text}"

    destination = _ingest_via_inbox(
        title=title.strip(),
        text=text,
        origin="file",
        source_type=source_type,
        author=author,
        canonical_url=canonical_url,
        date_published=date_published,
        tags=_parse_tags(tags),
        language=language,
        license_=license,
        topic_slug=topic_slug,
    )

    return {"status": "queued", "filename": destination.name}


# ---------------------------------------------------------------------------
# Review Queue
# ---------------------------------------------------------------------------

@app.get("/api/queue")
def get_queue():
    queue = load_queue()
    items = _reviewable_unscored_or_low(queue)
    result = []
    for e in items:
        result.append({
            "id": e.get("source_id", ""),
            "title": e.get("title", ""),
            "topic": e.get("topic_slug", ""),
            "confidence": e.get("confidence_score"),
            "confidence_band": e.get("confidence_band", ""),
            "date_synthesized": str(e.get("scored_at", e.get("queued_at", "")))[:10],
            "summary_path": str(e.get("source_note_path", "")),
        })
    return {"items": result}


@app.post("/api/queue/{source_id}/approve")
def approve_item(source_id: str):
    queue = load_queue()
    updated, found = approve(queue, source_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"'{source_id}' not found in queue.")
    save_queue(updated)
    item = next((e for e in updated if e.get("source_id") == source_id), {})
    path = _find_compiled_note(item, ROOT)
    if path:
        _patch_note_approved(path, approved=True)
    return {"status": "approved", "id": source_id}


@app.post("/api/queue/{source_id}/reject")
def reject_item(source_id: str, reason: str = ""):
    queue = load_queue()
    updated, found = reject(queue, source_id, reason=reason)
    if not found:
        raise HTTPException(status_code=404, detail=f"'{source_id}' not found in queue.")
    save_queue(updated)
    item = next((e for e in updated if e.get("source_id") == source_id), {})
    path = _find_compiled_note(item, ROOT)
    if path:
        _patch_note_approved(path, approved=False)
    return {"status": "rejected", "id": source_id}


@app.get("/api/queue/{source_id}/preview")
def preview_item(source_id: str):
    queue = load_queue()
    item = next((e for e in queue if e.get("source_id") == source_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"'{source_id}' not found in queue.")
    path = _find_compiled_note(item, ROOT)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Compiled note not found for this item.")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KB Ingestion & Review Dashboard")
    parser.add_argument("--port", type=int, default=7842, help="Port to listen on. Default: 7842")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Default: 127.0.0.1")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    print(f"KB Dashboard → http://{args.host}:{args.port}")
    uvicorn.run("dashboard:app", host=args.host, port=args.port, reload=False)

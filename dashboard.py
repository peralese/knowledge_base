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
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = ROOT / "dashboard"
TOPIC_REGISTRY_PATH = ROOT / "metadata" / "topic-registry.json"
TMP_DIR = ROOT / "tmp"

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
from stage_to_inbox import StageRequest, slugify_title, stage  # noqa: E402

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
# Ingestion
# ---------------------------------------------------------------------------

class IngestURLRequest(BaseModel):
    url: str
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

    # Derive a title from the URL path
    url_path = url.rstrip("/").split("/")[-1] or "web-article"
    title = _kebab(url_path).replace("-", " ").title()

    # Inject notes and topic into text
    if body.notes.strip():
        text = f"<!-- notes: {body.notes.strip()} -->\n\n{text}"
    if body.topic_slug.strip():
        text = f"<!-- topic_slug: {body.topic_slug.strip()} -->\n\n{text}"

    # Write to a temp file then stage via browser adapter
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = TMP_DIR / f"{uuid.uuid4().hex}.md"
    try:
        tmp_path.write_text(text, encoding="utf-8")
        request = StageRequest(
            adapter="browser",
            title=title,
            canonical_url=url,
            input_file=tmp_path,
            root=ROOT,
        )
        destination = stage(request)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    # Inject optional metadata into the staged file's frontmatter
    optional = {
        "source_type": body.source_type or "article",
        "author": body.author,
        "date_published": body.date_published,
        "tags": body.tags or [],
        "language": body.language,
        "license": body.license,
    }
    _inject_optional_frontmatter(destination, optional)

    return {"status": "queued", "filename": destination.name}


@app.post("/api/ingest/file")
def ingest_file(
    file: UploadFile = File(...),
    topic_slug: str = Form(default=""),
    notes: str = Form(default=""),
    source_type: str = Form(default="article"),
    author: str = Form(default=""),
    date_published: str = Form(default=""),
    tags: str = Form(default=""),
    language: str = Form(default=""),
    license: str = Form(default=""),
):
    suffix = Path(file.filename or "upload").suffix.lower()
    allowed = {".pdf", ".html", ".htm", ".md"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(allowed))}",
        )

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = TMP_DIR / f"{uuid.uuid4().hex}{suffix}"

    try:
        tmp_path.write_bytes(file.file.read())

        # For HTML files strip to text first
        if suffix in {".html", ".htm"}:
            raw = tmp_path.read_text(encoding="utf-8", errors="replace")
            text = normalize_text(html_to_text(raw))
            if notes.strip():
                text = f"<!-- notes: {notes.strip()} -->\n\n{text}"
            if topic_slug.strip():
                text = f"<!-- topic_slug: {topic_slug.strip()} -->\n\n{text}"
            tmp_path.write_text(text, encoding="utf-8")

        title = Path(file.filename or "upload").stem.replace("-", " ").replace("_", " ").title()
        adapter = "pdf-drop" if suffix == ".pdf" else "browser"

        request = StageRequest(
            adapter=adapter,
            title=title,
            input_file=tmp_path,
            root=ROOT,
        )
        destination = stage(request)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    # Inject optional metadata into the staged file's frontmatter
    optional = {
        "source_type": source_type.strip() or "article",
        "author": author.strip() or None,
        "date_published": date_published.strip() or None,
        "tags": _parse_tags(tags),
        "language": language.strip() or None,
        "license": license.strip() or None,
    }
    _inject_optional_frontmatter(destination, optional)

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

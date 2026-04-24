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
from datetime import date, datetime
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
SAVED_SEARCHES_PATH = ROOT / "outputs" / "saved_searches.json"
SOURCE_MANIFEST_PATH = ROOT / "metadata" / "source-manifest.json"

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
from feedback import write_feedback  # noqa: E402
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
# 2C-1 Share helpers
# ---------------------------------------------------------------------------

def _url_is_duplicate(url: str, root: Path) -> tuple[bool, str]:
    """Return (is_duplicate, existing_id). Checks manifest and staged inbox files."""
    normalized = url.strip().rstrip("/")

    manifest_path = root / "metadata" / "source-manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for src in manifest.get("sources", []):
                cu = str(src.get("canonical_url", "")).strip().rstrip("/")
                if cu and cu == normalized:
                    return True, str(src.get("source_id", src.get("filename", "unknown")))
        except (json.JSONDecodeError, OSError):
            pass

    for md_file in (root / "raw" / "inbox" / "browser").glob("*.md") if (root / "raw" / "inbox" / "browser").exists() else []:
        try:
            if normalized in md_file.read_text(encoding="utf-8"):
                return True, md_file.stem
        except OSError:
            pass

    for j in (root / "raw" / "inbox" / "feeds").glob("*.json") if (root / "raw" / "inbox" / "feeds").exists() else []:
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
            cu = str(data.get("canonical_url", "")).strip().rstrip("/")
            if cu and cu == normalized:
                return True, j.stem
        except (json.JSONDecodeError, OSError):
            pass

    return False, ""


def _read_raw_article_frontmatter(source_note_path: str, root: Path) -> dict:
    """Read canonical_url and date_ingested from a raw article's frontmatter."""
    path = root / source_note_path if source_note_path else None
    if not path or not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            return {}
        end = text.find("\n---\n", 4)
        if end == -1:
            return {}
        result: dict = {}
        for line in text[4:end].splitlines():
            for key in ("canonical_url", "date_ingested"):
                m = re.match(rf'^{re.escape(key)}:\s*"?([^"]+)"?\s*$', line.strip())
                if m:
                    result[key] = m.group(1).strip()
        return result
    except OSError:
        return {}


# ---------------------------------------------------------------------------
# 2C-3 Saved Searches helpers
# ---------------------------------------------------------------------------

def _load_saved_searches() -> list[dict]:
    if not SAVED_SEARCHES_PATH.exists():
        return []
    try:
        data = json.loads(SAVED_SEARCHES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_saved_searches(searches: list[dict]) -> None:
    SAVED_SEARCHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAVED_SEARCHES_PATH.write_text(json.dumps(searches, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 2C-3 Pinned Topics helpers
# ---------------------------------------------------------------------------

def _get_topic_note_path(slug: str, root: Path) -> Path:
    return root / "compiled" / "topics" / f"{slug}.md"


def _read_pinned_state(slug: str, root: Path) -> bool:
    path = _get_topic_note_path(slug, root)
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
        m = re.search(r'^pinned:\s*(true|false)\s*$', text, re.MULTILINE)
        return m.group(1) == "true" if m else False
    except OSError:
        return False


def _write_pinned_state(slug: str, pinned: bool, root: Path) -> bool:
    """Write pinned field into topic note frontmatter. Returns True on success."""
    path = _get_topic_note_path(slug, root)
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
        value_str = "true" if pinned else "false"
        pattern = r'^pinned:\s*(true|false)\s*$'
        if re.search(pattern, text, re.MULTILINE):
            text = re.sub(pattern, f"pinned: {value_str}", text, flags=re.MULTILINE)
        else:
            # Insert after the opening ---
            text = re.sub(r'\n---\n', f'\npinned: {value_str}\n---\n', text, count=1)
        path.write_text(text, encoding="utf-8")
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 2C-3 Recent Entity Activity helpers
# ---------------------------------------------------------------------------

def _recent_entity_activity(root: Path, limit: int = 10) -> list[dict]:
    """Return the N most recently active entities based on static metadata only.

    Activity date = max(entity date_updated, most recent approved source date mentioning it).
    No LLM calls. Completes well under 500ms.
    """

    entities_dir = root / "compiled" / "entities"
    articles_dir = root / "raw" / "articles"
    answers_dir = root / "outputs" / "answers"

    # Build entity list with their own dates
    results: list[dict] = []
    if not entities_dir.exists():
        return []

    # Index: approved source stem -> date_ingested (for fast lookup)
    source_dates: dict[str, str] = {}
    if articles_dir.exists():
        for art in articles_dir.glob("*.md"):
            try:
                text = art.read_text(encoding="utf-8", errors="replace")
                if "approved: true" not in text:
                    continue
                m = re.search(r'^date_ingested:\s*"?([0-9\-]+)"?\s*$', text, re.MULTILINE)
                if m:
                    source_dates[art.stem] = m.group(1).strip()
            except OSError:
                continue

    # Most recent answer date
    answer_dates: list[str] = []
    if answers_dir.exists():
        for ans in answers_dir.glob("*.md"):
            try:
                text = ans.read_text(encoding="utf-8", errors="replace")
                m = re.search(r'^date:\s*"?([0-9\-]+)"?\s*$', text, re.MULTILINE)
                if m:
                    answer_dates.append(m.group(1).strip())
            except OSError:
                continue
    latest_answer_date = max(answer_dates) if answer_dates else ""

    for ent_file in entities_dir.glob("*.md"):
        try:
            text = ent_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        slug = ent_file.stem
        name = slug.replace("-", " ").replace("_", " ").title()

        # Entity's own last-updated date
        m = re.search(r'^date_updated:\s*"?([0-9\-]+)"?\s*$', text, re.MULTILINE)
        if not m:
            m = re.search(r'^date_compiled:\s*"?([0-9\-]+)"?\s*$', text, re.MULTILINE)
        entity_date = m.group(1).strip() if m else ""

        # Sources listed in entity frontmatter
        source_stems: list[str] = []
        in_sources = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "sources:":
                in_sources = True
                continue
            if in_sources:
                if stripped.startswith("- "):
                    src = stripped[2:].strip().strip('"').strip("'")
                    source_stems.append(src)
                    continue
                if line and not line.startswith((" ", "\t")):
                    in_sources = False

        # Most recent source date for this entity
        source_dates_for_entity = [source_dates[s] for s in source_stems if s in source_dates]
        latest_source = max(source_dates_for_entity) if source_dates_for_entity else ""

        activity_date = max(filter(None, [entity_date, latest_source])) if any([entity_date, latest_source]) else ""
        if not activity_date:
            continue

        last_seen_in = source_stems[0] if source_stems else "entity note"
        results.append({
            "slug": slug,
            "name": name,
            "last_seen_date": activity_date,
            "last_seen_in": last_seen_in,
        })

    results.sort(key=lambda x: x["last_seen_date"], reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ShareURLRequest(BaseModel):
    url: str
    note: str = ""


class SavedSearchRequest(BaseModel):
    name: str
    query: str
    topic_scope: Optional[str] = None


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
        {
            "slug": t.get("slug", ""),
            "display_name": t.get("title", t.get("slug", "")),
            "pinned": _read_pinned_state(t.get("slug", ""), ROOT),
        }
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


# ---------------------------------------------------------------------------
# Concepts / Entities
# ---------------------------------------------------------------------------

def _build_concepts_index(root: Path) -> list[dict]:
    """Build a fast static index of all concept and entity notes.

    Each entry: {slug, name, type, is_stub, source_count, incoming_links}
    No LLM calls. Completes in well under 500ms for typical corpus sizes.
    """
    from graph_health import (  # noqa: PLC0415
        _all_wikilink_targets,
        _parse_compiled_from,
        _read_notes,
        is_stub,
    )

    concepts = _read_notes(root / "compiled" / "concepts")
    entities = _read_notes(root / "compiled" / "entities")
    summaries = _read_notes(root / "compiled" / "source_summaries")
    topics = _read_notes(root / "compiled" / "topics")

    # Build incoming-link count for each concept/entity slug
    all_collections = {
        "topics": topics,
        "source_summaries": summaries,
    }
    incoming = _all_wikilink_targets(all_collections)

    # Approved summary stems for source_count calculation
    approved_stems = {
        stem for stem, text in summaries.items() if "approved: true" in text
    }

    def _source_count(name: str) -> int:
        """Number of approved source summaries whose body mentions this name."""
        from inject_wikilinks import _slug_to_display  # noqa: PLC0415
        display = _slug_to_display(name)
        count = 0
        for stem, text in summaries.items():
            if stem not in approved_stems:
                continue
            body_lower = text.lower()
            if display in body_lower or name.lower() in body_lower:
                count += 1
        return count

    results: list[dict] = []

    for note_type, collection in [("concept", concepts), ("entity", entities)]:
        for slug, text in collection.items():
            name = slug.replace("-", " ").replace("_", " ").title()
            stub = is_stub(text)
            inc_count = len(incoming.get(slug, set()) - {slug})
            results.append({
                "slug": slug,
                "name": name,
                "type": note_type,
                "is_stub": stub,
                "source_count": _source_count(slug),
                "incoming_links": inc_count,
            })

    return results


@app.get("/api/concepts")
def get_concepts():
    """Return the concept/entity index as JSON. Fast static scan, no LLM calls."""
    items = _build_concepts_index(ROOT)
    return {"concepts": items, "total": len(items)}


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


class FeedbackRequest(BaseModel):
    answer_id: str
    rating: str
    note: str = ""


@app.post("/api/feedback")
def post_feedback(body: FeedbackRequest):
    rating = body.rating.strip()
    if rating not in ("good", "bad"):
        raise HTTPException(status_code=400, detail="rating must be 'good' or 'bad'.")
    answer_id = body.answer_id.strip()
    if not answer_id:
        raise HTTPException(status_code=400, detail="answer_id is required.")
    stem = answer_id.removesuffix(".md")
    path = ROOT / "outputs" / "answers" / f"{stem}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Answer not found: {answer_id}")
    write_feedback(path, rating, note=body.note)
    return {"ok": True, "answer_id": answer_id, "rating": rating}


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
        note_meta = _read_raw_article_frontmatter(str(e.get("source_note_path", "")), ROOT)
        result.append({
            "id": e.get("source_id", ""),
            "title": e.get("title", ""),
            "topic": e.get("topic_slug", ""),
            "confidence": e.get("confidence_score"),
            "confidence_band": e.get("confidence_band", ""),
            "date_synthesized": str(e.get("scored_at", e.get("queued_at", "")))[:10],
            "date_ingested": note_meta.get("date_ingested", str(e.get("queued_at", ""))[:10]),
            "canonical_url": note_meta.get("canonical_url", ""),
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
# 2C-1 Mobile Share Endpoint
# ---------------------------------------------------------------------------

@app.post("/api/share")
def share_url(body: ShareURLRequest):
    """Accept a URL from a mobile share sheet and queue it to the inbox.

    Returns {"status": "queued", "inbox_id": "INX-..."} on success.
    Returns 409 {"status": "duplicate", "existing_id": "..."} if already known.
    Returns 400 for invalid/unreachable URLs.
    """
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required.")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")

    is_dup, existing_id = _url_is_duplicate(url, ROOT)
    if is_dup:
        return JSONResponse(
            status_code=409,
            content={"status": "duplicate", "existing_id": existing_id},
        )

    # Validate reachability and extract title
    title = ""
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; KBDashboard/1.0)"},
        )
        response.raise_for_status()
        title = _extract_page_title(response.text) or ""
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"URL not reachable: {exc}")

    if not title:
        try:
            from urllib.parse import urlparse  # noqa: PLC0415
            title = urlparse(url).hostname or url
        except Exception:
            title = url

    note = body.note.strip()
    inbox_id = f"INX-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    content = note if note else f"[Shared from mobile — {inbox_id}]"

    # Write to inbox using same format as stage_to_inbox.py (feeds adapter)
    import json as _json  # noqa: PLC0415
    from stage_to_inbox import StageRequest, stage_feed  # noqa: PLC0415

    req = StageRequest(
        adapter="feeds",
        text=_json.dumps({
            "title": title,
            "canonical_url": url,
            "content": content,
            "inbox_id": inbox_id,
        }),
        title=title,
        canonical_url=url,
        root=ROOT,
    )
    stage_feed(req)

    return {"status": "queued", "inbox_id": inbox_id}


# ---------------------------------------------------------------------------
# 2C-3 Saved Searches Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/saved-searches")
def list_saved_searches():
    return {"searches": _load_saved_searches()}


@app.post("/api/saved-searches", status_code=201)
def create_saved_search(body: SavedSearchRequest):
    name = body.name.strip()
    query = body.query.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required.")
    if not query:
        raise HTTPException(status_code=400, detail="query is required.")

    searches = _load_saved_searches()
    search_id = f"SS-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    entry: dict = {
        "id": search_id,
        "name": name,
        "query": query,
        "topic_scope": body.topic_scope or None,
        "created_at": now,
        "last_run_at": None,
    }
    searches.append(entry)
    _save_saved_searches(searches)
    return {"search": entry}


@app.delete("/api/saved-searches/{search_id}")
def delete_saved_search(search_id: str):
    searches = _load_saved_searches()
    updated = [s for s in searches if s.get("id") != search_id]
    if len(updated) == len(searches):
        raise HTTPException(status_code=404, detail=f"Saved search '{search_id}' not found.")
    _save_saved_searches(updated)
    return {"status": "deleted", "id": search_id}


@app.post("/api/saved-searches/{search_id}/run")
def run_saved_search(search_id: str):
    """Update last_run_at timestamp and return the search for re-execution by the client."""
    searches = _load_saved_searches()
    entry = next((s for s in searches if s.get("id") == search_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Saved search '{search_id}' not found.")
    entry["last_run_at"] = datetime.now().isoformat()
    _save_saved_searches(searches)
    return {"search": entry}


# ---------------------------------------------------------------------------
# 2C-3 Pinned Topics Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/topics/{slug}/pin")
def pin_topic(slug: str):
    registry = _load_registry()
    topic = next((t for t in registry.get("topics", []) if t.get("slug") == slug), None)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found in registry.")
    success = _write_pinned_state(slug, pinned=True, root=ROOT)
    return {"status": "pinned", "slug": slug, "note_updated": success}


@app.post("/api/topics/{slug}/unpin")
def unpin_topic(slug: str):
    registry = _load_registry()
    topic = next((t for t in registry.get("topics", []) if t.get("slug") == slug), None)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found in registry.")
    success = _write_pinned_state(slug, pinned=False, root=ROOT)
    return {"status": "unpinned", "slug": slug, "note_updated": success}


# ---------------------------------------------------------------------------
# 2C-3 Recent Entity Activity Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/entities/recent")
def get_recent_entities():
    """Return the 10 most recently active entities based on static metadata scan.

    Completes in well under 500ms — no LLM calls.
    """
    results = _recent_entity_activity(ROOT, limit=10)
    return {"entities": results}


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

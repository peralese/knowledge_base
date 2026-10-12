"""Save a web article into a category folder on the NAS, then index it.

  python add_url.py <url> <category 1-7>

Saves <slug>.html plus <slug>.html.url.json (the source URL) under
LIBRARY_ROOT/<category folder>/articles/.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import httpx

import indexer
from notes import category_dir
from parse import parse_article
from store import CATEGORIES, LIBRARY_ROOT

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/605.1.15"


def add(url: str, category: int) -> tuple[Path, str]:
    """Fetch and save the page; returns (saved file, one-line summary)."""
    if category not in CATEGORIES:
        raise ValueError(f"category must be 1-7, got {category}")
    r = httpx.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=60)
    r.raise_for_status()
    slug = re.sub(r"[^a-z0-9]+", "-", url.rstrip("/").split("/")[-1].lower()).strip("-") or "article"
    out_dir = category_dir(category) / "articles"
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / f"{slug}.html"
    dest.write_text(r.text, encoding="utf-8")
    dest.with_suffix(".html.url.json").write_text(
        json.dumps({"url": url, "fetched": date.today().isoformat()}, indent=2))

    doc = parse_article(dest)
    words = sum(len(s.text.split()) for s in doc.sections)
    msg = (f"saved {dest.relative_to(LIBRARY_ROOT)}: {doc.title!r}, "
           f"{len(doc.sections)} sections, {words} words")
    if words < 200:
        msg += ("\nwarning: very little text extracted — the page may need JavaScript "
                "or be behind a login. Check before relying on it.")
    return dest, msg


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    dest, msg = add(sys.argv[1], int(sys.argv[2]))
    print(msg)
    print(indexer.index_path(dest))

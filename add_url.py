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
from parse import parse_article
from store import CATEGORIES, LIBRARY_ROOT

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/605.1.15"


def category_dir(category: int) -> Path:
    for d in LIBRARY_ROOT.iterdir():
        if d.is_dir() and re.match(rf"^\s*{category}\b", d.name):
            return d
    raise SystemExit(f"No folder for category {category} under {LIBRARY_ROOT}")


def add(url: str, category: int) -> Path:
    if category not in CATEGORIES:
        raise SystemExit(f"category must be 1-7, got {category}")
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
    print(f"saved {dest.relative_to(LIBRARY_ROOT)}: {doc.title!r}, "
          f"{len(doc.sections)} sections, {words} words")
    if words < 200:
        print("warning: very little text extracted — the page may need JavaScript "
              "or be behind a login. Check before relying on it.")
    return dest


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    add(sys.argv[1], int(sys.argv[2]))
    print(indexer.run())

"""feed_poller.py — Auto-fetch RSS/Atom feed entries into raw/inbox/feeds/.

Reads a list of feed URLs from metadata/feeds.json, fetches each feed with
urllib (no external dependencies), parses RSS 2.0 and Atom 1.0 entries, and
writes new entries as JSON files to raw/inbox/feeds/ for inbox_watcher.py to
pick up and ingest.

Already-fetched entries are tracked in metadata/.feed-poller-state.json by
their canonical URL so the poller is safe to stop and restart.

Config format (metadata/feeds.json):
    A JSON array of feed URLs (strings) or objects with a "url" key:

        ["https://example.com/feed.xml"]

    or

        [{"name": "Example Blog", "url": "https://example.com/feed.xml"}]

Usage:
    # Poll all feeds once then exit
    python3 scripts/feed_poller.py --once

    # Poll feeds on a schedule (default: every hour)
    python3 scripts/feed_poller.py

    # Custom interval (seconds)
    python3 scripts/feed_poller.py --interval 1800

    # Custom config file
    python3 scripts/feed_poller.py --config path/to/feeds.json

    # Dry run — print what would be written without touching disk
    python3 scripts/feed_poller.py --once --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator


ROOT = Path(__file__).resolve().parents[1]
FEEDS_CONFIG_PATH = ROOT / "metadata" / "feeds.json"
FEEDS_INBOX_DIR = ROOT / "raw" / "inbox" / "feeds"
STATE_PATH = ROOT / "metadata" / ".feed-poller-state.json"
DEFAULT_INTERVAL = 3600  # seconds
REQUEST_TIMEOUT = 15  # seconds

# XML namespaces
_NS_ATOM = "http://www.w3.org/2005/Atom"
_NS_CONTENT = "http://purl.org/rss/1.0/modules/content/"


@dataclass
class FeedEntry:
    title: str
    url: str
    content: str
    feed_name: str = ""


@dataclass
class PollResult:
    feed_url: str
    new_entries: list[FeedEntry] = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_feed_urls(config_path: Path) -> list[tuple[str, str]]:
    """Load feed list from config. Returns list of (name, url) tuples."""
    if not config_path.exists():
        return []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    result: list[tuple[str, str]] = []
    for item in data:
        if isinstance(item, str):
            url = item.strip()
            if url:
                result.append(("", url))
        elif isinstance(item, dict):
            url = str(item.get("url", "")).strip()
            name = str(item.get("name", "")).strip()
            if url:
                result.append((name, url))
    return result


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state(state_path: Path) -> dict[str, str]:
    """Load already-seen entry URLs mapped to fetch timestamp."""
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, str], state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def fetch_feed(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes:
    """Fetch a feed URL and return raw bytes. Raises urllib.error.URLError on failure."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "KnowledgeBase-FeedPoller/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


# ---------------------------------------------------------------------------
# HTML stripping (delegates to ingest.py to avoid duplication)
# ---------------------------------------------------------------------------

def _html_to_text(html_content: str) -> str:
    sys.path.insert(0, str(Path(__file__).parent))
    from ingest import html_to_text  # noqa: PLC0415
    return html_to_text(html_content)


# ---------------------------------------------------------------------------
# RSS / Atom parsing
# ---------------------------------------------------------------------------

def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return (element.text or "").strip()


def parse_rss(root: ET.Element, feed_name: str) -> Iterator[FeedEntry]:
    """Yield FeedEntry objects from an RSS 2.0 document."""
    channel = root.find("channel")
    if channel is None:
        return
    for item in channel.findall("item"):
        title = _element_text(item.find("title")) or "Untitled"
        link = _element_text(item.find("link")) or ""

        content_el = item.find(f"{{{_NS_CONTENT}}}encoded")
        raw_content = (
            _element_text(content_el)
            if content_el is not None
            else _element_text(item.find("description"))
        )
        content = _html_to_text(raw_content) if raw_content else ""

        if link:
            yield FeedEntry(title=title, url=link, content=content, feed_name=feed_name)


def parse_atom(root: ET.Element, feed_name: str) -> Iterator[FeedEntry]:
    """Yield FeedEntry objects from an Atom 1.0 document."""
    for entry in root.findall(f"{{{_NS_ATOM}}}entry"):
        title = _element_text(entry.find(f"{{{_NS_ATOM}}}title")) or "Untitled"

        # Prefer rel="alternate" link, fall back to first link with href
        link = ""
        for link_el in entry.findall(f"{{{_NS_ATOM}}}link"):
            rel = link_el.get("rel", "alternate")
            href = link_el.get("href", "")
            if rel in ("alternate", "") and href:
                link = href
                break
        if not link:
            first_link = entry.find(f"{{{_NS_ATOM}}}link")
            if first_link is not None:
                link = first_link.get("href", "")

        content_el = entry.find(f"{{{_NS_ATOM}}}content")
        summary_el = entry.find(f"{{{_NS_ATOM}}}summary")
        raw_content = _element_text(content_el) or _element_text(summary_el)
        content = _html_to_text(raw_content) if raw_content else ""

        if link:
            yield FeedEntry(title=title, url=link, content=content, feed_name=feed_name)


def parse_feed(data: bytes, feed_name: str = "") -> list[FeedEntry]:
    """Parse RSS or Atom feed bytes into a list of FeedEntry objects."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []

    tag = root.tag
    if tag == f"{{{_NS_ATOM}}}feed":
        return list(parse_atom(root, feed_name))
    if tag.lower() == "rss" or root.find("channel") is not None:
        return list(parse_rss(root, feed_name))
    if "feed" in tag.lower():
        return list(parse_atom(root, feed_name))
    return []


# ---------------------------------------------------------------------------
# Filename / entry writing
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    slug = text.strip().lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "feed-entry"


def _entry_filename(entry: FeedEntry, ts: str | None = None) -> str:
    timestamp = ts or datetime.now().strftime("%Y%m%d%H%M%S")
    slug = _slugify(entry.title)[:60]
    return f"{timestamp}-{slug}.json"


def write_entry(entry: FeedEntry, inbox_dir: Path, ts: str | None = None) -> Path:
    """Write a FeedEntry as a JSON file consumable by inbox_watcher.py."""
    inbox_dir.mkdir(parents=True, exist_ok=True)
    destination = inbox_dir / _entry_filename(entry, ts)
    payload = {
        "title": entry.title,
        "canonical_url": entry.url,
        "content": entry.content,
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


# ---------------------------------------------------------------------------
# Poll logic
# ---------------------------------------------------------------------------

def poll_feed(
    name: str,
    url: str,
    state: dict[str, str],
    inbox_dir: Path,
    dry_run: bool = False,
    fetcher: Callable[[str], bytes] | None = None,
) -> PollResult:
    """Fetch one feed, filter to unseen entries, and write them to inbox_dir.

    Args:
        fetcher: Optional callable replacing urllib fetch (useful in tests).
    """
    result = PollResult(feed_url=url)
    _fetch = fetcher if fetcher is not None else fetch_feed
    try:
        data = _fetch(url)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        result.error = str(exc)
        return result

    entries = parse_feed(data, name)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    for entry in entries:
        if not entry.url:
            continue
        if entry.url in state:
            continue
        result.new_entries.append(entry)
        if not dry_run:
            write_entry(entry, inbox_dir, ts)
        state[entry.url] = datetime.now().isoformat()

    return result


def poll_all(
    feeds: list[tuple[str, str]],
    state: dict[str, str],
    inbox_dir: Path,
    state_path: Path,
    dry_run: bool = False,
    fetcher: Callable[[str], bytes] | None = None,
) -> int:
    """Poll all configured feeds. Returns total count of new entries."""
    total_new = 0
    for name, url in feeds:
        label = name or url
        print(f"  Polling : {label}")
        result = poll_feed(name, url, state, inbox_dir, dry_run=dry_run, fetcher=fetcher)
        if result.error:
            print(f"    Error : {result.error}")
        else:
            count = len(result.new_entries)
            total_new += count
            suffix = "entry" if count == 1 else "entries"
            label_count = f"{count} new {suffix}" if count else "0 (nothing new)"
            print(f"    New   : {label_count}")
    if not dry_run:
        save_state(state, state_path)
    return total_new


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------

def run(
    config_path: Path,
    inbox_dir: Path,
    state_path: Path,
    interval: int,
    once: bool,
    dry_run: bool,
    fetcher: Callable[[str], bytes] | None = None,
) -> None:
    feeds = load_feed_urls(config_path)
    if not feeds:
        print(f"No feeds configured. Add URLs to {config_path.relative_to(ROOT)}")
        return

    state = load_state(state_path)

    if once:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] Polling {len(feeds)} feed(s)...")
        total = poll_all(feeds, state, inbox_dir, state_path, dry_run=dry_run, fetcher=fetcher)
        suffix = "entry" if total == 1 else "entries"
        print(f"  Done    : {total} new {suffix} written")
        return

    print(f"Feed poller started  (interval: {interval}s, Ctrl-C to stop)")
    print(f"Config : {config_path.relative_to(ROOT)}  |  Feeds: {len(feeds)}")
    try:
        while True:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] Polling {len(feeds)} feed(s)...")
            poll_all(feeds, state, inbox_dir, state_path, dry_run=dry_run, fetcher=fetcher)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nFeed poller stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll RSS/Atom feeds and write new entries to raw/inbox/feeds/."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=FEEDS_CONFIG_PATH,
        help="Path to feeds config JSON. Default: metadata/feeds.json",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Poll interval in seconds. Default: {DEFAULT_INTERVAL}",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Poll all feeds once then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print new entries without writing files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(
        config_path=args.config,
        inbox_dir=FEEDS_INBOX_DIR,
        state_path=STATE_PATH,
        interval=args.interval,
        once=args.once,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from scripts.feed_poller import (
    FeedEntry,
    _entry_filename,
    _slugify,
    load_feed_urls,
    load_state,
    parse_atom,
    parse_feed,
    parse_rss,
    poll_all,
    poll_feed,
    save_state,
    write_entry,
)
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

RSS_FEED = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <item>
      <title>First Post</title>
      <link>https://example.com/first</link>
      <description>Summary of the first post.</description>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.com/second</link>
      <description>&lt;p&gt;HTML summary.&lt;/p&gt;</description>
    </item>
  </channel>
</rss>"""

ATOM_FEED = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Blog</title>
  <entry>
    <title>Atom Entry One</title>
    <link rel="alternate" href="https://atom.example.com/one"/>
    <summary>Plain text summary.</summary>
  </entry>
  <entry>
    <title>Atom Entry Two</title>
    <link href="https://atom.example.com/two"/>
    <content type="html">&lt;p&gt;Rich content.&lt;/p&gt;</content>
  </entry>
</feed>"""

INVALID_XML = b"this is not xml at all <<<>>>"

ATOM_NO_LINK = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>No Link Entry</title>
    <summary>Has no link element.</summary>
  </entry>
</feed>"""

RSS_CONTENT_ENCODED = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <item>
      <title>Rich Item</title>
      <link>https://example.com/rich</link>
      <description>Plain fallback</description>
      <content:encoded>&lt;p&gt;Full HTML body here.&lt;/p&gt;</content:encoded>
    </item>
  </channel>
</rss>"""


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class LoadFeedUrlsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _config(self, data: object) -> Path:
        path = self.root / "feeds.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_string_urls(self) -> None:
        path = self._config(["https://a.com/feed", "https://b.com/rss"])
        result = load_feed_urls(path)
        self.assertEqual(result, [("", "https://a.com/feed"), ("", "https://b.com/rss")])

    def test_object_urls(self) -> None:
        path = self._config([{"name": "Blog A", "url": "https://a.com/feed"}])
        result = load_feed_urls(path)
        self.assertEqual(result, [("Blog A", "https://a.com/feed")])

    def test_mixed_formats(self) -> None:
        path = self._config(["https://a.com/feed", {"name": "B", "url": "https://b.com/rss"}])
        result = load_feed_urls(path)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("", "https://a.com/feed"))
        self.assertEqual(result[1], ("B", "https://b.com/rss"))

    def test_missing_file_returns_empty(self) -> None:
        result = load_feed_urls(self.root / "nonexistent.json")
        self.assertEqual(result, [])

    def test_invalid_json_returns_empty(self) -> None:
        path = self.root / "bad.json"
        path.write_text("not json", encoding="utf-8")
        result = load_feed_urls(path)
        self.assertEqual(result, [])

    def test_non_list_json_returns_empty(self) -> None:
        path = self._config({"url": "https://a.com"})
        result = load_feed_urls(path)
        self.assertEqual(result, [])

    def test_object_missing_url_skipped(self) -> None:
        path = self._config([{"name": "No URL"}])
        result = load_feed_urls(path)
        self.assertEqual(result, [])

    def test_empty_string_entries_skipped(self) -> None:
        path = self._config(["", "  "])
        result = load_feed_urls(path)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "state.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_load_missing_returns_empty(self) -> None:
        self.assertEqual(load_state(self.state_path), {})

    def test_save_and_load_roundtrip(self) -> None:
        state = {"https://example.com/a": "2026-04-13T00:00:00"}
        save_state(state, self.state_path)
        self.assertEqual(load_state(self.state_path), state)

    def test_corrupted_state_returns_empty(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text("not json", encoding="utf-8")
        self.assertEqual(load_state(self.state_path), {})

    def test_save_creates_parent_dirs(self) -> None:
        nested = Path(self.tmp.name) / "deep" / "nested" / "state.json"
        save_state({"k": "v"}, nested)
        self.assertTrue(nested.exists())


# ---------------------------------------------------------------------------
# RSS parsing
# ---------------------------------------------------------------------------

class ParseRssTests(unittest.TestCase):
    def _parse(self, data: bytes) -> list[FeedEntry]:
        root = ET.fromstring(data)
        return list(parse_rss(root, "TestFeed"))

    def test_parses_two_items(self) -> None:
        entries = self._parse(RSS_FEED)
        self.assertEqual(len(entries), 2)

    def test_title_and_url(self) -> None:
        entries = self._parse(RSS_FEED)
        self.assertEqual(entries[0].title, "First Post")
        self.assertEqual(entries[0].url, "https://example.com/first")

    def test_feed_name_propagated(self) -> None:
        entries = self._parse(RSS_FEED)
        self.assertEqual(entries[0].feed_name, "TestFeed")

    def test_html_stripped_from_description(self) -> None:
        entries = self._parse(RSS_FEED)
        self.assertNotIn("<p>", entries[1].content)
        self.assertIn("HTML summary", entries[1].content)

    def test_content_encoded_preferred_over_description(self) -> None:
        entries = self._parse(RSS_CONTENT_ENCODED)
        self.assertEqual(len(entries), 1)
        self.assertIn("Full HTML body", entries[0].content)

    def test_no_channel_returns_empty(self) -> None:
        data = b"<rss version='2.0'/>"
        root = ET.fromstring(data)
        self.assertEqual(list(parse_rss(root, "")), [])

    def test_item_without_link_skipped(self) -> None:
        data = b"""<rss><channel>
          <item><title>No Link</title><description>x</description></item>
        </channel></rss>"""
        root = ET.fromstring(data)
        entries = list(parse_rss(root, ""))
        self.assertEqual(entries, [])


# ---------------------------------------------------------------------------
# Atom parsing
# ---------------------------------------------------------------------------

class ParseAtomTests(unittest.TestCase):
    def _parse(self, data: bytes) -> list[FeedEntry]:
        root = ET.fromstring(data)
        return list(parse_atom(root, "AtomFeed"))

    def test_parses_two_entries(self) -> None:
        entries = self._parse(ATOM_FEED)
        self.assertEqual(len(entries), 2)

    def test_title_and_url(self) -> None:
        entries = self._parse(ATOM_FEED)
        self.assertEqual(entries[0].title, "Atom Entry One")
        self.assertEqual(entries[0].url, "https://atom.example.com/one")

    def test_summary_used_as_content(self) -> None:
        entries = self._parse(ATOM_FEED)
        self.assertIn("Plain text summary", entries[0].content)

    def test_html_content_stripped(self) -> None:
        entries = self._parse(ATOM_FEED)
        self.assertNotIn("<p>", entries[1].content)
        self.assertIn("Rich content", entries[1].content)

    def test_link_without_rel_attribute_used(self) -> None:
        entries = self._parse(ATOM_FEED)
        self.assertEqual(entries[1].url, "https://atom.example.com/two")

    def test_entry_without_link_skipped(self) -> None:
        root = ET.fromstring(ATOM_NO_LINK)
        entries = list(parse_atom(root, ""))
        self.assertEqual(entries, [])


# ---------------------------------------------------------------------------
# parse_feed dispatch
# ---------------------------------------------------------------------------

class ParseFeedTests(unittest.TestCase):
    def test_dispatches_rss(self) -> None:
        entries = parse_feed(RSS_FEED)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].title, "First Post")

    def test_dispatches_atom(self) -> None:
        entries = parse_feed(ATOM_FEED)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].title, "Atom Entry One")

    def test_invalid_xml_returns_empty(self) -> None:
        self.assertEqual(parse_feed(INVALID_XML), [])

    def test_unrecognized_root_returns_empty(self) -> None:
        self.assertEqual(parse_feed(b"<document/>"), [])


# ---------------------------------------------------------------------------
# Slugify / filename
# ---------------------------------------------------------------------------

class SlugifyTests(unittest.TestCase):
    def test_basic_slug(self) -> None:
        self.assertEqual(_slugify("Hello World"), "hello-world")

    def test_collapses_multiple_hyphens(self) -> None:
        self.assertEqual(_slugify("a  b  c"), "a-b-c")

    def test_strips_leading_trailing_hyphens(self) -> None:
        self.assertEqual(_slugify("  hello  "), "hello")

    def test_empty_string_returns_fallback(self) -> None:
        self.assertEqual(_slugify(""), "feed-entry")

    def test_special_chars_replaced(self) -> None:
        result = _slugify("C++ & Python!")
        self.assertNotIn("+", result)
        self.assertNotIn("&", result)
        self.assertNotIn("!", result)


class EntryFilenameTests(unittest.TestCase):
    def test_uses_provided_timestamp(self) -> None:
        entry = FeedEntry(title="My Post", url="https://x.com", content="")
        filename = _entry_filename(entry, ts="20260413120000")
        self.assertTrue(filename.startswith("20260413120000-"))
        self.assertTrue(filename.endswith(".json"))

    def test_slug_in_filename(self) -> None:
        entry = FeedEntry(title="Hello World", url="https://x.com", content="")
        filename = _entry_filename(entry, ts="20260413000000")
        self.assertIn("hello-world", filename)

    def test_long_title_truncated(self) -> None:
        entry = FeedEntry(title="A" * 100, url="https://x.com", content="")
        filename = _entry_filename(entry, ts="20260413000000")
        # slug portion is capped at 60 chars, plus timestamp and .json
        self.assertLessEqual(len(filename), len("20260413000000-") + 60 + len(".json"))


# ---------------------------------------------------------------------------
# write_entry
# ---------------------------------------------------------------------------

class WriteEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.tmp.name) / "feeds"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_writes_json_file(self) -> None:
        entry = FeedEntry(title="Test Entry", url="https://example.com/e", content="Body text")
        path = write_entry(entry, self.inbox, ts="20260413000000")
        self.assertTrue(path.exists())

    def test_json_payload_fields(self) -> None:
        entry = FeedEntry(title="Test Entry", url="https://example.com/e", content="Body text")
        path = write_entry(entry, self.inbox, ts="20260413000000")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["title"], "Test Entry")
        self.assertEqual(payload["canonical_url"], "https://example.com/e")
        self.assertEqual(payload["content"], "Body text")

    def test_creates_inbox_dir_if_missing(self) -> None:
        nested = Path(self.tmp.name) / "deep" / "feeds"
        entry = FeedEntry(title="X", url="https://x.com", content="")
        write_entry(entry, nested, ts="20260413000000")
        self.assertTrue(nested.exists())


# ---------------------------------------------------------------------------
# poll_feed
# ---------------------------------------------------------------------------

class PollFeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.tmp.name) / "feeds"
        self.state: dict[str, str] = {}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_new_entries_written(self) -> None:
        result = poll_feed("", "http://fake/rss", self.state, self.inbox, fetcher=lambda u: RSS_FEED)
        self.assertEqual(len(result.new_entries), 2)
        files = list(self.inbox.glob("*.json"))
        self.assertEqual(len(files), 2)

    def test_already_seen_entry_skipped(self) -> None:
        self.state["https://example.com/first"] = "2026-04-13T00:00:00"
        result = poll_feed("", "http://fake/rss", self.state, self.inbox, fetcher=lambda u: RSS_FEED)
        self.assertEqual(len(result.new_entries), 1)

    def test_dry_run_writes_no_files(self) -> None:
        result = poll_feed("", "http://fake/rss", self.state, self.inbox, dry_run=True, fetcher=lambda u: RSS_FEED)
        self.assertEqual(len(result.new_entries), 2)
        self.assertFalse(self.inbox.exists())

    def test_fetch_error_returns_error_result(self) -> None:
        def bad_fetcher(url: str) -> bytes:
            raise urllib.error.URLError("connection refused")

        result = poll_feed("", "http://fake/rss", self.state, self.inbox, fetcher=bad_fetcher)
        self.assertNotEqual(result.error, "")
        self.assertEqual(result.new_entries, [])

    def test_state_updated_with_seen_urls(self) -> None:
        poll_feed("", "http://fake/rss", self.state, self.inbox, fetcher=lambda u: RSS_FEED)
        self.assertIn("https://example.com/first", self.state)
        self.assertIn("https://example.com/second", self.state)

    def test_invalid_xml_produces_no_entries(self) -> None:
        result = poll_feed("", "http://fake/rss", self.state, self.inbox, fetcher=lambda u: INVALID_XML)
        self.assertEqual(result.new_entries, [])
        self.assertEqual(result.error, "")

    def test_atom_feed_parsed(self) -> None:
        result = poll_feed("", "http://fake/atom", self.state, self.inbox, fetcher=lambda u: ATOM_FEED)
        self.assertEqual(len(result.new_entries), 2)


# ---------------------------------------------------------------------------
# poll_all
# ---------------------------------------------------------------------------

class PollAllTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.tmp.name) / "feeds"
        self.state_path = Path(self.tmp.name) / "state.json"
        self.state: dict[str, str] = {}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_returns_total_new_entry_count(self) -> None:
        feeds = [("Blog", "http://rss"), ("Atom", "http://atom")]
        total = poll_all(
            feeds,
            self.state,
            self.inbox,
            self.state_path,
            fetcher=lambda u: RSS_FEED if "rss" in u else ATOM_FEED,
        )
        self.assertEqual(total, 4)  # 2 from RSS + 2 from Atom

    def test_state_saved_after_poll(self) -> None:
        feeds = [("", "http://rss")]
        poll_all(feeds, self.state, self.inbox, self.state_path, fetcher=lambda u: RSS_FEED)
        self.assertTrue(self.state_path.exists())

    def test_dry_run_does_not_save_state(self) -> None:
        feeds = [("", "http://rss")]
        poll_all(feeds, self.state, self.inbox, self.state_path, dry_run=True, fetcher=lambda u: RSS_FEED)
        self.assertFalse(self.state_path.exists())

    def test_error_feed_does_not_stop_others(self) -> None:
        def fetcher(url: str) -> bytes:
            if "bad" in url:
                raise urllib.error.URLError("timeout")
            return RSS_FEED

        feeds = [("Bad", "http://bad"), ("Good", "http://good")]
        total = poll_all(feeds, self.state, self.inbox, self.state_path, fetcher=fetcher)
        self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()

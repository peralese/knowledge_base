from pathlib import Path

from bs4 import BeautifulSoup

import indexer
from parse import Block, Section, _walk, parse_article, split_passages
from search import fts_query


def _section(*blocks):
    return Section(["Book", "Ch"], "", list(blocks))


def test_code_block_is_never_split():
    code = Block("\n".join(f"x{i} = {i}" for i in range(400)), "code")  # ~1200 words
    s = _section(Block("intro " * 300, "text"), code, Block("after " * 50, "text"))
    passages = split_passages(s)
    assert sum(code.text in p for p in passages) == 1


def test_passages_respect_target_and_merge_short_tail():
    s = _section(*[Block("w " * 100, "text") for _ in range(8)], Block("tail " * 20, "text"))
    passages = split_passages(s)
    sizes = [len(p.split()) for p in passages]
    assert all(300 <= n <= 600 for n in sizes), sizes
    assert "tail" in passages[-1]


def test_heading_stays_with_following_text():
    s = _section(Block("w " * 340, "text"), Block("Next Topic", "heading"), Block("body " * 400, "text"))
    passages = split_passages(s)
    assert not passages[0].endswith("Next Topic")
    assert passages[1].startswith("Next Topic")
    assert all(len(p.split()) <= 600 for p in passages)


def test_walk_switches_section_on_anchor_and_keeps_pre_whitespace():
    html = """<body><div id="a"><h1>A</h1><p>one</p></div>
              <div id="b"><h1>B</h1><pre>def f():\n    return 1</pre></div></body>"""
    events = []
    _walk(BeautifulSoup(html, "lxml").body, lambda a: events.append(("anchor", a)),
          lambda b: events.append((b.kind, b.text)))
    assert events == [("anchor", "a"), ("heading", "A"), ("text", "one"),
                      ("anchor", "b"), ("heading", "B"), ("code", "def f():\n    return 1")]


def test_article_sections_split_at_headings(tmp_path: Path):
    f = tmp_path / "a.html"
    f.write_text("<html><head><title>T</title></head><body><article><h1>T</h1><p>intro</p>"
                 "<h2>Part one</h2><p>alpha</p><h2>Part two</h2><p>beta</p></article></body></html>")
    doc = parse_article(f)
    assert [s.path for s in doc.sections] == [["T"], ["T", "Part one"], ["T", "Part two"]]


def test_fts_query_keeps_phrases_and_drops_stopwords():
    assert fts_query('how do I use "git rebase --onto" safely') == '"git rebase --onto" OR "use" OR "safely"'
    assert fts_query("the and of") is None


def test_category_comes_from_numbered_top_folder():
    assert indexer._category(Path("4 - Data, AI & ML/book.epub")) == 4
    assert indexer._category(Path("4 - Data/articles/x.html")) == 4
    assert indexer._category(Path("Misc/book.epub")) is None
    assert indexer._category(Path("book.epub")) is None

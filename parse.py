"""Turn an EPUB or an HTML/Markdown article into sections and passages.

Sections come from the book's own table of contents (every EPUB we have has
an anchored TOC; heading tags are not reliable — Learning Git uses <h1> for
sub-sections). Passages are a few paragraphs, split only at block boundaries,
and a code block is never split.
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup, NavigableString, Tag

warnings.filterwarnings("ignore", module="ebooklib")
from bs4 import XMLParsedAsHTMLWarning  # noqa: E402
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

TARGET_WORDS = 350  # start a new passage once this is reached
MAX_WORDS = 600  # never let a passage grow past this (except a single huge block)
MIN_TAIL_WORDS = 80  # a shorter final passage is merged into the previous one

BLOCK_TAGS = {"p", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "li", "table",
              "blockquote", "figcaption", "dt", "dd"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

# Front/back matter that is never worth citing.
SKIP_TITLES = re.compile(
    r"^\W*(index|copyright|colophon|about the authors?|table of contents|contents|"
    r"o.reilly online learning|how to contact us|conventions used in this book|"
    r"using code examples|dedication|cover|title page)\W*$",
    re.I,
)


@dataclass
class Block:
    text: str
    kind: str  # "text" | "code" | "heading"

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass
class Section:
    path: list[str]  # breadcrumb, e.g. ["Part I. ...", "Chapter 2. ...", "Get the Data"]
    anchor: str
    blocks: list[Block] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.path[-1]

    @property
    def chapter(self) -> str:
        for p in self.path:
            if re.match(r"^(chapter\s+)?\d+[.:]|^chapter\b|^appendix\b", p, re.I):
                return p
        return self.path[0]

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)


@dataclass
class Document:
    title: str
    authors: list[str]
    sections: list[Section]


# ---------------------------------------------------------------- block text

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _block(el: Tag) -> Block | None:
    if el.name == "pre":
        text = el.get_text().strip("\n")
        return Block(text, "code") if text.strip() else None
    if el.name == "table":
        rows = []
        for tr in el.find_all("tr"):
            cells = [_clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if cells:
                rows.append(" | ".join(cells))
        text = "\n".join(rows)
        return Block(text, "text") if text else None
    text = _clean(el.get_text(" "))
    if not text:
        return None
    if el.name in HEADING_TAGS:
        return Block(text, "heading")
    if el.name == "li":
        text = "- " + text
    return Block(text, "text")


def _walk(el: Tag, on_anchor, on_block):
    """Visit elements in document order, reporting anchors and leaf blocks."""
    for child in el.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag) or child.name in ("script", "style", "nav"):
            continue
        if child.get("id"):
            on_anchor(child["id"])
        if child.name in BLOCK_TAGS and not (
            child.name == "li" and child.find(["pre", "table", "p"])
        ):
            # anchors nested inside a block (rare) still switch sections
            for inner in child.find_all(id=True):
                on_anchor(inner["id"])
            b = _block(child)
            if b:
                on_block(b)
        else:
            _walk(child, on_anchor, on_block)


# ---------------------------------------------------------------------- EPUB

def _flatten_toc(toc, trail=()):
    import ebooklib.epub as epub
    for item in toc:
        if isinstance(item, tuple):
            head, children = item
            title = _clean(head.title or "")
            yield title, head.href, (*trail, title)
            yield from _flatten_toc(children, (*trail, title))
        elif isinstance(item, epub.Link):
            title = _clean(item.title or "")
            yield title, item.href, (*trail, title)


def parse_epub(path: Path) -> Document:
    import ebooklib
    from ebooklib import epub

    book = epub.read_epub(str(path), {"ignore_ncx": False})
    title = (book.get_metadata("DC", "title") or [[path.stem]])[0][0]
    authors = [a[0] for a in book.get_metadata("DC", "creator")]

    # TOC entries grouped by file, keyed by anchor
    entries: list[tuple[str, str, str, tuple]] = []  # (file, anchor, title, path)
    for t, href, trail in _flatten_toc(book.toc):
        f, _, anchor = unquote(href).partition("#")
        entries.append((f.split("/")[-1], anchor, t, trail))
    by_file: dict[str, list] = {}
    for f, anchor, t, trail in entries:
        by_file.setdefault(f, []).append((anchor, trail))

    sections: list[Section] = []
    current: Section | None = None

    def start(trail):
        nonlocal current
        current = Section(list(trail), "")
        sections.append(current)

    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        fname = item.get_name().split("/")[-1]
        file_entries = by_file.get(fname, [])
        anchors = {a: trail for a, trail in file_entries if a}
        # a TOC entry with no anchor starts at the top of its file
        top = next((trail for a, trail in file_entries if not a), None)
        if top is not None:
            start(top)
        elif file_entries and not anchors:
            start(file_entries[0][1])

        soup = BeautifulSoup(item.get_content(), "lxml")
        body = soup.body or soup

        def on_anchor(a):
            if a in anchors:
                start(anchors.pop(a))
                current.anchor = a

        def on_block(b):
            if current is not None:
                current.blocks.append(b)

        _walk(body, on_anchor, on_block)

    kept = []
    for s in sections:
        if any(SKIP_TITLES.match(p) for p in s.path):
            continue
        # drop opening blocks that just repeat the section title or number
        # (e.g. Learning Git's "Chapter 11 . Rebasing" / "[ 11 ]" / "Rebasing")
        title_key = _key(s.title)
        while s.blocks and (s.blocks[0].kind == "heading" or (
                s.blocks[0].words <= 5 and _key(s.blocks[0].text) in title_key)):
            s.blocks.pop(0)
        if s.blocks:
            kept.append(s)
    return Document(title, authors, kept)


# ------------------------------------------------------------------- article

def parse_article(path: Path) -> Document:
    """An HTML page or Markdown file; sections are split at h2 (or '## ')."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".md", ".markdown"):
        return _parse_markdown(raw, path)
    soup = BeautifulSoup(raw, "lxml")
    meta_title = soup.find("meta", property="og:title")
    title = (meta_title.get("content") if meta_title else None) or (
        soup.title.get_text(strip=True) if soup.title else path.stem)
    author_meta = soup.find("meta", attrs={"name": "author"})
    authors = [author_meta["content"]] if author_meta and author_meta.get("content") else []
    root = soup.find("article") or soup.find("main") or soup.body or soup
    for junk in root.find_all(["nav", "header", "footer", "aside", "form", "script", "style"]):
        junk.decompose()

    sections = [Section([title], "")]

    def on_anchor(_):
        pass

    def on_block(b):
        if b.kind == "heading" and b.text != title and len(b.text) < 120:
            sections.append(Section([title, b.text], ""))
        elif b.kind != "heading":
            sections[-1].blocks.append(b)

    _walk(root, on_anchor, on_block)
    return Document(title, authors, [s for s in sections if s.blocks])


def _parse_markdown(raw: str, path: Path) -> Document:
    fm = {}
    if raw.startswith("---"):
        head, _, raw = raw[3:].partition("\n---")
        for line in head.splitlines():
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("\"'")
    title = fm.get("title") or path.stem
    authors = [fm["author"]] if fm.get("author") else []
    sections = [Section([title], "")]
    para: list[str] = []
    in_code = False

    def flush(kind="text"):
        if para:
            text = "\n".join(para).strip()
            if text:
                sections[-1].blocks.append(Block(text, kind))
            para.clear()

    for line in raw.splitlines():
        if line.startswith("```"):
            if in_code:
                para.append(line)
                flush("code")
            else:
                flush()
                para.append(line)
            in_code = not in_code
        elif in_code:
            para.append(line)
        elif m := re.match(r"^#{1,3}\s+(.*)", line):
            flush()
            h = m.group(1).strip()
            if h != title:
                sections.append(Section([title, h], ""))
        elif not line.strip():
            flush()
        else:
            para.append(line)
    flush("code" if in_code else "text")
    return Document(title, authors, [s for s in sections if s.blocks])


# ------------------------------------------------------------------ passages

def split_passages(section: Section) -> list[str]:
    """Group a section's blocks into passages of roughly TARGET_WORDS."""
    passages: list[list[Block]] = []
    cur: list[Block] = []
    n = 0
    for b in section.blocks:
        if cur and n + b.words > MAX_WORDS:
            # a trailing heading moves forward with the text it introduces
            carry = []
            while cur and cur[-1].kind == "heading":
                carry.insert(0, cur.pop())
            if cur:
                passages.append(cur)
            cur, n = carry, sum(x.words for x in carry)
        cur.append(b)
        n += b.words
        if n >= TARGET_WORDS and b.kind != "heading":
            passages.append(cur)
            cur, n = [], 0
    if cur:
        if passages and sum(b.words for b in cur) < MIN_TAIL_WORDS:
            passages[-1].extend(cur)
        else:
            passages.append(cur)
    return ["\n\n".join(b.text for b in p) for p in passages]


def parse(path: Path) -> Document:
    if path.suffix.lower() == ".epub":
        return parse_epub(path)
    return parse_article(path)

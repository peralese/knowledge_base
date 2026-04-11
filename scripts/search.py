"""Phase 10 Search Engine: BM25 keyword search over compiled notes.

Indexes all compiled notes and ranks them by relevance to a query using the
Okapi BM25 algorithm. Pure stdlib — no external dependencies.

Usable directly from the CLI for human browsing, and imported by query.py
to narrow context to relevant notes before calling the LLM.

Usage:
    # Search and print ranked results
    python3 scripts/search.py "kubernetes security fargate"

    # Return top 3 results only
    python3 scripts/search.py "kubernetes security" --top-n 3

    # Search across raw notes as well as compiled
    python3 scripts/search.py "kubernetes" --include-raw

    # Output as JSON (for programmatic use)
    python3 scripts/search.py "kubernetes security" --json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

COMPILED_DIRS = [
    Path("compiled/topics"),
    Path("compiled/concepts"),
    Path("compiled/source_summaries"),
]

RAW_DIRS = [
    Path("raw/articles"),
    Path("raw/notes"),
    Path("raw/pdfs"),
]

# BM25 hyperparameters (standard defaults)
BM25_K1 = 1.5   # term frequency saturation
BM25_B = 0.75   # length normalisation


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------

@dataclass
class Document:
    path: Path
    title: str
    body: str
    layer: str  # "compiled" or "raw"

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass
class SearchResult:
    document: Document
    score: float
    matched_terms: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "for", "from", "has", "have", "he", "her", "his", "how", "i",
    "if", "in", "is", "it", "its", "of", "on", "or", "our", "s",
    "she", "so", "than", "that", "the", "their", "them", "then",
    "there", "they", "this", "to", "was", "we", "were", "what",
    "when", "which", "who", "will", "with", "you", "your",
}


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, remove stop words and short tokens."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]


def _parse_frontmatter_title(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return ""
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return ""
    for line in parts[0].splitlines():
        m = re.match(r'^title:\s*"?([^"]+)"?\s*$', line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _strip_frontmatter(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return normalized.strip()
    parts = normalized.split("\n---\n", 1)
    if len(parts) < 2:
        return normalized.strip()
    return parts[1].strip()


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def load_documents(root: Path, include_raw: bool = False) -> list[Document]:
    """Load compiled (and optionally raw) notes as Documents."""
    docs: list[Document] = []

    for rel_dir in COMPILED_DIRS:
        directory = root / rel_dir
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            title = _parse_frontmatter_title(text) or path.stem.replace("-", " ").title()
            body = _strip_frontmatter(text)
            docs.append(Document(path=path, title=title, body=body, layer="compiled"))

    if include_raw:
        for rel_dir in RAW_DIRS:
            directory = root / rel_dir
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.md")):
                text = path.read_text(encoding="utf-8", errors="replace")
                title = _parse_frontmatter_title(text) or path.stem.replace("-", " ").title()
                body = _strip_frontmatter(text)
                docs.append(Document(path=path, title=title, body=body, layer="raw"))

    return docs


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------

@dataclass
class BM25Index:
    documents: list[Document]
    # term → {doc_index → term_frequency}
    inverted: dict[str, dict[int, int]]
    doc_lengths: list[int]
    avg_length: float
    doc_count: int


def build_index(documents: list[Document]) -> BM25Index:
    """Build a BM25 index from a list of documents."""
    inverted: dict[str, dict[int, int]] = {}
    doc_lengths: list[int] = []

    for idx, doc in enumerate(documents):
        # Index title tokens with a boost (repeat them 3x to weight title matches)
        tokens = tokenize(doc.title) * 3 + tokenize(doc.body)
        doc_lengths.append(len(tokens))
        counts = Counter(tokens)
        for term, freq in counts.items():
            inverted.setdefault(term, {})[idx] = freq

    avg_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0

    return BM25Index(
        documents=documents,
        inverted=inverted,
        doc_lengths=doc_lengths,
        avg_length=avg_length,
        doc_count=len(documents),
    )


def bm25_score(term: str, doc_idx: int, index: BM25Index) -> float:
    """Compute BM25 score for a single term against a single document."""
    postings = index.inverted.get(term, {})
    df = len(postings)
    if df == 0:
        return 0.0

    tf = postings.get(doc_idx, 0)
    if tf == 0:
        return 0.0

    idf = math.log((index.doc_count - df + 0.5) / (df + 0.5) + 1)
    dl = index.doc_lengths[doc_idx]
    norm_tf = (tf * (BM25_K1 + 1)) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * dl / index.avg_length))
    return idf * norm_tf


def search(query: str, index: BM25Index, top_n: int = 5) -> list[SearchResult]:
    """Search the index and return top_n results ranked by BM25 score."""
    query_terms = tokenize(query)
    if not query_terms:
        return []

    scores: dict[int, float] = {}
    term_hits: dict[int, set[str]] = {}

    for term in query_terms:
        for doc_idx in index.inverted.get(term, {}):
            scores[doc_idx] = scores.get(doc_idx, 0.0) + bm25_score(term, doc_idx, index)
            term_hits.setdefault(doc_idx, set()).add(term)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return [
        SearchResult(
            document=index.documents[idx],
            score=round(score, 4),
            matched_terms=sorted(term_hits.get(idx, set())),
        )
        for idx, score in ranked
        if score > 0
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_results(results: list[SearchResult], query: str) -> None:
    if not results:
        print(f"No results for: {query!r}")
        return
    print(f"Results for: {query!r}\n")
    for rank, result in enumerate(results, 1):
        doc = result.document
        layer_label = f"[{doc.layer}]"
        print(f"  {rank}. {doc.title}  {layer_label}")
        print(f"     {doc.path.name}  (score: {result.score})")
        print(f"     Terms: {', '.join(result.matched_terms)}")
        print()


def _print_json(results: list[SearchResult]) -> None:
    output = [
        {
            "rank": rank,
            "stem": r.document.stem,
            "title": r.document.title,
            "path": str(r.document.path),
            "layer": r.document.layer,
            "score": r.score,
            "matched_terms": r.matched_terms,
        }
        for rank, r in enumerate(results, 1)
    ]
    print(json.dumps(output, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 10 Search: BM25 keyword search over compiled notes."
    )
    parser.add_argument("query", help="Search query string.")
    parser.add_argument(
        "--top-n", type=int, default=5,
        help="Maximum number of results to return. Default: 5",
    )
    parser.add_argument(
        "--include-raw", action="store_true",
        help="Also search raw notes in addition to compiled notes.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output results as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    docs = load_documents(ROOT, include_raw=args.include_raw)
    if not docs:
        print("Error: no notes found to index.", file=sys.stderr)
        return 1

    index = build_index(docs)
    results = search(args.query, index, top_n=args.top_n)

    if args.as_json:
        _print_json(results)
    else:
        _print_results(results, args.query)

    return 0


if __name__ == "__main__":
    sys.exit(main())

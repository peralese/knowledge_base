"""2D-1 — Query Latency Benchmark.

Establishes an honest performance baseline for BM25 retrieval and (optionally)
end-to-end Ollama synthesis latency. No answer files are written. Safe to
re-run at any time to track performance over time.

Usage:
    # BM25 retrieval timing only (fast, no Ollama calls)
    python3 scripts/benchmark_query.py

    # Full end-to-end including Ollama synthesis
    python3 scripts/benchmark_query.py --full

    # Fewer Ollama runs (default: 3 per query type when --full)
    python3 scripts/benchmark_query.py --full --runs 1

    # Save results to custom path (default: outputs/benchmarks/TIMESTAMP-query.json)
    python3 scripts/benchmark_query.py --output path/to/results.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
OLLAMA_BASE_URL = "http://localhost:11434"
BENCHMARKS_DIR = ROOT / "outputs" / "benchmarks"

# ---------------------------------------------------------------------------
# Query test sets — tuned to the actual KB corpus topics
# ---------------------------------------------------------------------------

# Queries that use exact terms from note content
EXACT_KEYWORD_QUERIES = [
    "zero trust docker isolation",
    "openclaw security risks checklist",
    "soul.md permission boundaries",
]

# Queries phrased differently from note content (semantic mismatch)
SEMANTIC_QUERIES = [
    "how do AI agents manage their memory over time",
    "what prevents a local model from accessing files it should not see",
    "strategies for ensuring LLM output quality",
]

# Short broad queries that match many notes
BROAD_QUERIES = [
    "security",
    "agents",
    "knowledge",
]

# Topic-scoped queries (--topic flag on the KB's query CLI)
SCOPED_QUERIES = [
    ("what are the biggest security risks", "openclaw-security"),
    ("what is covered in this knowledge base", "llm-knowledge-bases"),
]

# Queries very unlikely to match anything in the corpus
EMPTY_QUERIES = [
    "quantum cryptography lattice-based post-quantum",
    "marine biology coral reef biodiversity",
]


# ---------------------------------------------------------------------------
# BM25 retrieval (no Ollama)
# ---------------------------------------------------------------------------

def _bm25_retrieval_latencies(queries: list[str], runs: int, root: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).parent))
    from search import build_index, load_documents, search as bm25_search  # noqa: PLC0415

    docs = load_documents(root, include_raw=False)
    if not docs:
        return {"error": "no compiled documents found"}

    index = build_index(docs)

    latencies_ms: list[float] = []
    result_counts: list[int] = []

    for q in queries:
        for _ in range(runs):
            t0 = time.perf_counter()
            results = bm25_search(q, index, top_n=10)
            elapsed = (time.perf_counter() - t0) * 1000
            latencies_ms.append(elapsed)
            result_counts.append(len(results))

    return {
        "runs": len(latencies_ms),
        "avg_ms": round(sum(latencies_ms) / len(latencies_ms), 3) if latencies_ms else 0,
        "min_ms": round(min(latencies_ms), 3) if latencies_ms else 0,
        "max_ms": round(max(latencies_ms), 3) if latencies_ms else 0,
        "p95_ms": round(_percentile(latencies_ms, 95), 3) if latencies_ms else 0,
        "avg_results": round(sum(result_counts) / len(result_counts), 1) if result_counts else 0,
    }


def _percentile(data: list[float], p: int) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = math.ceil(p / 100.0 * len(sorted_data)) - 1
    return sorted_data[max(0, idx)]


# ---------------------------------------------------------------------------
# Ollama end-to-end (optional)
# ---------------------------------------------------------------------------

def _is_substantive(response: str) -> bool:
    """Heuristic: answer is substantive if it is long enough and not a refusal."""
    if len(response.strip()) < 200:
        return False
    refusals = [
        "i don't know", "i cannot", "i do not have", "no information",
        "not enough information", "cannot answer", "context does not",
        "not provided", "i'm unable",
    ]
    lower = response.lower()
    return not any(r in lower for r in refusals)


def _call_ollama_no_stream(prompt: str, model: str, timeout: int = 90) -> str:
    """Call Ollama for synthesis without persisting any answer file."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return str(data.get("response", ""))


def _build_prompt_for_query(question: str, root: Path, topic: str = "") -> str:
    sys.path.insert(0, str(Path(__file__).parent))
    from query_engine import build_query_prompt, load_context  # noqa: PLC0415

    context, _ = load_context(topic or None, root)
    if not context:
        context = "[No context loaded]"
    return build_query_prompt(question, context)


def _end_to_end_latencies(
    queries: list[str | tuple],
    runs: int,
    model: str,
    root: Path,
    scoped: bool = False,
) -> dict:
    latencies_ms: list[float] = []
    substantive_count = 0
    total = 0

    for q in queries:
        question = q[0] if isinstance(q, tuple) else q
        topic = q[1] if isinstance(q, tuple) else ""

        for _ in range(runs):
            t0 = time.perf_counter()
            try:
                prompt = _build_prompt_for_query(question, root, topic)
                response = _call_ollama_no_stream(prompt, model)
                elapsed = (time.perf_counter() - t0) * 1000
                latencies_ms.append(elapsed)
                if _is_substantive(response):
                    substantive_count += 1
                total += 1
            except (URLError, OSError, TimeoutError) as exc:
                sys.stderr.write(f"  Ollama call failed: {exc}\n")

    if not latencies_ms:
        return {"error": "all Ollama calls failed"}

    return {
        "runs": len(latencies_ms),
        "avg_ms": round(sum(latencies_ms) / len(latencies_ms), 1),
        "min_ms": round(min(latencies_ms), 1),
        "max_ms": round(max(latencies_ms), 1),
        "substantive_rate": f"{substantive_count}/{total}",
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt_row(label: str, stats: dict) -> str:
    if "error" in stats:
        return f"  {label:<24} ERROR: {stats['error']}"
    runs = stats.get("runs", 0)
    avg = stats.get("avg_ms", 0)
    mn = stats.get("min_ms", 0)
    mx = stats.get("max_ms", 0)
    sub = stats.get("substantive_rate", "—")
    return (
        f"  {label:<24} {runs:<6} {avg:<10.1f} {mn:<10.1f} {mx:<10.1f} {sub}"
    )


def _print_report(results: dict, include_ollama: bool) -> None:
    ts = results["timestamp"]
    corpus = results["corpus"]
    print(f"\nQuery Latency Benchmark — {results['date']}")
    print(f"Timestamp: {ts}")
    print(f"Corpus: {corpus['topics']} topics, {corpus['concepts']} concepts, "
          f"{corpus['entities']} entities, {corpus['source_summaries']} source summaries "
          f"= {corpus['total']} total indexed notes")
    print()
    print(f"  {'Query type':<24} {'Runs':<6} {'Avg (ms)':<10} {'Min (ms)':<10} "
          f"{'Max (ms)':<10} {'Substantive'}")
    print("  " + "-" * 80)

    bm25 = results.get("bm25_only", {})
    for label, key in [
        ("Exact keyword (BM25)", "exact_keyword"),
        ("Semantic (BM25)", "semantic"),
        ("Broad (BM25)", "broad"),
        ("Scoped (BM25)", "scoped"),
        ("Empty corpus (BM25)", "empty"),
    ]:
        if key in bm25:
            print(_fmt_row(label, bm25[key]))

    if include_ollama:
        print()
        e2e = results.get("end_to_end", {})
        for label, key in [
            ("Exact (end-to-end)", "exact_keyword"),
            ("Semantic (end-to-end)", "semantic"),
            ("Broad (end-to-end)", "broad"),
            ("Scoped (end-to-end)", "scoped"),
            ("Empty (end-to-end)", "empty"),
        ]:
            if key in e2e:
                print(_fmt_row(label, e2e[key]))

    print()
    assessment = results.get("assessment", {})
    print("Assessment:")
    for line in assessment.get("lines", []):
        print(f"  {line}")
    print()


def _build_assessment(bm25_results: dict, e2e_results: dict | None, corpus: dict) -> dict:
    lines: list[str] = []
    total_notes = corpus["total"]

    # BM25 speed assessment
    all_bm25_avgs = [v["avg_ms"] for v in bm25_results.values() if isinstance(v, dict) and "avg_ms" in v]
    max_bm25_avg = max(all_bm25_avgs) if all_bm25_avgs else 0
    if max_bm25_avg < 1:
        lines.append(f"BM25 retrieval is extremely fast (<1ms avg) on a {total_notes}-note corpus.")
        lines.append("Bottleneck is Ollama synthesis, not retrieval.")
    elif max_bm25_avg < 50:
        lines.append(f"BM25 retrieval is fast (<50ms avg) on a {total_notes}-note corpus.")
    else:
        lines.append(f"BM25 retrieval at {max_bm25_avg:.0f}ms avg — consider optimization.")

    if total_notes < 100:
        lines.append(
            f"Corpus is small ({total_notes} notes < 100 threshold). "
            "Latency case for vector retrieval is weak at this scale."
        )

    # Semantic gap assessment
    if e2e_results:
        semantic = e2e_results.get("semantic", {})
        exact = e2e_results.get("exact_keyword", {})
        sem_rate = semantic.get("substantive_rate", "0/0")
        ex_rate = exact.get("substantive_rate", "0/0")
        try:
            sem_n, sem_d = (int(x) for x in sem_rate.split("/"))
            ex_n, ex_d = (int(x) for x in ex_rate.split("/"))
            if sem_d > 0 and ex_d > 0 and (sem_n / sem_d) < (ex_n / ex_d) - 0.1:
                lines.append(
                    f"Semantic substantive rate ({sem_rate}) meaningfully lower than "
                    f"exact keyword ({ex_rate}). Vector retrieval is warranted for "
                    "semantic recall improvement."
                )
            else:
                lines.append(
                    f"Semantic and exact rates are comparable ({sem_rate} vs {ex_rate}). "
                    "Vector retrieval would be a minor improvement at this corpus size."
                )
        except (ValueError, ZeroDivisionError):
            pass

    # Projection
    bm25_p95 = max(
        (v.get("p95_ms", 0) for v in bm25_results.values() if isinstance(v, dict)),
        default=0,
    )
    projected_3x = bm25_p95 * 3
    lines.append(
        f"Projected BM25 at 3× corpus ({total_notes * 3} notes): "
        f"~{projected_3x:.1f}ms (p95). Still negligible vs Ollama synthesis."
    )
    lines.append(
        "Recommendation: implement vector index for semantic recall quality "
        "improvement, not latency. sqlite-vec preferred over FAISS at this scale."
    )

    return {"lines": lines}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_benchmark(
    root: Path = ROOT,
    include_ollama: bool = False,
    runs: int = 10,
    ollama_runs: int = 3,
    model: str = "qwen2.5:7b",
    output_path: Path | None = None,
) -> dict:
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H%M%S")
    today = now.strftime("%Y-%m-%d")

    # Corpus size
    corpus = {
        "topics": len(list((root / "compiled" / "topics").glob("*.md"))) if (root / "compiled" / "topics").exists() else 0,
        "concepts": len(list((root / "compiled" / "concepts").glob("*.md"))) if (root / "compiled" / "concepts").exists() else 0,
        "entities": len(list((root / "compiled" / "entities").glob("*.md"))) if (root / "compiled" / "entities").exists() else 0,
        "source_summaries": len(list((root / "compiled" / "source_summaries").glob("*.md"))) if (root / "compiled" / "source_summaries").exists() else 0,
    }
    corpus["total"] = sum(corpus.values())

    print(f"Benchmark — BM25 retrieval ({runs} runs per query type)")
    print(f"Corpus: {corpus['total']} notes")

    bm25_results: dict = {}
    for label, queries, scoped in [
        ("exact_keyword", EXACT_KEYWORD_QUERIES, False),
        ("semantic", SEMANTIC_QUERIES, False),
        ("broad", BROAD_QUERIES, False),
        ("scoped", [q[0] for q in SCOPED_QUERIES], True),
        ("empty", EMPTY_QUERIES, False),
    ]:
        print(f"  BM25 {label}...", end=" ", flush=True)
        bm25_results[label] = _bm25_retrieval_latencies(queries, runs, root)
        avg = bm25_results[label].get("avg_ms", 0)
        print(f"{avg:.3f}ms avg")

    e2e_results: dict | None = None
    if include_ollama:
        print(f"\nBenchmark — end-to-end with Ollama ({model}, {ollama_runs} runs per type)")
        e2e_results = {}
        for label, queries in [
            ("exact_keyword", EXACT_KEYWORD_QUERIES),
            ("semantic", SEMANTIC_QUERIES),
            ("broad", BROAD_QUERIES),
            ("scoped", SCOPED_QUERIES),
            ("empty", EMPTY_QUERIES),
        ]:
            print(f"  E2E {label}...", end=" ", flush=True)
            e2e_results[label] = _end_to_end_latencies(queries, ollama_runs, model, root)
            avg = e2e_results[label].get("avg_ms", 0)
            rate = e2e_results[label].get("substantive_rate", "?")
            print(f"{avg:.0f}ms avg  substantive: {rate}")

    assessment = _build_assessment(bm25_results, e2e_results, corpus)

    results = {
        "date": today,
        "timestamp": timestamp,
        "corpus": corpus,
        "model": model if include_ollama else None,
        "bm25_only": bm25_results,
        "end_to_end": e2e_results,
        "assessment": assessment,
    }

    # Save JSON snapshot
    save_dir = output_path.parent if output_path else BENCHMARKS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_path or (save_dir / f"{timestamp}-query.json")
    out_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    _print_report(results, include_ollama)
    print(f"Results saved: {out_path.relative_to(root)}")

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2D-1 Query Latency Benchmark. Measures BM25 and optionally Ollama synthesis latency."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include end-to-end Ollama synthesis timing (slow — adds Ollama calls per query type).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of BM25 runs per query type. Default: 10",
    )
    parser.add_argument(
        "--ollama-runs",
        type=int,
        default=3,
        dest="ollama_runs",
        help="Number of Ollama synthesis runs per query type (only with --full). Default: 3",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5:7b",
        help="Ollama model for synthesis timing (only with --full). Default: qwen2.5:7b",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Custom output path for JSON results. Default: outputs/benchmarks/TIMESTAMP-query.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_benchmark(
        root=ROOT,
        include_ollama=args.full,
        runs=args.runs,
        ollama_runs=args.ollama_runs,
        model=args.model,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Phase 5 LLM Driver: call a local Ollama model with a prompt-pack and file the result.

Usage:
    python3 scripts/llm_driver.py \\
        --prompt-pack metadata/prompts/compile-openclaw-security.md \\
        --output-type compiled

The driver:
  1. Reads the prompt-pack produced by compile_notes.py
  2. Sends it to the Ollama REST API (streaming)
  3. Writes raw output to tmp/synthesis-output.md for inspection
  4. Passes the output through apply_synthesis to create a durable artifact
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "qwen2.5:14b"
OLLAMA_BASE_URL = "http://localhost:11434"
TMP_OUTPUT = ROOT / "tmp" / "synthesis-output.md"


# ---------------------------------------------------------------------------
# Ollama API
# ---------------------------------------------------------------------------

def _check_model_available(model: str) -> None:
    """Raise a clear error if the requested model is not pulled in Ollama."""
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/tags",
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except URLError as exc:
        raise ConnectionError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. Is it running?\n"
            "  Start with: ollama serve"
        ) from exc

    available = [m.get("name", "") for m in data.get("models", [])]
    if model not in available:
        available_str = ", ".join(available) if available else "(none pulled)"
        raise ValueError(
            f"Model '{model}' is not available in Ollama.\n"
            f"  Available: {available_str}\n"
            f"  Pull with: ollama pull {model}"
        )


def call_ollama(prompt: str, model: str) -> str:
    """Send prompt to Ollama /api/generate with streaming; return full response text."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    chunks: list[str] = []
    with urllib.request.urlopen(req) as resp:
        for raw_line in resp:
            line = raw_line.strip()
            if not line:
                continue
            data = json.loads(line)
            token = data.get("response", "")
            if token:
                print(token, end="", flush=True)
                chunks.append(token)
            if data.get("done"):
                break

    print()  # trailing newline after streamed output
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(
    prompt_pack: Path,
    model: str,
    output_type: str,
    title_override: str,
    force: bool,
) -> int:
    prompt_pack_path = ROOT / prompt_pack if not prompt_pack.is_absolute() else prompt_pack

    if not prompt_pack_path.exists():
        print(f"Error: prompt-pack not found: {prompt_pack_path}", file=sys.stderr)
        return 1

    # Validate model before spending time on anything else
    try:
        _check_model_available(model)
    except (ConnectionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    prompt = prompt_pack_path.read_text(encoding="utf-8")
    print(f"Model       : {model}")
    print(f"Prompt-pack : {prompt_pack_path.name}  ({len(prompt):,} chars)")
    print(f"Output type : {output_type}")
    print("-" * 60)

    try:
        synthesized = call_ollama(prompt, model)
    except URLError as exc:
        print(f"Error: Ollama request failed: {exc}", file=sys.stderr)
        return 1

    print("-" * 60)

    # Persist raw output so it can be inspected or retried
    TMP_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TMP_OUTPUT.write_text(synthesized, encoding="utf-8")
    print(f"Raw output  : {TMP_OUTPUT.relative_to(ROOT)}")

    # Apply synthesis
    sys.path.insert(0, str(Path(__file__).parent))
    from apply_synthesis import apply_synthesis, ApplySynthesisRequest  # noqa: PLC0415

    try:
        output_path = apply_synthesis(
            ApplySynthesisRequest(
                prompt_pack=prompt_pack_path,
                synthesized_file=TMP_OUTPUT,
                output_type=output_type,
                title_override=title_override,
                force=force,
                generation_method="ollama_local",
                root=ROOT,
            )
        )
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error applying synthesis: {exc}", file=sys.stderr)
        return 1

    print(f"Artifact    : {output_path.relative_to(ROOT)}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 5 LLM Driver: send a prompt-pack to Ollama and file the result."
    )
    parser.add_argument(
        "--prompt-pack",
        type=Path,
        required=True,
        help="Path to a Phase 3 prompt-pack (relative to repo root or absolute).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--output-type",
        default="compiled",
        choices=["compiled", "answer", "report"],
        help="Artifact type to create. Default: compiled",
    )
    parser.add_argument(
        "--title",
        dest="title_override",
        default="",
        help="Optional title override (passed to apply_synthesis).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the destination artifact if it already exists.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        prompt_pack=args.prompt_pack,
        model=args.model,
        output_type=args.output_type,
        title_override=args.title_override,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX_ROOT = ROOT / "raw" / "inbox"
ADAPTER_DIRS = {
    "browser": INBOX_ROOT / "browser",
    "clipboard": INBOX_ROOT / "clipboard",
    "feeds": INBOX_ROOT / "feeds",
    "pdf-drop": INBOX_ROOT / "pdf-drop",
}


@dataclass
class StageRequest:
    adapter: str
    title: str = ""
    text: str = ""
    canonical_url: str = ""
    input_file: Path | None = None
    root: Path = ROOT


def slugify_title(title: str) -> str:
    slug = title.strip().lower()
    slug = "".join(character if character.isalnum() else "-" for character in slug)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "staged-input"


def ensure_adapter_dir(adapter: str, root: Path) -> Path:
    directory = root / "raw" / "inbox" / adapter
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _frontmatter(title: str, canonical_url: str) -> str:
    lines = ["---", f'title: "{title.replace(chr(34), chr(39))}"']
    if canonical_url.strip():
        lines.append(f'canonical_url: "{canonical_url.replace(chr(34), chr(39))}"')
    lines.append("---")
    return "\n".join(lines)


def stage_clipboard(request: StageRequest) -> Path:
    if not request.text.strip():
        raise ValueError("Clipboard staging requires --text or stdin content.")
    title = request.title.strip() or "Clipboard Capture"
    body = request.text.strip()
    directory = ensure_adapter_dir("clipboard", request.root)
    destination = directory / f"{slugify_title(title)}.md"
    destination.write_text(
        f"{_frontmatter(title, request.canonical_url)}\n\n{body}\n",
        encoding="utf-8",
    )
    return destination


def stage_browser(request: StageRequest) -> Path:
    if request.input_file is None:
        raise ValueError("Browser staging requires --input-file.")
    if not request.input_file.exists():
        raise FileNotFoundError(f"Input file not found: {request.input_file}")
    directory = ensure_adapter_dir("browser", request.root)

    if request.input_file.suffix.lower() in {".md", ".txt", ".html"} and request.title.strip():
        text = request.input_file.read_text(encoding="utf-8", errors="replace")
        extension = ".md" if request.input_file.suffix.lower() == ".md" else request.input_file.suffix.lower()
        destination = directory / f"{slugify_title(request.title)}{extension or '.md'}"
        destination.write_text(
            f"{_frontmatter(request.title.strip(), request.canonical_url)}\n\n{text.strip()}\n",
            encoding="utf-8",
        )
        return destination

    destination = directory / request.input_file.name
    shutil.copy2(request.input_file, destination)
    return destination


def stage_feed(request: StageRequest) -> Path:
    directory = ensure_adapter_dir("feeds", request.root)
    payload: dict[str, object]

    if request.input_file is not None:
        if not request.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {request.input_file}")
        payload = json.loads(request.input_file.read_text(encoding="utf-8"))
    else:
        if not request.text.strip():
            raise ValueError("Feed staging requires --input-file or --text JSON.")
        payload = json.loads(request.text)

    if not isinstance(payload, dict):
        raise ValueError("Feed payload must be a JSON object.")

    title = str(payload.get("title", "")).strip() or request.title.strip() or "Feed Item"
    canonical_url = str(payload.get("canonical_url") or payload.get("url") or payload.get("link") or request.canonical_url).strip()
    content = str(payload.get("content") or payload.get("summary") or payload.get("body") or "").strip()

    destination = directory / f"{slugify_title(title)}.json"
    destination.write_text(
        json.dumps(
            {
                "title": title,
                "canonical_url": canonical_url,
                "content": content,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def stage_pdf(request: StageRequest) -> Path:
    if request.input_file is None:
        raise ValueError("PDF staging requires --input-file.")
    if not request.input_file.exists():
        raise FileNotFoundError(f"Input file not found: {request.input_file}")
    directory = ensure_adapter_dir("pdf-drop", request.root)
    destination = directory / request.input_file.name
    shutil.copy2(request.input_file, destination)
    return destination


def stage(request: StageRequest) -> Path:
    adapter = request.adapter.strip().lower()
    if adapter == "clipboard":
        return stage_clipboard(request)
    if adapter == "browser":
        return stage_browser(request)
    if adapter == "feeds":
        return stage_feed(request)
    if adapter == "pdf-drop":
        return stage_pdf(request)
    raise ValueError(f"Unsupported adapter: {request.adapter}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage browser, clipboard, feed, or PDF inputs into raw/inbox adapter folders."
    )
    parser.add_argument(
        "adapter",
        choices=sorted(ADAPTER_DIRS),
        help="Inbox adapter destination: browser, clipboard, feeds, or pdf-drop.",
    )
    parser.add_argument("--title", default="", help="Optional title for staged markdown/json wrappers.")
    parser.add_argument("--text", default="", help="Direct text or JSON payload to stage.")
    parser.add_argument("--canonical-url", default="", help="Optional canonical URL metadata.")
    parser.add_argument("--input-file", type=Path, help="Optional input file to stage.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    staged_text = args.text
    if not staged_text and not sys.stdin.isatty():
        staged_text = sys.stdin.read()

    destination = stage(
        StageRequest(
            adapter=args.adapter,
            title=args.title,
            text=staged_text,
            canonical_url=args.canonical_url,
            input_file=args.input_file,
            root=ROOT,
        )
    )
    print(f"Staged      : {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

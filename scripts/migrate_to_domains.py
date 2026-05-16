from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))

from domains import DEFAULT_DOMAIN_SLUG, create_domain, ensure_domain_dirs, get_domain  # noqa: E402


COPY_PAIRS = [
    ("raw/articles", "raw/domains/{domain}/articles"),
    ("raw/notes", "raw/domains/{domain}/notes"),
    ("raw/pdfs", "raw/domains/{domain}/pdfs"),
    ("raw/archive", "raw/domains/{domain}/archive"),
    ("metadata/prompts", "metadata/domains/{domain}/prompts"),
    ("compiled/topics", "compiled/domains/{domain}/topics"),
    ("compiled/concepts", "compiled/domains/{domain}/concepts"),
    ("compiled/entities", "compiled/domains/{domain}/entities"),
    ("compiled/source_summaries", "compiled/domains/{domain}/source_summaries"),
    ("outputs/answers", "outputs/domains/{domain}/answers"),
]

FILE_PAIRS = [
    ("metadata/source-manifest.json", "metadata/domains/{domain}/source-manifest.json"),
    ("metadata/review-queue.json", "metadata/domains/{domain}/review-queue.json"),
    ("metadata/review-queue.md", "metadata/domains/{domain}/review-queue.md"),
    ("metadata/topic-registry.json", "metadata/domains/{domain}/topic-registry.json"),
    ("metadata/concept-registry.json", "metadata/domains/{domain}/concept-registry.json"),
    ("metadata/entity-registry.json", "metadata/domains/{domain}/entity-registry.json"),
    ("compiled/index.md", "compiled/domains/{domain}/index.md"),
]


def _copy_file(src: Path, dest: Path, apply: bool) -> bool:
    if not src.exists() or dest.exists():
        return False
    if apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return True


def _copy_tree(src: Path, dest: Path, apply: bool) -> int:
    if not src.exists():
        return 0
    copied = 0
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        target = dest / path.relative_to(src)
        if target.exists():
            continue
        copied += 1
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return copied


def run(domain: str, display_name: str, apply: bool, root: Path = ROOT) -> int:
    try:
        resolved = get_domain(domain, root)
    except ValueError:
        if not apply:
            resolved_slug = domain
        else:
            resolved = create_domain(display_name or domain, slug=domain, root=root)
            resolved_slug = resolved.slug
    else:
        resolved_slug = resolved.slug

    ensure_domain_dirs(root, resolved_slug)
    print(f"{'Applying' if apply else 'Planning'} migration into domain: {resolved_slug}")
    print("Existing files are never deleted or overwritten.")

    total = 0
    for src_rel, dest_rel in COPY_PAIRS:
        count = _copy_tree(root / src_rel, root / dest_rel.format(domain=resolved_slug), apply)
        if count:
            total += count
            print(f"  {src_rel} -> {dest_rel.format(domain=resolved_slug)}  ({count} file(s))")

    for src_rel, dest_rel in FILE_PAIRS:
        if _copy_file(root / src_rel, root / dest_rel.format(domain=resolved_slug), apply):
            total += 1
            print(f"  {src_rel} -> {dest_rel.format(domain=resolved_slug)}")

    print(f"\n{'Copied' if apply else 'Would copy'} {total} artifact(s).")
    if not apply:
        print("Run again with --apply to copy files.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy the legacy single-domain KB layout into a domain namespace."
    )
    parser.add_argument("--domain", default=DEFAULT_DOMAIN_SLUG, help=f"Target domain slug. Default: {DEFAULT_DOMAIN_SLUG}.")
    parser.add_argument("--display-name", default="AI", help="Display name if the domain must be created.")
    parser.add_argument("--apply", action="store_true", help="Copy files. Without this flag, only print the plan.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args.domain, args.display_name, args.apply, ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared artifact removal logic for purging a source from the knowledge base.

Used by both ``scripts/review.py purge`` and the dashboard
``DELETE /api/pipeline-status/<source_id>`` endpoint.

The function is deliberately state-agnostic: it removes whatever artifacts
exist without checking whether the source was rejected, missing, or otherwise.
Callers are responsible for enforcing any pre-conditions (e.g. rejected-only).
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from runtime_safety import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).parent))
from domains import DEFAULT_DOMAIN_SLUG, compiled_subdir, metadata_domain_dir, metadata_file  # noqa: E402


def _domain_or_legacy(domain_path: Path, legacy_path: Path) -> Path:
    return domain_path if domain_path.exists() else legacy_path


def purge_source(
    source_id: str,
    root: Path = ROOT,
    *,
    dry_run: bool = False,
    domain: str = DEFAULT_DOMAIN_SLUG,
) -> dict:
    """Remove all artifacts for a source from the knowledge base.

    Deletion order:
      1. Entry in ``metadata/source-manifest.json``
      2. Prompt-pack file in ``metadata/prompts/``
      3. Synthesis file in ``compiled/source_summaries/``
      4. Review-queue entry in ``metadata/review-queue.json``
      5. Raw source file at the path recorded in the manifest

    Returns a dict with keys:
      source_id, title, removed (list), skipped (list),
      dry_run (bool), affected_paths (list[Path]).

    ``affected_paths`` lists every file that was actually modified or deleted
    (empty in dry-run mode).  Pass this to ``commit_pipeline_stage`` after the
    call so git stages all changes in one shot.

    Raises ``ValueError`` if ``source_id`` is not found in the manifest.
    """
    manifest_path = _domain_or_legacy(
        metadata_file(root, domain, "source-manifest.json"),
        root / "metadata" / "source-manifest.json",
    )
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found at {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources: list[dict] = manifest.get("sources", [])
    source = next((s for s in sources if s.get("source_id") == source_id), None)
    if source is None:
        raise ValueError(f"Source '{source_id}' not found in manifest.")

    stem = Path(source.get("filename", "")).stem
    title: str = source.get("title", "")

    removed: list[str] = []
    skipped: list[str] = []
    affected_paths: list[Path] = []

    # 1. Manifest entry
    if not dry_run:
        manifest["sources"] = [s for s in sources if s.get("source_id") != source_id]
        manifest["last_updated"] = date.today().isoformat()
        atomic_write_json(manifest_path, manifest)
        affected_paths.append(manifest_path)
    removed.append(f"{manifest_path.relative_to(root)} entry")

    # 2. Prompt pack
    prompt_pack = _domain_or_legacy(
        metadata_domain_dir(root, domain) / "prompts" / f"compile-{stem}-synthesis.md",
        root / "metadata" / "prompts" / f"compile-{stem}-synthesis.md",
    )
    if prompt_pack.exists():
        if not dry_run:
            prompt_pack.unlink()
            affected_paths.append(prompt_pack)
        removed.append(str(prompt_pack.relative_to(root)))
    else:
        skipped.append(str(prompt_pack.relative_to(root)))

    # 3. Synthesis file
    synthesis = _domain_or_legacy(
        compiled_subdir(root, domain, "source_summaries") / f"{stem}-synthesis.md",
        root / "compiled" / "source_summaries" / f"{stem}-synthesis.md",
    )
    if synthesis.exists():
        if not dry_run:
            synthesis.unlink()
            affected_paths.append(synthesis)
        removed.append(str(synthesis.relative_to(root)))
    else:
        skipped.append(str(synthesis.relative_to(root)))

    # 4. Queue entry
    queue_path = _domain_or_legacy(
        metadata_file(root, domain, "review-queue.json"),
        root / "metadata" / "review-queue.json",
    )
    queue_entry_removed = False
    if queue_path.exists():
        try:
            queue: list[dict] = json.loads(queue_path.read_text(encoding="utf-8"))
            if isinstance(queue, list):
                updated_queue = [e for e in queue if e.get("source_id") != source_id]
                if len(updated_queue) < len(queue):
                    if not dry_run:
                        queue_path.write_text(
                            json.dumps(updated_queue, indent=2) + "\n", encoding="utf-8"
                        )
                        affected_paths.append(queue_path)
                    removed.append(f"{queue_path.relative_to(root)} entry")
                    queue_entry_removed = True
        except (json.JSONDecodeError, OSError):
            pass
    if not queue_entry_removed:
        skipped.append(f"{queue_path.relative_to(root)} entry")

    # 5. Raw source file
    path_rel: str = source.get("path", "")
    if path_rel:
        raw_path = root / path_rel
        if raw_path.exists():
            if not dry_run:
                raw_path.unlink()
                affected_paths.append(raw_path)
            removed.append(path_rel)
        else:
            skipped.append(f"{path_rel} (not found)")

    return {
        "source_id": source_id,
        "title": title,
        "removed": removed,
        "skipped": skipped,
        "dry_run": dry_run,
        "affected_paths": affected_paths,
    }

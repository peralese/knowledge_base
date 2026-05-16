from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOMAINS_PATH = ROOT / "metadata" / "domains.json"
DEFAULT_DOMAIN_SLUG = "ai"


@dataclass
class Domain:
    display_name: str
    slug: str
    description: str = ""
    created_at: str = ""
    active: bool = True


def slugify_domain(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "inbox"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_domain() -> Domain:
    return Domain(
        display_name="AI",
        slug=DEFAULT_DOMAIN_SLUG,
        description="Default domain for the original single-domain knowledge base.",
        created_at=_now(),
        active=True,
    )


def load_domains(root: Path = ROOT) -> list[Domain]:
    path = root / "metadata" / "domains.json"
    if not path.exists():
        return [_default_domain()]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [_default_domain()]
    raw_domains = payload.get("domains", payload if isinstance(payload, list) else [])
    domains: list[Domain] = []
    for item in raw_domains:
        if not isinstance(item, dict):
            continue
        display_name = str(item.get("display_name") or item.get("name") or item.get("slug") or "").strip()
        slug = slugify_domain(str(item.get("slug") or display_name))
        if not display_name or not slug:
            continue
        domains.append(
            Domain(
                display_name=display_name,
                slug=slug,
                description=str(item.get("description", "")),
                created_at=str(item.get("created_at") or _now()),
                active=bool(item.get("active", True)),
            )
        )
    return domains or [_default_domain()]


def save_domains(domains: list[Domain], root: Path = ROOT) -> None:
    path = root / "metadata" / "domains.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "default_domain": DEFAULT_DOMAIN_SLUG,
        "domains": [asdict(domain) for domain in domains],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_domains_file(root: Path = ROOT) -> Path:
    path = root / "metadata" / "domains.json"
    if not path.exists():
        save_domains(load_domains(root), root)
    return path


def get_domain(slug: str | None = None, root: Path = ROOT, *, create: bool = False) -> Domain:
    requested = slugify_domain(slug or default_domain_slug(root))
    domains = load_domains(root)
    for domain in domains:
        if domain.slug == requested and domain.active:
            return domain
    if create:
        return create_domain(requested, root=root)
    raise ValueError(f"Unknown or inactive domain: {requested}")


def create_domain(
    display_name: str,
    *,
    slug: str | None = None,
    description: str = "",
    root: Path = ROOT,
) -> Domain:
    cleaned_name = " ".join(display_name.split()).strip()
    if not cleaned_name:
        raise ValueError("Domain display name is required.")
    requested_slug = slugify_domain(slug or cleaned_name)
    domains = load_domains(root)
    if any(domain.slug == requested_slug for domain in domains):
        raise ValueError(f"Domain slug already exists: {requested_slug}")
    domain = Domain(
        display_name=cleaned_name,
        slug=requested_slug,
        description=description.strip(),
        created_at=_now(),
        active=True,
    )
    domains.append(domain)
    save_domains(domains, root)
    ensure_domain_dirs(root, requested_slug)
    return domain


def default_domain_slug(root: Path = ROOT) -> str:
    path = root / "metadata" / "domains.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            slug = slugify_domain(str(payload.get("default_domain", DEFAULT_DOMAIN_SLUG)))
            if slug:
                return slug
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_DOMAIN_SLUG


def set_default_domain(slug: str, root: Path = ROOT) -> None:
    domain = get_domain(slug, root)
    domains = load_domains(root)
    path = root / "metadata" / "domains.json"
    payload = {
        "version": "1.0",
        "default_domain": domain.slug,
        "domains": [asdict(item) for item in domains],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def raw_domain_dir(root: Path, domain_slug: str) -> Path:
    return root / "raw" / "domains" / slugify_domain(domain_slug)


def metadata_domain_dir(root: Path, domain_slug: str) -> Path:
    return root / "metadata" / "domains" / slugify_domain(domain_slug)


def compiled_domain_dir(root: Path, domain_slug: str) -> Path:
    return root / "compiled" / "domains" / slugify_domain(domain_slug)


def outputs_domain_dir(root: Path, domain_slug: str) -> Path:
    return root / "outputs" / "domains" / slugify_domain(domain_slug)


def indexes_domain_dir(root: Path, domain_slug: str) -> Path:
    return root / "indexes" / "domains" / slugify_domain(domain_slug)


def raw_subdir(root: Path, domain_slug: str, name: str) -> Path:
    return raw_domain_dir(root, domain_slug) / name


def inbox_subdir(root: Path, domain_slug: str, adapter: str) -> Path:
    return raw_domain_dir(root, domain_slug) / "inbox" / adapter


def metadata_file(root: Path, domain_slug: str, filename: str) -> Path:
    return metadata_domain_dir(root, domain_slug) / filename


def compiled_subdir(root: Path, domain_slug: str, name: str) -> Path:
    return compiled_domain_dir(root, domain_slug) / name


def outputs_subdir(root: Path, domain_slug: str, name: str) -> Path:
    return outputs_domain_dir(root, domain_slug) / name


def vector_index_path(root: Path, domain_slug: str) -> Path:
    return indexes_domain_dir(root, domain_slug) / "vector_index.db"


def ensure_domain_dirs(root: Path, domain_slug: str) -> None:
    for directory in [
        raw_subdir(root, domain_slug, "articles"),
        raw_subdir(root, domain_slug, "notes"),
        raw_subdir(root, domain_slug, "pdfs"),
        raw_subdir(root, domain_slug, "archive"),
        inbox_subdir(root, domain_slug, "browser"),
        inbox_subdir(root, domain_slug, "clipboard"),
        inbox_subdir(root, domain_slug, "feeds"),
        inbox_subdir(root, domain_slug, "pdf-drop"),
        metadata_domain_dir(root, domain_slug) / "prompts",
        compiled_subdir(root, domain_slug, "topics"),
        compiled_subdir(root, domain_slug, "concepts"),
        compiled_subdir(root, domain_slug, "entities"),
        compiled_subdir(root, domain_slug, "source_summaries"),
        outputs_subdir(root, domain_slug, "answers"),
        indexes_domain_dir(root, domain_slug),
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def domain_from_path(path: Path, root: Path = ROOT) -> str | None:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    for prefix in ("raw", "metadata", "compiled", "outputs", "indexes"):
        if len(parts) >= 3 and parts[0] == prefix and parts[1] == "domains":
            return parts[2]
    return None


def legacy_or_domain_file(root: Path, domain_slug: str | None, domain_rel: Path, legacy_rel: Path) -> Path:
    if domain_slug:
        candidate = root / domain_rel
        if candidate.exists():
            return candidate
    return root / legacy_rel

"""Deterministic creation of curated article Markdown sources."""

import errno
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from .contract import (
    ArticleValidationError,
    CuratedArticle,
    load_articles,
    normalize_source_domain,
    parse_article_text,
    slugify,
)


@dataclass(frozen=True)
class IngestResult:
    path: Path
    article: CuratedArticle
    sha256: str
    commit_message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "slug": self.article.slug,
            "sha256": self.sha256,
            "commit_message": self.commit_message,
        }


def utc_added_date(now: Optional[datetime] = None) -> str:
    """Return the UTC calendar date used for ``added_date``."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return current.astimezone(timezone.utc).date().isoformat()


def _optional_string(manifest: Mapping[str, Any], field: str) -> Optional[str]:
    value = manifest.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ArticleValidationError(f"{field} must be a string")
    value = value.strip()
    return value or None


def _required_string(manifest: Mapping[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ArticleValidationError(f"{field} must be a non-empty string")
    return value.strip()


def build_article_source(
    manifest: Mapping[str, Any],
    body_md: str,
    *,
    added_date: Optional[str] = None,
) -> tuple[CuratedArticle, str]:
    """Build validated article source text from structured input."""
    if not isinstance(body_md, str) or not body_md.strip():
        raise ArticleValidationError("article body must not be empty")

    title = _required_string(manifest, "title")
    source_url = _required_string(manifest, "source_url")
    published_date = _required_string(manifest, "published_date")
    summary = _required_string(manifest, "summary")
    source_domain = normalize_source_domain(source_url)
    supplied_domain = _optional_string(manifest, "source_domain")
    if supplied_domain and supplied_domain.lower().removeprefix("www.") != source_domain:
        raise ArticleValidationError(
            f"source_domain must be {source_domain!r} for source_url"
        )

    tags = manifest.get("tags") or []
    if not isinstance(tags, list):
        raise ArticleValidationError("tags must be a list")
    slug = slugify(
        source_domain,
        published_date,
        title,
        short_title=_optional_string(manifest, "slug_title"),
    )

    metadata: dict[str, Any] = {
        "title": title,
        "source_url": source_url,
        "source_domain": source_domain,
        "published_date": published_date,
        "added_date": added_date or utc_added_date(),
        "slug": slug,
        "summary": summary,
    }
    if tags:
        metadata["tags"] = tags
    cover = _optional_string(manifest, "cover")
    if cover:
        metadata["cover"] = cover
    intro = _optional_string(manifest, "intro")
    if intro:
        metadata["intro"] = intro

    yaml_text = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()
    source_text = f"---\n{yaml_text}\n---\n\n{body_md.strip()}\n"
    article = parse_article_text(source_text, Path(f"{slug}.md"))
    return article, source_text


def write_article(
    source_dir: Path,
    manifest: Mapping[str, Any],
    body_md: str,
    *,
    added_date: Optional[str] = None,
) -> IngestResult:
    """Validate and atomically create one article without overwriting existing data."""
    article, source_text = build_article_source(
        manifest, body_md, added_date=added_date
    )
    source_dir.mkdir(parents=True, exist_ok=True)

    for existing in load_articles(source_dir):
        if existing.source_url == article.source_url:
            raise ArticleValidationError(
                f"source_url already exists in {existing.slug}.md"
            )

    destination = source_dir / f"{article.slug}.md"
    if destination.exists():
        raise ArticleValidationError(f"article already exists: {destination.name}")

    payload = source_text.encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{article.slug}.", suffix=".tmp", dir=source_dir
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fchmod(handle.fileno(), 0o644)
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ArticleValidationError(
                f"article already exists: {destination.name}"
            ) from exc
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                raise ArticleValidationError(
                    "article source directory does not support atomic creation"
                ) from exc
            raise
    finally:
        temporary.unlink(missing_ok=True)

    try:
        validated = parse_article_text(
            destination.read_text(encoding="utf-8"), destination
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return IngestResult(
        path=destination,
        article=validated,
        sha256=hashlib.sha256(payload).hexdigest(),
        commit_message=f"clip(article): {article.slug}",
    )


def load_manifest(path: Path) -> dict[str, Any]:
    """Read a JSON object used as structured ingest input."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArticleValidationError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArticleValidationError("manifest must contain a JSON object")
    return value

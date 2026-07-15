"""Canonical contract for curated article Markdown sources."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import frontmatter

REQUIRED_FIELDS = (
    "title",
    "source_url",
    "source_domain",
    "published_date",
    "added_date",
    "slug",
    "summary",
)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARKDOWN_IMAGE_RE = re.compile(
    r"(?P<prefix>!\[[^\]]*\]\()(?P<url><[^>]+>|[^)\s]+)(?P<suffix>\s+[^)]*)?\)"
)
SHORT_TITLE_WORD_LIMIT = 6
SHORT_TITLE_CHAR_LIMIT = 64


class ArticleValidationError(ValueError):
    """Raised when an article source violates the curated article contract."""


@dataclass
class CuratedArticle:
    slug: str
    title: str
    source_url: str
    source_domain: str
    published_date: str
    added_date: str
    summary: str
    tags: list[str]
    cover: Optional[str]
    intro: Optional[str]
    body_md: str
    asset_map: dict[str, str] = field(default_factory=dict)


def _require_iso_date(path: Path, field: str, value: object) -> str:
    value_str = str(value)
    if not ISO_DATE_RE.fullmatch(value_str):
        raise ArticleValidationError(
            f"{path.name}: {field} must be ISO YYYY-MM-DD, got {value_str!r}"
        )
    try:
        date_cls.fromisoformat(value_str)
    except ValueError as exc:
        raise ArticleValidationError(
            f"{path.name}: {field} must be ISO YYYY-MM-DD, got {value_str!r}"
        ) from exc
    return value_str


def _require_url(
    path: Path, field: str, value: str, *, allowed_schemes: set[str]
) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in allowed_schemes or not parsed.hostname:
        allowed = "/".join(sorted(allowed_schemes))
        raise ArticleValidationError(
            f"{path.name}: {field} must be an absolute {allowed} URL, got {value!r}"
        )


def normalize_source_domain(source_url: str) -> str:
    """Return the lowercase, IDNA-safe hostname used by the article contract."""
    parsed = urlsplit(str(source_url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ArticleValidationError(
            f"source_url must be an absolute http/https URL, got {source_url!r}"
        )
    try:
        hostname = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise ArticleValidationError(
            f"source_url contains an invalid hostname: {source_url!r}"
        ) from exc
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _slug_words(value: str) -> list[str]:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", ascii_value.lower())


def slugify(
    source_domain: str,
    published_date: str,
    title: str,
    *,
    short_title: Optional[str] = None,
) -> str:
    """Generate the stable contract slug using at most six short-title words."""
    published_date_str = str(published_date)
    if not ISO_DATE_RE.fullmatch(published_date_str):
        raise ArticleValidationError(
            f"published_date must be ISO YYYY-MM-DD, got {published_date!r}"
        )
    try:
        date_part = date_cls.fromisoformat(published_date_str).strftime("%Y%m%d")
    except ValueError as exc:
        raise ArticleValidationError(
            f"published_date must be ISO YYYY-MM-DD, got {published_date!r}"
        ) from exc

    domain_words = _slug_words(source_domain)
    if not domain_words:
        raise ArticleValidationError(f"source_domain cannot form a slug: {source_domain!r}")

    title_words = _slug_words(short_title if short_title is not None else title)
    if not title_words:
        raise ArticleValidationError(
            "slug_title is required when the article title has no ASCII words"
        )
    if short_title is not None and len(title_words) < 2:
        raise ArticleValidationError("slug_title must contain at least two ASCII words")
    title_part = "-".join(title_words[:SHORT_TITLE_WORD_LIMIT])
    title_part = title_part[:SHORT_TITLE_CHAR_LIMIT].rstrip("-")
    if not title_part:
        raise ArticleValidationError("slug_title cannot form a safe slug")
    return "-".join(("-".join(domain_words), date_part, title_part))


def markdown_image_url(match: re.Match[str]) -> str:
    return match.group("url").strip("<>")


def markdown_image_urls(body_md: str) -> list[str]:
    return [markdown_image_url(match) for match in MARKDOWN_IMAGE_RE.finditer(body_md)]


def parse_article_text(text: str, path: Path) -> CuratedArticle:
    """Parse and validate article source text as if it lived at ``path``."""
    post = frontmatter.loads(text)
    meta = post.metadata or {}
    missing = [field for field in REQUIRED_FIELDS if not meta.get(field)]
    if missing:
        raise ArticleValidationError(
            f"{path.name}: missing required field(s): {', '.join(missing)}"
        )

    slug = str(meta["slug"])
    if not SLUG_RE.fullmatch(slug):
        raise ArticleValidationError(
            f"{path.name}: slug must be lowercase ASCII words joined by hyphens"
        )
    if path.stem != slug:
        raise ArticleValidationError(
            f"{path.name}: filename stem must match slug {slug!r}"
        )

    title = str(meta["title"]).strip()
    if not title:
        raise ArticleValidationError(f"{path.name}: title must not be empty")

    source_url = str(meta["source_url"])
    _require_url(path, "source_url", source_url, allowed_schemes={"http", "https"})
    expected_domain = normalize_source_domain(source_url)
    source_domain = str(meta["source_domain"]).lower().rstrip(".")
    if source_domain != expected_domain:
        raise ArticleValidationError(
            f"{path.name}: source_domain must be {expected_domain!r} for source_url"
        )

    cover = str(meta["cover"]) if meta.get("cover") else None
    if cover:
        _require_url(path, "cover", cover, allowed_schemes={"https"})

    body_md = (post.content or "").strip()
    if not body_md:
        raise ArticleValidationError(f"{path.name}: article body must not be empty")
    for image in markdown_image_urls(body_md):
        _require_url(path, "body image", image, allowed_schemes={"https"})

    tags = meta.get("tags") or []
    if not isinstance(tags, list) or any(
        not isinstance(tag, str) or not tag.strip() for tag in tags
    ):
        raise ArticleValidationError(f"{path.name}: tags must be a list of non-empty strings")

    summary = str(meta["summary"]).strip()
    if not summary or "\n" in summary or "\r" in summary:
        raise ArticleValidationError(
            f"{path.name}: summary must be a non-empty single line"
        )

    raw_intro = meta.get("intro")
    intro = (str(raw_intro).strip() or None) if raw_intro else None
    return CuratedArticle(
        slug=slug,
        title=title,
        source_url=source_url,
        source_domain=source_domain,
        published_date=_require_iso_date(path, "published_date", meta["published_date"]),
        added_date=_require_iso_date(path, "added_date", meta["added_date"]),
        summary=summary,
        tags=[tag.strip() for tag in tags],
        cover=cover,
        intro=intro,
        body_md=body_md,
    )


def load_article(path: Path) -> CuratedArticle:
    """Load one curated article source from disk."""
    return parse_article_text(path.read_text(encoding="utf-8"), path)


def load_articles(source_dir: Path) -> list[CuratedArticle]:
    """Scan ``source_dir/*.md`` and return articles sorted by added date."""
    if not source_dir.is_dir():
        return []
    articles = [load_article(path) for path in sorted(source_dir.glob("*.md"))]
    articles.sort(key=lambda article: article.added_date, reverse=True)
    return articles

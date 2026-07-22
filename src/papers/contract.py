"""Canonical contract for Horizon paper close-read Markdown sources."""

import re
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import frontmatter

from ..articles.contract import markdown_image_urls

REQUIRED_FIELDS = (
    "title",
    "original_title",
    "slug",
    "authors",
    "venue",
    "publication_year",
    "paper_url",
    "pdf_url",
    "added_date",
    "paper_license",
    "summary",
    "tags",
)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
ARXIV_ID_RE = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?$", re.IGNORECASE)
REQUIRED_BODY_SECTIONS = ("论文结论与证据边界", "AI 解读")


class PaperValidationError(ValueError):
    """Raised when a paper close-read violates the source contract."""


@dataclass(frozen=True)
class ResearchPaper:
    slug: str
    title: str
    original_title: str
    authors: list[str]
    affiliations: list[str]
    venue: str
    publication_year: int
    paper_url: str
    pdf_url: str
    project_url: Optional[str]
    code_url: Optional[str]
    data_url: Optional[str]
    arxiv_id: Optional[str]
    doi: Optional[str]
    submitted_date: Optional[str]
    revised_date: Optional[str]
    added_date: str
    paper_license: str
    paper_license_url: Optional[str]
    code_license: Optional[str]
    summary: str
    tags: list[str]
    models: list[str]
    benchmarks: list[str]
    body_md: str


def _require_text(path: Path, field: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise PaperValidationError(f"{path.name}: {field} must not be empty")
    return text


def _require_single_line(path: Path, field: str, value: object) -> str:
    text = _require_text(path, field, value)
    if "\n" in text or "\r" in text:
        raise PaperValidationError(f"{path.name}: {field} must be a single line")
    return text


def _require_list(
    path: Path,
    field: str,
    value: object,
    *,
    minimum: int = 0,
    maximum: Optional[int] = None,
) -> list[str]:
    if value is None and minimum == 0:
        return []
    if not isinstance(value, list):
        raise PaperValidationError(f"{path.name}: {field} must be a list")
    items = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PaperValidationError(
                f"{path.name}: {field} must contain only non-empty strings"
            )
        items.append(item.strip())
    if len(items) < minimum:
        raise PaperValidationError(
            f"{path.name}: {field} must contain at least {minimum} item(s)"
        )
    if maximum is not None and len(items) > maximum:
        raise PaperValidationError(
            f"{path.name}: {field} must contain at most {maximum} item(s)"
        )
    if len(items) != len(set(items)):
        raise PaperValidationError(f"{path.name}: {field} must not contain duplicates")
    return items


def _require_iso_date(path: Path, field: str, value: object) -> str:
    value_str = str(value)
    if not ISO_DATE_RE.fullmatch(value_str):
        raise PaperValidationError(
            f"{path.name}: {field} must be ISO YYYY-MM-DD, got {value_str!r}"
        )
    try:
        date_cls.fromisoformat(value_str)
    except ValueError as exc:
        raise PaperValidationError(
            f"{path.name}: {field} must be ISO YYYY-MM-DD, got {value_str!r}"
        ) from exc
    return value_str


def _optional_iso_date(path: Path, field: str, value: object) -> Optional[str]:
    if value in (None, ""):
        return None
    return _require_iso_date(path, field, value)


def _require_https_url(path: Path, field: str, value: object) -> str:
    text = _require_text(path, field, value)
    parsed = urlsplit(text)
    if parsed.scheme != "https" or not parsed.hostname:
        raise PaperValidationError(
            f"{path.name}: {field} must be an absolute https URL, got {text!r}"
        )
    return text


def _optional_https_url(path: Path, field: str, value: object) -> Optional[str]:
    if value in (None, ""):
        return None
    return _require_https_url(path, field, value)


def _require_publication_year(path: Path, value: object) -> int:
    if isinstance(value, bool):
        raise PaperValidationError(f"{path.name}: publication_year must be a year")
    try:
        year = int(value)
    except (TypeError, ValueError) as exc:
        raise PaperValidationError(
            f"{path.name}: publication_year must be a year"
        ) from exc
    if year < 1900 or year > date_cls.today().year + 1:
        raise PaperValidationError(
            f"{path.name}: publication_year must be between 1900 and "
            f"{date_cls.today().year + 1}"
        )
    return year


def _validate_body(path: Path, body_md: str) -> None:
    if re.search(r"^#\s+", body_md, flags=re.MULTILINE):
        raise PaperValidationError(
            f"{path.name}: body must not contain an H1; title comes from frontmatter"
        )
    headings = re.findall(r"^##\s+(.+?)\s*$", body_md, flags=re.MULTILINE)
    normalized_headings = [re.sub(r"^\d+\.\s*", "", heading) for heading in headings]
    for section in REQUIRED_BODY_SECTIONS:
        if not any(
            heading == section or heading.startswith(f"{section}：")
            for heading in normalized_headings
        ):
            raise PaperValidationError(
                f"{path.name}: body must contain a '## {section}' section"
            )
    for image_url in markdown_image_urls(body_md):
        _require_https_url(path, "body image", image_url)


def parse_paper_text(text: str, path: Path) -> ResearchPaper:
    """Parse and validate a paper source as if it lived at ``path``."""
    post = frontmatter.loads(text)
    meta = post.metadata or {}
    missing = [field for field in REQUIRED_FIELDS if not meta.get(field)]
    if missing:
        raise PaperValidationError(
            f"{path.name}: missing required field(s): {', '.join(missing)}"
        )

    slug = str(meta["slug"])
    if not SLUG_RE.fullmatch(slug):
        raise PaperValidationError(
            f"{path.name}: slug must be lowercase ASCII words joined by hyphens"
        )
    if path.stem != slug:
        raise PaperValidationError(
            f"{path.name}: filename stem must match slug {slug!r}"
        )

    submitted_date = _optional_iso_date(path, "submitted_date", meta.get("submitted_date"))
    revised_date = _optional_iso_date(path, "revised_date", meta.get("revised_date"))
    if submitted_date and revised_date and revised_date < submitted_date:
        raise PaperValidationError(
            f"{path.name}: revised_date must not be before submitted_date"
        )

    arxiv_id = _require_text(path, "arxiv_id", meta["arxiv_id"]) if meta.get("arxiv_id") else None
    if arxiv_id and not ARXIV_ID_RE.fullmatch(arxiv_id):
        raise PaperValidationError(f"{path.name}: invalid arxiv_id {arxiv_id!r}")

    doi = _require_text(path, "doi", meta["doi"]) if meta.get("doi") else None
    if doi and not DOI_RE.fullmatch(doi):
        raise PaperValidationError(f"{path.name}: invalid DOI {doi!r}")

    body_md = (post.content or "").strip()
    if not body_md:
        raise PaperValidationError(f"{path.name}: paper body must not be empty")
    _validate_body(path, body_md)

    return ResearchPaper(
        slug=slug,
        title=_require_single_line(path, "title", meta["title"]),
        original_title=_require_single_line(path, "original_title", meta["original_title"]),
        authors=_require_list(path, "authors", meta["authors"], minimum=1),
        affiliations=_require_list(path, "affiliations", meta.get("affiliations")),
        venue=_require_single_line(path, "venue", meta["venue"]),
        publication_year=_require_publication_year(path, meta["publication_year"]),
        paper_url=_require_https_url(path, "paper_url", meta["paper_url"]),
        pdf_url=_require_https_url(path, "pdf_url", meta["pdf_url"]),
        project_url=_optional_https_url(path, "project_url", meta.get("project_url")),
        code_url=_optional_https_url(path, "code_url", meta.get("code_url")),
        data_url=_optional_https_url(path, "data_url", meta.get("data_url")),
        arxiv_id=arxiv_id,
        doi=doi,
        submitted_date=submitted_date,
        revised_date=revised_date,
        added_date=_require_iso_date(path, "added_date", meta["added_date"]),
        paper_license=_require_single_line(path, "paper_license", meta["paper_license"]),
        paper_license_url=_optional_https_url(
            path, "paper_license_url", meta.get("paper_license_url")
        ),
        code_license=(
            _require_single_line(path, "code_license", meta["code_license"])
            if meta.get("code_license")
            else None
        ),
        summary=_require_single_line(path, "summary", meta["summary"]),
        tags=_require_list(path, "tags", meta["tags"], minimum=2, maximum=5),
        models=_require_list(path, "models", meta.get("models")),
        benchmarks=_require_list(path, "benchmarks", meta.get("benchmarks")),
        body_md=body_md,
    )


def load_paper(path: Path) -> ResearchPaper:
    return parse_paper_text(path.read_text(encoding="utf-8"), path)


def load_papers(source_dir: Path) -> list[ResearchPaper]:
    if not source_dir.is_dir():
        return []
    papers = [load_paper(path) for path in sorted(source_dir.glob("*.md"))]
    seen_urls: set[str] = set()
    seen_arxiv: set[str] = set()
    for paper in papers:
        if paper.paper_url in seen_urls:
            raise PaperValidationError(f"duplicate paper_url: {paper.paper_url}")
        seen_urls.add(paper.paper_url)
        if paper.arxiv_id:
            if paper.arxiv_id in seen_arxiv:
                raise PaperValidationError(f"duplicate arxiv_id: {paper.arxiv_id}")
            seen_arxiv.add(paper.arxiv_id)
    papers.sort(
        key=lambda paper: (paper.added_date, paper.publication_year, paper.title),
        reverse=True,
    )
    return papers

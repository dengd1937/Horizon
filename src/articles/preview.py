"""Isolated local preview generation for one captured curated article."""

import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from ..render.curated import load_articles, render_curated
from .fetch import validate_fetch_output
from .ingest import write_article
from .publication import validate_horizon_workspace
from .translation import load_translated_body, validate_article_translation


class PreviewError(RuntimeError):
    """Raised when a local preview would escape its isolation boundary."""


@dataclass(frozen=True)
class PreviewResult:
    preview_root: str
    article_source: str
    site_root: str
    index_path: str
    detail_path: str
    slug: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _isolated_preview_root(repo: Path, preview_root: Path) -> Path:
    root = preview_root.expanduser().resolve()
    try:
        root.relative_to(repo)
    except ValueError:
        pass
    else:
        raise PreviewError("preview root must be outside the Horizon workspace")

    if root.exists():
        if not root.is_dir():
            raise PreviewError(f"preview root is not a directory: {root}")
        if any(root.iterdir()):
            raise PreviewError(f"preview root must be empty: {root}")
    return root


def render_article_preview(
    repo: Path,
    manifest: Mapping[str, Any],
    fetched_markdown: Path,
    translated_markdown: Path,
    preview_root: Path,
    *,
    added_date: Optional[str] = None,
) -> PreviewResult:
    """Validate one capture and render it without touching repo articles or Git."""
    repo = validate_horizon_workspace(repo)
    preview_root = _isolated_preview_root(repo, preview_root)
    fetched = validate_fetch_output(fetched_markdown)
    translated_body = validate_article_translation(
        manifest, fetched.body_md, load_translated_body(translated_markdown)
    )

    source_dir = preview_root / "article-source"
    ingest = write_article(
        source_dir,
        manifest,
        translated_body,
        added_date=added_date,
    )
    articles = load_articles(source_dir)
    site_root = preview_root / "site"
    render_curated(site_root, articles)

    index_path = site_root / "articles" / "index.html"
    detail_path = site_root / "articles" / f"{ingest.article.slug}.html"
    root_index = site_root / "index.html"
    relative_detail = f"articles/{ingest.article.slug}.html"
    root_index.write_text(
        "<!doctype html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={relative_detail}">'
        f'<title>{html.escape(ingest.article.title)} · Horizon Preview</title></head>'
        f'<body><a href="{relative_detail}">打开文章预览</a></body></html>\n',
        encoding="utf-8",
    )

    return PreviewResult(
        preview_root=str(preview_root),
        article_source=str(ingest.path),
        site_root=str(site_root),
        index_path=str(index_path),
        detail_path=str(detail_path),
        slug=ingest.article.slug,
    )


def preview_result_json(result: PreviewResult) -> str:
    """Serialize preview output for CLI consumers."""
    return json.dumps(result.as_dict(), ensure_ascii=False, indent=2)

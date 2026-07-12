"""Curated article rendering: parse frontmatter sources, render detail + index.

Consumes hand-curated ``articles/*.md`` files (produced by the standalone
``web-article-clipper`` skill) and renders the ``/articles/`` library: a
month-grouped index plus per-article detail pages with original-source link,
reprint notice, optional intro, full body, and prev/next navigation.
"""

import html
import re
from dataclasses import dataclass
from datetime import date as date_cls, timedelta
from pathlib import Path
from typing import Optional

import frontmatter
import markdown

from .site_css import SITE_CSS

_e = html.escape

REQUIRED_FIELDS = (
    "title",
    "source_url",
    "source_domain",
    "published_date",
    "added_date",
    "slug",
    "summary",
)


class ArticleValidationError(ValueError):
    """Raised when an article source is missing required frontmatter."""


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


def load_article(path: Path) -> CuratedArticle:
    """Parse one frontmatter source file into a validated CuratedArticle."""
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata or {}
    missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
    if missing:
        raise ArticleValidationError(
            f"{path.name}: missing required field(s): {', '.join(missing)}"
        )
    raw_intro = meta.get("intro")
    intro = str(raw_intro).strip() or None if raw_intro else None
    return CuratedArticle(
        slug=str(meta["slug"]),
        title=str(meta["title"]),
        source_url=str(meta["source_url"]),
        source_domain=str(meta["source_domain"]),
        published_date=str(meta["published_date"]),
        added_date=str(meta["added_date"]),
        summary=str(meta["summary"]),
        tags=[str(t) for t in (meta.get("tags") or [])],
        cover=(str(meta["cover"]) if meta.get("cover") else None),
        intro=intro,
        body_md=(post.content or "").strip(),
    )


def load_articles(source_dir: Path) -> list[CuratedArticle]:
    """Scan ``source_dir/*.md``; return articles sorted by added_date desc."""
    if not source_dir.is_dir():
        return []
    articles = [load_article(p) for p in sorted(source_dir.glob("*.md"))]
    articles.sort(key=lambda a: a.added_date, reverse=True)
    return articles


def count_recent(articles: list[CuratedArticle], *, today: str, days: int = 7) -> int:
    """Count articles added within the last ``days`` days (inclusive of today)."""
    today_d = date_cls.fromisoformat(today)
    cutoff = today_d - timedelta(days=days)
    return sum(
        1
        for a in articles
        if cutoff <= date_cls.fromisoformat(a.added_date) <= today_d
    )


def new_articles_section(
    articles: list[CuratedArticle],
    *,
    base_url: str,
    since: str,
    today: str,
) -> str:
    """Build the '## 本期新增精选文章' markdown section; '' when none qualify.

    An article qualifies when ``since < added_date <= today``. Links are absolute
    so they resolve in both plain-text and HTML email alternatives.
    """
    since_d = date_cls.fromisoformat(since)
    today_d = date_cls.fromisoformat(today)
    new = [
        a
        for a in articles
        if since_d < date_cls.fromisoformat(a.added_date) <= today_d
    ]
    if not new:
        return ""
    base = base_url.rstrip("/")
    lines = ["\n\n## 本期新增精选文章\n"]
    for a in new:
        url = f"{base}/articles/{a.slug}.html"
        lines.append(
            f"- **{a.title}** · {a.source_domain}\n"
            f"  {a.summary}\n"
            f"  [阅读全文]({url})"
        )
    return "\n".join(lines)


# ---------- helpers ----------

_IMG_ASSET_RE = re.compile(r"(!\[[^\]]*\]\()assets/")


def _to_detail_relative(path: Optional[str]) -> Optional[str]:
    """Rewrite a root-relative asset ref to detail-page-relative (../assets/)."""
    if not path:
        return None
    return "../" + path if path.startswith("assets/") else path


def _render_markdown(md: str) -> str:
    """Render markdown body, rewriting root-relative image refs to ../assets/."""
    return markdown.markdown(_IMG_ASSET_RE.sub(r"\g<1>../assets/", md))


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(title)}</title>\n<style>{SITE_CSS}</style>\n</head>\n"
        f'<body>\n<div class="wrap">\n{body}\n</div>\n</body>\n</html>\n'
    )


def _month_key(date_iso: str) -> str:
    return date_iso[:7]


def _zh_day(date_iso: str) -> str:
    return f"{int(date_iso[5:7])}月{int(date_iso[8:10])}日"


# ---------- detail page ----------

def detail_page_html(
    article: CuratedArticle,
    older: Optional[CuratedArticle],
    newer: Optional[CuratedArticle],
) -> str:
    parts = [
        '<div class="art-top"><span class="brand">HORIZON</span>'
        '<a href="index.html">文章库 ↗</a></div>',
        '<p class="art-kicker">精选文章 · 转载长文</p>',
        f'<h1 class="art-title">{_e(article.title)}</h1>',
    ]

    meta_bits = [
        f"<span>{_e(article.source_domain)}</span>",
        f"<span>发表于 {_e(article.published_date)}</span>",
        f"<span>入库 {_e(article.added_date)}</span>",
    ]
    if article.tags:
        meta_bits.append(
            f'<span>{" ".join(f"#{_e(t)}" for t in article.tags)}</span>'
        )
    parts.append(f'<p class="art-byline">{"".join(meta_bits)}</p>')

    parts.append(
        f'<p class="art-source">📄 <a href="{_e(article.source_url)}">'
        f"阅读原文 · {_e(article.source_domain)}</a></p>"
    )
    parts.append(
        f'<p class="art-license">本文转载自 {_e(article.source_domain)}，'
        "版权归原作者所有</p>"
    )

    if article.intro:
        parts.append(f'<div class="intro">{_render_markdown(article.intro)}</div>')

    cover = _to_detail_relative(article.cover)
    if cover:
        parts.append(f'<img class="art-cover" src="{_e(cover)}" alt="">')

    parts.append(f'<div class="prose">{_render_markdown(article.body_md)}</div>')

    nav = ['<nav class="pagenav">']
    if older:
        nav.append(
            f'<a class="prev" href="{_e(older.slug)}.html">'
            '<span class="dir">← 较旧</span>'
            f'<span class="ttl">{_e(older.title)}</span></a>'
        )
    else:
        nav.append('<span class="muted"></span>')
    nav.append('<a class="up" href="index.html">文章库</a>')
    if newer:
        nav.append(
            f'<a class="next" href="{_e(newer.slug)}.html">'
            '<span class="dir">较新 →</span>'
            f'<span class="ttl">{_e(newer.title)}</span></a>'
        )
    else:
        nav.append('<span class="muted"></span>')
    nav.append("</nav>")
    parts.append("".join(nav))

    return _page(f"{article.title} · Horizon", "".join(parts))


# ---------- index page ----------

def index_page_html(articles: list[CuratedArticle]) -> str:
    by_month: dict[str, list[CuratedArticle]] = {}
    for a in articles:
        by_month.setdefault(_month_key(a.added_date), []).append(a)

    sections = []
    for month in sorted(by_month, reverse=True):
        year, mon = month.split("-")
        rows = []
        for a in by_month[month]:
            meta_line = a.source_domain
            if a.tags:
                meta_line += " · " + " ".join(f"#{t}" for t in a.tags)
            rows.append(
                f'<a class="art-entry" href="{_e(a.slug)}.html">'
                f'<span class="day-tag">{_zh_day(a.added_date)}</span>'
                f'<span class="ttl">{_e(a.title)}</span>'
                f'<span class="meta">{_e(meta_line)}</span>'
                f'<span class="sum">{_e(a.summary)}</span>'
                "</a>"
            )
        sections.append(
            f'<h2 class="idx-month">{year} 年 {int(mon)} 月</h2>' + "".join(rows)
        )

    body = (
        '<div class="art-top"><span class="brand">HORIZON</span>'
        '<a href="../index.html">最新 ↗</a></div>'
        "<h1 class=\"idx-title\">文章库</h1>"
        '<p class="idx-sub">人工精选 · 转载长文</p>'
        + ("".join(sections) if sections else '<p class="empty">暂无文章。</p>')
    )
    return _page("Horizon · 文章库", body)


# ---------- top-level render ----------

def render_curated(out_dir: Path, articles: list[CuratedArticle]) -> list[Path]:
    """Render detail + index pages under ``out_dir/articles/``."""
    arts_dir = out_dir / "articles"
    arts_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    index_path = arts_dir / "index.html"
    index_path.write_text(index_page_html(articles), encoding="utf-8")
    paths.append(index_path)

    for i, article in enumerate(articles):
        older = articles[i + 1] if i + 1 < len(articles) else None
        newer = articles[i - 1] if i > 0 else None
        detail_path = arts_dir / f"{article.slug}.html"
        detail_path.write_text(
            detail_page_html(article, older, newer), encoding="utf-8"
        )
        paths.append(detail_path)

    return paths

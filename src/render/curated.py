"""Curated article rendering: parse frontmatter sources, render detail + index.

Consumes hand-curated ``articles/*.md`` files (produced by Horizon's project-level
``horizon-add-article`` skill) and renders the ``/articles/`` library: a
month-grouped index plus per-article detail pages with original-source link,
reprint notice, optional intro, full body, and prev/next navigation.
"""

import html
import json
import re
from collections import Counter
from datetime import date as date_cls, timedelta
from pathlib import Path
from typing import Collection, Optional

import markdown

from ..articles.contract import (
    MARKDOWN_IMAGE_RE,
    ArticleValidationError,
    CuratedArticle,
    load_article,
    load_articles,
    markdown_image_url,
    slugify,
)
from .assets import MediaDownloader
from .article_index_js import ARTICLE_INDEX_JS
from .html_sanitizer import sanitize_html_fragment
from .site_css import SITE_CSS

_e = html.escape


def article_media_urls(article: CuratedArticle) -> list[str]:
    """Return remote cover/body image URLs without collecting ordinary links."""
    urls: list[str] = []
    candidates = [
        article.cover,
        *(markdown_image_url(m) for m in MARKDOWN_IMAGE_RE.finditer(article.body_md)),
    ]
    for url in candidates:
        if url and url.startswith("https://") and url not in urls:
            urls.append(url)
    return urls


async def localize_article_media(
    articles: list[CuratedArticle], downloader: MediaDownloader
) -> int:
    """Download curated cover/body images and attach URL-to-local-path mappings."""
    downloaded = 0
    for article in articles:
        mapping, new_files = await downloader.download_urls(
            article_media_urls(article), relative_dir=f"assets/articles/{article.slug}"
        )
        article.asset_map.update(mapping)
        downloaded += new_files
    return downloaded


def count_recent(articles: list[CuratedArticle], *, today: str, days: int = 7) -> int:
    """Count additions in a UTC report-date rolling window, inclusive of today.

    ``today`` is the static digest's UTC ``YYYY-MM-DD`` date, not the process
    clock.  With the default ``days=7``, the fixed window is ``today - 6``
    through ``today``: seven calendar dates in total.
    """
    if days < 1:
        raise ValueError("days must be at least 1")
    today_d = date_cls.fromisoformat(today)
    cutoff = today_d - timedelta(days=days - 1)
    return sum(
        1
        for a in articles
        if cutoff <= date_cls.fromisoformat(a.added_date) <= today_d
    )


def select_new_articles(
    articles: list[CuratedArticle],
    *,
    since: str,
    today: str,
    delivered_slugs: Collection[str] = (),
) -> list[CuratedArticle]:
    """Select unsent articles in an inclusive UTC date window."""
    since_d = date_cls.fromisoformat(since)
    today_d = date_cls.fromisoformat(today)
    delivered = set(delivered_slugs)
    return [
        article
        for article in articles
        if since_d <= date_cls.fromisoformat(article.added_date) <= today_d
        and article.slug not in delivered
    ]


def format_new_articles_section(
    articles: list[CuratedArticle], *, base_url: str
) -> str:
    """Format already-selected articles for the email Markdown body."""
    if not articles:
        return ""
    base = base_url.rstrip("/")
    lines = ["\n\n## 本期新增精选文章\n"]
    for article in articles:
        url = f"{base}/articles/{article.slug}.html"
        lines.append(
            f"- **{article.title}** · {article.source_domain}\n"
            f"  {article.summary}\n"
            f"  [阅读全文]({url})"
        )
    return "\n".join(lines)


def place_new_articles_after_overview(summary: str, section: str) -> str:
    """Put the optional curated-articles block before the daily item list.

    Daily summaries open with an H1 and a short overview, followed by a
    horizontal divider before their item list.  Keeping curated articles before
    that first divider makes them prominent in email without changing the
    ordering of the rendered site or stored daily summary.  The fallbacks keep
    the block near the top if a custom summary omits the expected divider.
    """
    if not section:
        return summary

    before_divider, divider, after_divider = summary.partition("\n---\n")
    if divider:
        return (
            f"{before_divider.rstrip()}{section}\n\n---\n"
            f"{after_divider.lstrip()}"
        )

    heading, newline, remaining = summary.partition("\n")
    if heading.startswith("# ") and newline:
        return f"{heading.rstrip()}{section}\n\n{remaining.lstrip()}"
    return f"{section.lstrip()}\n\n{summary.lstrip()}"


def new_articles_section(
    articles: list[CuratedArticle],
    *,
    base_url: str,
    since: str,
    today: str,
    delivered_slugs: Collection[str] = (),
) -> str:
    """Build the '## 本期新增精选文章' markdown section; '' when none qualify.

    ``since`` is inclusive so an article added after an earlier same-day delivery
    remains eligible. ``delivered_slugs`` prevents it from being sent twice.
    """
    selected = select_new_articles(
        articles,
        since=since,
        today=today,
        delivered_slugs=delivered_slugs,
    )
    return format_new_articles_section(selected, base_url=base_url)


# ---------- helpers ----------


def _to_detail_relative(path: Optional[str], asset_map: dict[str, str]) -> Optional[str]:
    """Resolve downloaded assets from the detail page's directory."""
    if not path:
        return None
    if path in asset_map:
        return "../" + asset_map[path]
    return "../" + path if path.startswith("assets/") else path


def _render_markdown(md: str, asset_map: Optional[dict[str, str]] = None) -> str:
    """Render markdown while rewriting only localised Markdown image URLs."""
    asset_map = asset_map or {}

    def rewrite(match: re.Match[str]) -> str:
        source = markdown_image_url(match)
        resolved = asset_map.get(source)
        if resolved:
            source = "../" + resolved
        elif source.startswith("assets/"):
            source = "../" + source
        return f"{match.group('prefix')}{source}{match.group('suffix') or ''})"

    rendered = markdown.markdown(MARKDOWN_IMAGE_RE.sub(rewrite, md))
    return sanitize_html_fragment(rendered)


def _page(title: str, body: str, *, script_src: Optional[str] = None) -> str:
    script_policy = "'self'" if script_src else "'none'"
    script = (
        f'\n<script defer src="{_e(script_src)}"></script>' if script_src else ""
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; img-src \'self\' https: data:; '
        'media-src \'self\' https:; style-src \'unsafe-inline\'; '
        f'script-src {script_policy}; base-uri \'none\'; form-action \'none\'">\n'
        '<link rel="icon" href="data:,">\n'
        f"<title>{_e(title)}</title>\n<style>{SITE_CSS}</style>{script}\n</head>\n"
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
        parts.append(
            f'<div class="intro">{_render_markdown(article.intro, article.asset_map)}</div>'
        )

    cover = _to_detail_relative(article.cover, article.asset_map)
    if cover:
        parts.append(f'<img class="art-cover" src="{_e(cover)}" alt="">')

    parts.append(
        f'<div class="prose">{_render_markdown(article.body_md, article.asset_map)}</div>'
    )

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

    tag_counts: Counter[str] = Counter()
    for article in articles:
        tag_counts.update(list(dict.fromkeys(article.tags)))
    filter_tags = sorted(
        (
            (tag, count)
            for tag, count in tag_counts.items()
            if 0 < count < len(articles)
        ),
        key=lambda item: (-item[1], item[0].casefold(), item[0]),
    )

    sections = []
    for month in sorted(by_month, reverse=True):
        year, mon = month.split("-")
        rows = []
        for a in by_month[month]:
            tags = list(dict.fromkeys(a.tags))
            tags_json = json.dumps(tags, ensure_ascii=False, separators=(",", ":"))
            meta_line = a.source_domain
            if tags:
                meta_line += " · " + " ".join(f"#{t}" for t in tags)
            rows.append(
                f'<a class="art-entry" data-article-entry '
                f'data-tags="{_e(tags_json)}" href="{_e(a.slug)}.html">'
                f'<span class="day-tag">{_zh_day(a.added_date)}</span>'
                f'<span class="ttl">{_e(a.title)}</span>'
                f'<span class="meta">{_e(meta_line)}</span>'
                f'<span class="sum">{_e(a.summary)}</span>'
                "</a>"
            )
        sections.append(
            '<section class="idx-group" data-article-group>'
            f'<h2 class="idx-month">{year} 年 {int(mon)} 月</h2>'
            + "".join(rows)
            + "</section>"
        )

    controls = ""
    filtered_empty = ""
    script_src = None
    if articles:
        tag_buttons = [
            '<button class="idx-tag" type="button" data-article-tag data-tag="" '
            f'aria-pressed="true">全部 <span>{len(articles)}</span></button>'
        ]
        tag_buttons.extend(
            '<button class="idx-tag" type="button" data-article-tag '
            f'data-tag="{_e(tag)}" aria-pressed="false">'
            f'{_e(tag)} <span>{count}</span></button>'
            for tag, count in filter_tags
        )
        controls = (
            '<section class="idx-tools" data-article-filter hidden aria-label="文章筛选">'
            '<div class="idx-search-row">'
            '<label class="visually-hidden" for="article-search">搜索文章</label>'
            '<input class="idx-search" id="article-search" type="search" '
            'data-article-search autocomplete="off" spellcheck="false" '
            'aria-controls="article-groups" '
            'placeholder="搜索标题、摘要、来源或标签……">'
            '<button class="idx-reset" type="button" data-article-reset hidden>重置</button>'
            '</div>'
            '<div class="idx-tags" role="group" aria-label="按标签筛选">'
            + "".join(tag_buttons)
            + "</div>"
            f'<p class="idx-results" data-article-results aria-live="polite" '
            f'aria-atomic="true">共 {len(articles)} 篇文章</p>'
            "</section>"
        )
        filtered_empty = (
            '<p class="idx-empty" data-article-empty hidden>'
            "没有找到符合条件的文章。</p>"
        )
        script_src = "article-index.js"

    body = (
        '<main data-article-library>'
        '<div class="art-top"><span class="brand">HORIZON</span>'
        '<a href="../index.html">最新 ↗</a></div>'
        "<h1 class=\"idx-title\">文章库</h1>"
        '<p class="idx-sub">人工精选 · 转载长文</p>'
        + controls
        + (
            '<div class="idx-groups" id="article-groups" data-article-groups>'
            + "".join(sections)
            + "</div>"
            if sections
            else '<p class="empty">暂无文章。</p>'
        )
        + filtered_empty
        + "</main>"
    )
    return _page("Horizon · 文章库", body, script_src=script_src)


# ---------- top-level render ----------

def render_curated(out_dir: Path, articles: list[CuratedArticle]) -> list[Path]:
    """Render detail + index pages under ``out_dir/articles/``."""
    arts_dir = out_dir / "articles"
    arts_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    (arts_dir / "article-index.js").write_text(ARTICLE_INDEX_JS, encoding="utf-8")

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

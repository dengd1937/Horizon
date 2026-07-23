"""Static reading-site renderer: daily digest, article pages, archive index.

Templates the acceptance-approved design draft with real item data. Every
page references a shared stylesheet, with media served from the local assets
directory via each item's asset_map.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from ..models import ContentItem, SiteConfig
from ..papers.contract import ResearchPaper, load_papers
from ..scrapers.twitter_article import ARTICLE_MARKER
from .article_html import article_to_html, article_to_text
from .curated import CuratedArticle, count_recent, load_articles, render_curated
from .papers import render_papers
from .site_css import SITE_CSS_HREF, write_site_css

logger = logging.getLogger(__name__)

_e = html.escape
_URL_LINK_RE = re.compile(r"(https?://[^\s<]+)")
_ARTICLE_URL_RE = re.compile(r"https?://\S*/i/article/\S+")
_LEGACY_DAILY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.html$")
_LEGACY_X_ARTICLE_RE = re.compile(r"^(\d+)\.html$")
_LEGACY_X_ARTICLE_HREF_RE = re.compile(r'(href=["\'])articles/(\d+)\.html(["\'])')
_LEGACY_DAILY_BACK_HREF_RE = re.compile(
    r'(href=["\'])\.\./(\d{4}-\d{2}-\d{2}\.html(?:#[^"\']*)?)(["\'])'
)
_DAILY_ARTICLE_LIBRARY_LINK_RE = re.compile(
    r'(<a href="\.\./articles/index\.html">文章库(?: ↗)?</a>)'
)
_DAILY_PAPER_LIBRARY_HREF = 'href="../papers/index.html"'
_WEEKDAYS_ZH = ["一", "二", "三", "四", "五", "六", "日"]
_TWEET_FOLD_CHAR_LIMIT = 240
_TWEET_FOLD_NEWLINE_LIMIT = 4


def daily_digest_path(date: str) -> Path:
    """Daily Twitter digest page: daily/{date}.html."""
    return Path("daily") / f"{date}.html"


def daily_article_path(article_id: str) -> Path:
    """X Article detail page (lives under the daily section): daily/article-{id}.html."""
    return Path("daily") / f"article-{article_id}.html"


def archive_index_path() -> Path:
    """Daily archive index: daily/index.html (grouped by month)."""
    return Path("daily") / "index.html"


def root_index_path() -> Path:
    """Root landing page: redirects to the latest daily digest."""
    return Path("index.html")


def backfill_paper_library_navigation(site_root: Path) -> list[Path]:
    """One-time migration: add the paper-library link to legacy daily pages.

    Incremental production publishing never scans historical HTML. This helper
    remains available for an explicit, locally prepared legacy migration.
    """
    daily_dir = site_root / "daily"
    if not daily_dir.is_dir():
        return []

    updated: list[Path] = []
    paper_link = '<a href="../papers/index.html">论文库 ↗</a>'
    for page in sorted(daily_dir.glob("*.html")):
        content = page.read_text(encoding="utf-8")
        if _DAILY_PAPER_LIBRARY_HREF in content:
            continue
        migrated, count = _DAILY_ARTICLE_LIBRARY_LINK_RE.subn(
            lambda match: match.group(1) + paper_link,
            content,
            count=1,
        )
        if count:
            page.write_text(migrated, encoding="utf-8")
            updated.append(page)
    return updated

_RT_SVG = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" aria-hidden="true">'
    '<path d="M17 2l4 4-4 4M3 11v-1a4 4 0 014-4h14M7 22l-4-4 4-4M21 13v1a4 4 0 01-4 4H3"/></svg>'
)


def _linkify(escaped_text: str) -> str:
    """Turn bare URLs in already-escaped text into anchors."""
    return _URL_LINK_RE.sub(r'<a href="\1">\1</a>', escaped_text)


def _rich_text(text: str) -> str:
    return _linkify(_e(text or ""))


def _fmt_score(item: ContentItem) -> str:
    return f"{item.ai_score:.1f}" if item.ai_score is not None else "?"


def _fmt_dt_zh(dt: datetime) -> str:
    return f"{dt.month}月{dt.day}日 {dt:%H:%M}"


def _zh_title(item: ContentItem) -> str:
    return str(item.metadata.get("title_zh") or item.title)


def _summary_text(item: ContentItem) -> str:
    meta = item.metadata
    return str(
        meta.get("detailed_summary_zh")
        or meta.get("detailed_summary")
        or item.ai_summary
        or ""
    )


def item_anchor(item: ContentItem, index: int) -> str:
    """Stable in-page anchor for an item; shared with the email summary so
    email 'original' links jump to the right card on the reading site."""
    return f"t-{item.metadata.get('tweet_id') or index}"


def _tweet_body(item: ContentItem) -> str:
    """Original tweet text: content minus any appended article full text."""
    content = item.content or ""
    marker = "\n\n" + ARTICLE_MARKER + "\n"
    return content.split(marker)[0] if marker in content else content


def _strip_article_link(text: str, meta: dict) -> str:
    """Drop bare /i/article/ links when the article card already covers them."""
    if meta.get("article"):
        return _ARTICLE_URL_RE.sub("", text).strip()
    return text


class SiteRenderer:
    """Render one run's items into the static reading site."""

    def __init__(self, config: SiteConfig):
        self.config = config
        self.out = Path(config.output_dir)

    # ---------- public ----------

    def render(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        curated_articles: Optional[list[CuratedArticle]] = None,
        research_papers: Optional[list[ResearchPaper]] = None,
    ) -> list[Path]:
        """Compatibility full-site render used by local previews and tests.

        Production daily runs use :meth:`render_daily`; content-library
        publishing renders its own independently-owned directories.
        """
        self.out.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_paths()
        articles = (
            curated_articles
            if curated_articles is not None
            else load_articles(Path(self.config.articles_source_dir))
        )
        papers = (
            research_papers
            if research_papers is not None
            else load_papers(Path(self.config.papers_source_dir))
        )

        paths = self.render_daily(
            items,
            date,
            total_fetched,
            curated_articles=articles,
        )
        paths.extend(render_curated(self.out, articles))
        paths.extend(render_papers(self.out, papers))
        paths = list(dict.fromkeys(paths))

        logger.info("Site rendered: %d page(s) under %s", len(paths), self.out)
        return paths

    def render_daily(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        curated_articles: Optional[list[CuratedArticle]] = None,
    ) -> list[Path]:
        """Render only the current daily release and shared daily indexes."""
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "daily").mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []

        articles = (
            curated_articles
            if curated_articles is not None
            else load_articles(Path(self.config.articles_source_dir))
        )

        digest = self.out / daily_digest_path(date)
        digest.write_text(
            self._digest_page(
                items, date, total_fetched, count_recent(articles, today=date)
            ),
            encoding="utf-8",
        )
        paths.append(digest)

        for index, item in enumerate(items, start=1):
            page = self._article_page(item, date, index)
            if page is not None:
                paths.append(page)

        manifest = self._update_manifest(date, items)
        paths.append(self.out / "site_manifest.json")
        archive = self.out / archive_index_path()
        archive.write_text(self._index_page(manifest), encoding="utf-8")
        paths.append(archive)

        root_index = self.out / root_index_path()
        root_index.write_text(self._root_index_page(manifest), encoding="utf-8")
        paths.append(root_index)
        paths.append(write_site_css(self.out))

        logger.info("Daily site rendered: %d page(s) under %s", len(paths), self.out)
        return paths

    def _migrate_legacy_paths(self) -> None:
        """Move pre-``/daily`` output into its new locations for full previews.

        This compatibility path is intentionally absent from production daily
        rendering. Remote history migrations must be prepared and reviewed as
        explicit one-time operations.
        """
        daily_dir = self.out / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)

        for legacy in self.out.iterdir():
            if not legacy.is_file() or not _LEGACY_DAILY_RE.fullmatch(legacy.name):
                continue
            target = daily_dir / legacy.name
            if not target.exists():
                content = legacy.read_text(encoding="utf-8")
                content = content.replace('src="assets/', 'src="../assets/')
                content = content.replace('poster="assets/', 'poster="../assets/')
                content = _LEGACY_X_ARTICLE_HREF_RE.sub(
                    r"\1article-\2.html\3", content
                )
                target.write_text(content, encoding="utf-8")
            legacy.unlink()

        legacy_articles_dir = self.out / "articles"
        if not legacy_articles_dir.is_dir():
            return
        for legacy in legacy_articles_dir.iterdir():
            match = _LEGACY_X_ARTICLE_RE.fullmatch(legacy.name)
            if not legacy.is_file() or not match:
                continue
            target = daily_dir / f"article-{match.group(1)}.html"
            if not target.exists():
                content = legacy.read_text(encoding="utf-8")
                content = _LEGACY_DAILY_BACK_HREF_RE.sub(r"\1\2\3", content)
                target.write_text(content, encoding="utf-8")
            legacy.unlink()

    # ---------- shared bits ----------

    def _resolver(self, item: ContentItem, prefix: str = "") -> Callable[[str], str]:
        asset_map = item.metadata.get("asset_map") or {}

        def resolve(url: str) -> str:
            rel = asset_map.get(url)
            return (prefix + rel) if rel else url

        return resolve

    @staticmethod
    def _page(title: str, body: str) -> str:
        return (
            "<!DOCTYPE html>\n"
            '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<link rel="icon" href="data:,">\n'
            f"<title>{_e(title)}</title>\n"
            f'<link rel="stylesheet" href="{SITE_CSS_HREF}">\n</head>\n'
            f'<body>\n<div class="wrap">\n{body}\n</div>\n</body>\n</html>\n'
        )

    # ---------- digest page ----------

    def _digest_page(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        recent_count: int,
    ) -> str:
        day = datetime.strptime(date, "%Y-%m-%d")
        weekday = _WEEKDAYS_ZH[day.weekday()]
        authors = {it.author for it in items if it.author}
        sources = " · ".join(sorted({it.source_type.value for it in items})) or "twitter"
        generated = datetime.now(timezone.utc).strftime("%H:%M")
        recent_span = (
            f'<span><a href="../articles/index.html">文章库本周 +{recent_count}</a></span>'
            if recent_count > 0
            else ""
        )

        bars = []
        for index, item in enumerate(items, start=1):
            score = item.ai_score if item.ai_score is not None else 5.0
            height = int(20 + (max(min(score, 10), 0) / 10) * 28)
            opacity = round(0.45 + (max(min(score, 10), 0) / 10) * 0.5, 2)
            bars.append(
                f'<a href="#{item_anchor(item, index)}" style="height:{height}px;opacity:{opacity}" '
                f'title="{_e(_fmt_score(item))} · {_e(_zh_title(item))}"></a>'
            )

        toc = []
        for index, item in enumerate(items, start=1):
            toc.append(
                f'<li><a href="#{item_anchor(item, index)}">{_e(_zh_title(item))}</a>'
                f'<span class="s">{_e(_fmt_score(item))}</span></li>'
            )

        rendered_items = "".join(
            self._item_html(item, index) for index, item in enumerate(items, start=1)
        )

        body = (
            '<header class="mast">\n'
            '<div class="mast-top"><span class="brand">HORIZON</span>'
            '<span class="mast-links">'
            '<a href="../articles/index.html">文章库 ↗</a>'
            '<a href="../papers/index.html">论文库 ↗</a>'
            '<a href="index.html">归档 ↗</a></span></div>\n'
            f"<h1>{day.month}月{day.day}日<small>{day.year} · 星期{weekday}</small></h1>\n"
            f'<p class="stats">从 {total_fetched} 条抓取中筛选 <b>{len(items)}</b> 条 · '
            f"{_e(sources)} × {len(authors)} 账号 · {generated} UTC 生成</p>\n"
            f'<div class="band" aria-label="今日条目评分，点击跳转">{"".join(bars)}</div>\n'
            '<p class="band-hint">今日信号 · 高度即评分 · 点击直达</p>\n'
            '<hr class="rule">\n</header>\n'
            f'<ol class="toc">{"".join(toc)}</ol>\n'
            f"{rendered_items}\n"
            '<footer class="foot"><span>HORIZON · 内容与媒体已本地化</span>'
            f"{recent_span}"
            '<span><a href="index.html">全部归档</a></span></footer>'
        )
        return self._page(f"Horizon 每日速递 · {date}", body)

    def _item_html(self, item: ContentItem, index: int) -> str:
        meta = item.metadata
        resolver = self._resolver(item, prefix="../")

        summary = _summary_text(item)
        summary_html = f'<p class="summary">{_e(summary)}</p>\n' if summary else ""

        folds = []
        background = meta.get("background_zh") or meta.get("background")
        if background:
            folds.append(
                f'<details><summary>背景</summary><div class="fold-body">{_e(str(background))}</div></details>'
            )
        discussion = meta.get("community_discussion_zh") or meta.get("community_discussion")
        if discussion:
            folds.append(
                f'<details><summary>社区讨论</summary><div class="fold-body">{_e(str(discussion))}</div></details>'
            )

        meta_parts = [f"<span>{_e(_fmt_dt_zh(item.published_at))}</span>"]
        meta_parts.append(f'<a href="{_e(str(item.url))}">在 X 打开</a>')
        if item.ai_tags:
            tags = " ".join(f"#{t}" for t in item.ai_tags[:5])
            meta_parts.append(f"<span>{_e(tags)}</span>")

        return (
            f'<article class="item" id="{_e(item_anchor(item, index))}">\n'
            f'<div class="item-head"><span class="no">{index:02d}</span>'
            f'<span class="score">{_e(_fmt_score(item))}</span></div>\n'
            f"<h2>{_e(_zh_title(item))}</h2>\n"
            f"{summary_html}"
            f"{self._original_tweet_html(item, resolver)}\n"
            f'{"".join(folds)}\n'
            f'<p class="meta">{"".join(meta_parts)}</p>\n'
            "</article>\n"
        )

    # ---------- tweet cards ----------

    def _original_tweet_html(self, item: ContentItem, resolver) -> str:
        """Render a tweet directly or behind a media-aware native fold."""
        should_fold = self._should_fold_tweet(item)
        full_card = self._tweet_card(
            item,
            resolver,
            autoplay_gif=not should_fold,
        )
        if not should_fold:
            return full_card

        author, label, preview_text = self._tweet_preview_copy(item)
        media = self._ordered_tweet_media(item)
        media_preview = self._media_preview_html(media, resolver)
        facts = self._tweet_preview_facts(item, media)
        facts_html = f'<span class="tweet-preview-facts">{_e(facts)}</span>' if facts else ""

        return (
            '<details class="tweet-fold">'
            '<summary>'
            '<span class="tweet-preview">'
            '<span class="tweet-preview-content">'
            '<span class="tweet-preview-head">'
            f'<b>@{_e(author)}</b><span>{_e(label)}</span>'
            f"{facts_html}</span>"
            f'<span class="tweet-preview-text">{_e(preview_text)}</span>'
            f"{media_preview}"
            '</span>'
            '<span class="tweet-fold-action">'
            '<span class="when-closed">展开原推文</span>'
            '<span class="when-open">收起原推文</span>'
            '</span>'
            '</span>'
            '</summary>'
            f'<div class="tweet-fold-body">{full_card}</div>'
            '</details>'
        )

    @staticmethod
    def _should_fold_tweet(item: ContentItem) -> bool:
        meta = item.metadata
        thread_parts = meta.get("thread_parts") or []
        if len(thread_parts) > 1:
            return True
        if meta.get("is_quote"):
            return True
        if meta.get("is_retweet") and meta.get("quoted_text"):
            return True

        if meta.get("is_retweet"):
            text = str(meta.get("rt_original_text") or _tweet_body(item))
        else:
            text = _tweet_body(item)
        return (
            len(text) > _TWEET_FOLD_CHAR_LIMIT
            or text.count("\n") >= _TWEET_FOLD_NEWLINE_LIMIT
        )

    @staticmethod
    def _tweet_preview_copy(item: ContentItem) -> tuple[str, str, str]:
        meta = item.metadata
        thread_parts = meta.get("thread_parts") or []
        if thread_parts:
            return (
                item.author or "unknown",
                f"串推 {len(thread_parts)} 条",
                str(thread_parts[0].get("text") or _tweet_body(item)),
            )
        if meta.get("is_retweet"):
            return (
                str(meta.get("rt_original_author") or "unknown"),
                f"@{item.author or 'unknown'} 转推",
                str(meta.get("rt_original_text") or _tweet_body(item)),
            )
        if meta.get("is_quote") and meta.get("qrt_comment"):
            return (
                item.author or "unknown",
                "引用推文",
                str(meta.get("qrt_comment")),
            )
        if meta.get("is_quote") and meta.get("quoted_text"):
            return (
                str(meta.get("quoted_author") or "unknown"),
                f"@{item.author or 'unknown'} 引用",
                str(meta.get("quoted_text")),
            )
        return item.author or "unknown", "原推文", _tweet_body(item)

    @staticmethod
    def _ordered_tweet_media(item: ContentItem) -> list[dict]:
        """Collect media in preview priority order and remove duplicates."""
        meta = item.metadata
        groups: list[list[dict]] = []
        thread_parts = meta.get("thread_parts") or []
        if thread_parts:
            groups.append(thread_parts[0].get("media") or [])
            groups.append(meta.get("quoted_media") or [])
            groups.extend(part.get("media") or [] for part in thread_parts[1:])
            groups.append(meta.get("media") or [])
        else:
            groups.append(meta.get("media") or [])
            groups.append(meta.get("quoted_media") or [])

        ordered: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for group in groups:
            for media in group:
                key = (
                    str(media.get("type") or ""),
                    str(media.get("thumbnail_url") or ""),
                    str(media.get("mp4_url") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                ordered.append(media)
        return ordered

    @staticmethod
    def _tweet_preview_facts(item: ContentItem, media: list[dict]) -> str:
        facts = []
        thread_parts = item.metadata.get("thread_parts") or []
        if len(thread_parts) > 1:
            facts.append(f"{len(thread_parts)} 段")
        photos = sum(1 for m in media if m.get("type") == "photo")
        videos = sum(
            1 for m in media if m.get("type") in {"video", "animated_gif"}
        )
        if photos:
            facts.append(f"{photos} 张图片")
        if videos:
            facts.append(f"{videos} 个视频")
        return " · ".join(facts)

    def _media_preview_html(self, media: list[dict], resolver) -> str:
        if not media:
            return ""
        representative = media[0]
        mtype = representative.get("type")
        thumb = resolver(representative.get("thumbnail_url") or "")
        extra = len(media) - 1
        extra_html = f'<span class="media-more">+{extra}</span>' if extra else ""

        if thumb:
            kind = " video-preview" if mtype in {"video", "animated_gif"} else ""
            play = (
                '<span class="media-play" aria-hidden="true">▶</span>'
                if kind
                else ""
            )
            return (
                f'<span class="tweet-preview-media{kind}">'
                f'<img src="{_e(thumb)}" alt="原推文媒体预览" loading="lazy">'
                f"{play}{extra_html}</span>"
            )
        if mtype in {"video", "animated_gif"}:
            return (
                '<span class="tweet-preview-media media-placeholder">'
                '<span class="media-play" aria-hidden="true">▶</span>'
                f'<span class="media-placeholder-label">视频</span>{extra_html}</span>'
            )
        return ""

    def _tweet_card(self, item: ContentItem, resolver, autoplay_gif: bool = True) -> str:
        meta = item.metadata
        if meta.get("thread_parts"):
            return self._thread_card(item, resolver, autoplay_gif)
        if meta.get("is_retweet"):
            return self._repost_card(
                item,
                resolver,
                author=meta.get("rt_original_author") or "unknown",
                text=meta.get("rt_original_text") or _tweet_body(item),
                include_nested=True,
                autoplay_gif=autoplay_gif,
            )
        if meta.get("is_quote") and meta.get("qrt_comment"):
            return self._qrt_card(item, resolver, autoplay_gif)
        if meta.get("is_quote") and meta.get("quoted_text"):
            return self._repost_card(
                item,
                resolver,
                author=meta.get("quoted_author") or "unknown",
                text=str(meta.get("quoted_text")),
                include_nested=False,
                autoplay_gif=autoplay_gif,
            )
        return self._plain_card(item, resolver, autoplay_gif)

    def _attachments(
        self,
        item: ContentItem,
        resolver,
        with_media: bool = True,
        autoplay_gif: bool = True,
    ) -> str:
        meta = item.metadata
        parts = []
        if with_media:
            parts.append(
                self._media_html(
                    meta.get("media") or [], resolver, autoplay_gif=autoplay_gif
                )
            )
        if meta.get("article"):
            parts.append(self._article_card(item, resolver))
        elif meta.get("card"):
            parts.append(self._link_card(meta, resolver))
        return "".join(p for p in parts if p)

    def _plain_card(self, item: ContentItem, resolver, autoplay_gif: bool) -> str:
        text = _strip_article_link(_tweet_body(item), item.metadata)
        return (
            '<div class="tweet">'
            f'<p class="t-author"><b>@{_e(item.author or "unknown")}</b></p>'
            f'<p class="t-text">{_rich_text(text)}</p>'
            f"{self._attachments(item, resolver, autoplay_gif=autoplay_gif)}"
            "</div>"
        )

    def _repost_card(
        self,
        item: ContentItem,
        resolver,
        author: str,
        text: str,
        include_nested: bool,
        autoplay_gif: bool,
    ) -> str:
        meta = item.metadata
        nested = ""
        if include_nested and meta.get("quoted_text"):
            nested_media = self._media_html(
                meta.get("quoted_media") or [],
                resolver,
                autoplay_gif=autoplay_gif,
            )
            nested = (
                '<div class="tweet">'
                f'<p class="t-author"><b>@{_e(meta.get("quoted_author") or "unknown")}</b></p>'
                f'<p class="t-text">{_rich_text(str(meta.get("quoted_text")))}</p>'
                f"{nested_media}</div>"
            )
        return (
            '<div class="tweet">'
            f'<p class="rt-line">{_RT_SVG} @{_e(item.author or "")} 转推了</p>'
            '<div class="tweet">'
            f'<p class="t-author"><b>@{_e(author)}</b></p>'
            f'<p class="t-text">{_rich_text(_strip_article_link(text, meta))}</p>'
            f"{self._media_html(meta.get('media') or [], resolver, autoplay_gif=autoplay_gif)}"
            f"{nested}"
            f"{self._attachments(item, resolver, with_media=False, autoplay_gif=autoplay_gif)}"
            "</div></div>"
        )

    def _qrt_card(self, item: ContentItem, resolver, autoplay_gif: bool) -> str:
        meta = item.metadata
        quoted_media = self._media_html(
            meta.get("quoted_media") or [], resolver, autoplay_gif=autoplay_gif
        )
        comment = _strip_article_link(str(meta.get("qrt_comment")), meta)
        return (
            '<div class="tweet">'
            f'<p class="t-author"><b>@{_e(item.author or "unknown")}</b></p>'
            f'<p class="t-text">{_rich_text(comment)}</p>'
            f"{self._attachments(item, resolver, autoplay_gif=autoplay_gif)}"
            '<div class="tweet">'
            f'<p class="t-author"><b>@{_e(meta.get("quoted_author") or "unknown")}</b></p>'
            f'<p class="t-text">{_rich_text(str(meta.get("quoted_text")))}</p>'
            f"{quoted_media}</div>"
            "</div>"
        )

    def _thread_card(self, item: ContentItem, resolver, autoplay_gif: bool) -> str:
        meta = item.metadata
        parts = meta.get("thread_parts") or []
        rows = []
        for i, part in enumerate(parts):
            last = " last" if i == len(parts) - 1 else ""
            media = self._media_html(
                part.get("media") or [], resolver, autoplay_gif=autoplay_gif
            )
            quoted = ""
            if i == 0 and meta.get("quoted_text"):
                quoted_media = self._media_html(
                    meta.get("quoted_media") or [],
                    resolver,
                    autoplay_gif=autoplay_gif,
                )
                quoted = (
                    '<div class="tweet">'
                    f'<p class="t-author"><b>@{_e(meta.get("quoted_author") or "unknown")}</b></p>'
                    f'<p class="t-text">{_rich_text(str(meta.get("quoted_text")))}</p>'
                    f"{quoted_media}</div>"
                )
            rows.append(
                f'<div class="tick{last}"></div>'
                f'<div class="seg"><p class="t-text">{_rich_text(part.get("text", ""))}</p>'
                f"{media}{quoted}</div>"
            )
        return (
            '<div class="tweet">'
            f'<p class="t-author"><b>@{_e(item.author or "unknown")}</b>'
            f'<span class="h">串推 {len(parts)} 条</span></p>'
            f'<div class="thread">{"".join(rows)}</div>'
            f"{self._attachments(item, resolver, with_media=False, autoplay_gif=autoplay_gif)}"
            "</div>"
        )

    # ---------- media & cards ----------

    def _media_html(
        self,
        media_list: list,
        resolver,
        autoplay_gif: bool = True,
    ) -> str:
        cells = []
        for m in media_list or []:
            mtype = m.get("type")
            thumb = resolver(m.get("thumbnail_url") or "")
            mp4 = m.get("mp4_url") or ""
            if mtype == "photo" and thumb:
                cells.append(f'<img src="{_e(thumb)}" alt="" loading="lazy">')
            elif mtype == "animated_gif" and mp4 and autoplay_gif:
                src = resolver(mp4)
                cells.append(
                    f'<div class="gifwrap"><video autoplay loop muted playsinline src="{_e(src)}"></video>'
                    '<span class="tag">GIF</span></div>'
                )
            elif mtype in ("video", "animated_gif"):
                if mp4:
                    src = resolver(mp4)
                    cells.append(
                        f'<video controls preload="metadata" poster="{_e(thumb)}">'
                        f'<source src="{_e(src)}" type="video/mp4"></video>'
                    )
                elif thumb:
                    cells.append(f'<img src="{_e(thumb)}" alt="" loading="lazy">')
        if not cells:
            return ""
        grid = " grid" if len(cells) > 1 else ""
        return f'<div class="media{grid}">{"".join(cells)}</div>'

    def _link_card(self, meta: dict, resolver) -> str:
        card = meta.get("card") or {}
        title = card.get("title", "")
        if not title:
            return ""
        href = card.get("card_url", "")
        for link in meta.get("links") or []:
            if link.get("short_url") == href and link.get("expanded_url"):
                href = link["expanded_url"]
                break
        thumb = card.get("thumbnail_url", "")
        thumb_html = (
            f'<img class="thumb" src="{_e(resolver(thumb))}" alt="" loading="lazy">'
            if thumb
            else '<span class="thumb"></span>'
        )
        domain = card.get("domain") or ""
        return (
            f'<a class="linkcard" href="{_e(href)}">{thumb_html}'
            f'<span class="lc-body"><span class="lc-title">{_e(title)}</span>'
            f'<span class="lc-domain" style="display:block">{_e(domain)} · 直连原文</span></span></a>'
        )

    def _article_card(self, item: ContentItem, resolver) -> str:
        article = item.metadata.get("article") or {}
        title = article.get("title", "")
        if not title:
            return ""
        preview = str(article.get("preview_text") or "")[:90]
        cover_url = article.get("cover_url", "")
        cover = (
            f'<img class="cover" src="{_e(resolver(cover_url))}" alt="" loading="lazy">'
            if cover_url
            else ""
        )
        if article.get("content_state"):
            href = f"article-{article.get('article_id')}.html"
            kicker = "X ARTICLE · 全文已本地化"
            chars = len(article_to_text(article))
            images = len(article.get("media_entities") or [])
            cta = f"阅读全文 · {chars} 字 · {images} 图 →"
        else:
            href = str(item.url)
            kicker = "X ARTICLE"
            cta = "在 X 打开 →"
        return (
            f'<a class="articlecard" href="{_e(href)}">{cover}'
            '<span class="ac-body" style="display:block">'
            f'<span class="ac-kicker" style="display:block">{_e(kicker)}</span>'
            f'<span class="ac-title" style="display:block">{_e(title)}</span>'
            f'<span class="ac-preview" style="display:block">{_e(preview)}…</span>'
            f'<span class="ac-cta">{_e(cta)}</span></span></a>'
        )

    # ---------- article page ----------

    def _article_page(self, item: ContentItem, date: str, index: int) -> Optional[Path]:
        article = item.metadata.get("article") or {}
        if not article.get("content_state"):
            return None
        resolver = self._resolver(item, prefix="../")
        body_html = article_to_html(article, resolver)
        title = article.get("title", "无题")
        chars = len(article_to_text(article))
        images = len(article.get("media_entities") or [])
        cover_url = article.get("cover_url", "")
        cover = (
            f'<img class="art-cover" src="{_e(resolver(cover_url))}" alt="">'
            if cover_url
            else ""
        )
        back = f"{date}.html#{item_anchor(item, index)}"
        body = (
            '<div class="art-top"><span class="brand">HORIZON</span>'
            '<span class="mast-links">'
            f'<a href="{_e(back)}">← 返回 {date}</a>'
            '<a href="../articles/index.html">文章库</a>'
            '<a href="../papers/index.html">论文库</a>'
            "</span></div>\n"
            f'<p class="art-kicker">X ARTICLE · 已本地化 · {chars} 字 · {images} 图</p>\n'
            f'<h1 class="art-title">{_e(title)}</h1>\n'
            f'<p class="art-byline"><span>@{_e(item.author or "unknown")}</span>'
            f"<span>{_e(_fmt_dt_zh(item.published_at))}</span>"
            f'<a href="{_e(str(item.url))}">在 X 打开</a></p>\n'
            f"{cover}\n"
            f'<div class="prose">{body_html}</div>\n'
            f'<p class="backline"><a href="{_e(back)}">← 返回当日速递 · 第 {index:02d} 条</a></p>'
        )
        daily_dir = self.out / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        path = daily_dir / f"article-{article.get('article_id')}.html"
        path.write_text(self._page(f"{title} · Horizon", body), encoding="utf-8")
        return path

    # ---------- archive index ----------

    def _update_manifest(self, date: str, items: List[ContentItem]) -> dict:
        manifest_path = self.out / "site_manifest.json"
        data: dict = {}
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                data = {}
        data[date] = {
            "count": len(items),
            "top": [_zh_title(item) for item in items[:3]],
        }
        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        return data

    def _index_page(self, manifest: dict) -> str:
        by_month: dict[str, list[tuple[str, dict]]] = {}
        for date in sorted(manifest, reverse=True):
            by_month.setdefault(date[:7], []).append((date, manifest[date]))

        sections = []
        for month, days in by_month.items():
            year, mon = month.split("-")
            rows = []
            for date, info in days:
                day = datetime.strptime(date, "%Y-%m-%d")
                top = " · ".join(info.get("top") or [])
                rows.append(
                    f'<a class="day" href="{_e(date)}.html">'
                    f'<span class="d">{day.month}月{day.day}日</span>'
                    f'<span class="n">{info.get("count", 0)} 条</span>'
                    f'<span class="t">{_e(top)}</span></a>'
                )
            sections.append(
                f'<h2 class="idx-month">{year} 年 {int(mon)} 月</h2>\n' + "\n".join(rows)
            )

        body = (
            '<div class="art-top"><span class="brand">HORIZON</span>'
            '<span class="mast-links"><a href="../articles/index.html">文章库 ↗</a>'
            '<a href="../papers/index.html">论文库 ↗</a>'
            '<a href="../index.html">最新 ↗</a></span></div>\n'
            '<h1 class="idx-title">归档</h1>\n'
            '<p class="idx-sub">内容与媒体已本地化 · 无需代理</p>\n'
            + "\n".join(sections)
        )
        return self._page("Horizon · 归档", body)

    # ---------- root landing ----------

    def _root_index_page(self, manifest: dict) -> str:
        """Root / redirects to the latest daily digest (or archive when empty)."""
        dates = sorted(manifest, reverse=True)
        relative_target = f"daily/{dates[0]}.html" if dates else "daily/index.html"
        base_url = (self.config.base_url or "").rstrip("/")
        target = f"{base_url}/{relative_target}" if base_url else relative_target
        return (
            "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<link rel="icon" href="data:,">\n'
            f'<meta http-equiv="refresh" content="0; url={_e(target)}">\n'
            "<title>Horizon</title>\n"
            "</head>\n<body>\n"
            f'<p>跳转中… <a href="{_e(target)}">进入 Horizon</a></p>\n'
            "</body>\n</html>\n"
        )

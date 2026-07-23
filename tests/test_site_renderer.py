"""Tests for the static reading-site renderer (digest / article / index)."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.models import ContentItem, SiteConfig, SourceType
from src.render.site import (
    SiteRenderer,
    archive_index_path,
    backfill_paper_library_navigation,
    daily_article_path,
    daily_digest_path,
    root_index_path,
)


def test_backfill_paper_library_navigation_updates_old_daily_pages_once(tmp_path):
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    digest = daily_dir / "2026-07-22.html"
    digest.write_text(
        '<span class="mast-links">'
        '<a href="../articles/index.html">文章库 ↗</a>'
        '<a href="index.html">归档 ↗</a></span>',
        encoding="utf-8",
    )
    current = daily_dir / "2026-07-23.html"
    current.write_text(
        '<a href="../articles/index.html">文章库 ↗</a>'
        '<a href="../papers/index.html">论文库 ↗</a>',
        encoding="utf-8",
    )
    unrelated = daily_dir / "article-1.html"
    unrelated.write_text('<a href="2026-07-22.html">返回</a>', encoding="utf-8")

    assert backfill_paper_library_navigation(tmp_path) == [digest]
    migrated = digest.read_text(encoding="utf-8")
    assert (
        '<a href="../articles/index.html">文章库 ↗</a>'
        '<a href="../papers/index.html">论文库 ↗</a>'
    ) in migrated
    assert backfill_paper_library_navigation(tmp_path) == []


def _item(tweet_id: str, title: str = "", **meta) -> ContentItem:
    metadata = {"tweet_id": tweet_id, "category": "ai-news"}
    metadata.update(meta)
    return ContentItem(
        id=f"twitter:tweet:{tweet_id}",
        source_type=SourceType.TWITTER,
        title=title or f"@dotey: tweet {tweet_id}",
        url=f"https://x.com/dotey/status/{tweet_id}",
        content=meta.get("_content", "tweet body"),
        author="dotey",
        published_at=datetime(2026, 7, 5, 8, 30, tzinfo=timezone.utc),
        metadata=metadata,
        ai_score=8.0,
        ai_summary="英文摘要",
        ai_tags=["AI"],
    )


def _six_shapes() -> list[ContentItem]:
    plain = _item(
        "1",
        title_zh="普通推文",
        media=[{"type": "photo", "thumbnail_url": "https://p/1.jpg"}],
        asset_map={"https://p/1.jpg": "assets/2026-07-05/aa.jpg"},
        detailed_summary_zh="中文摘要一",
        background_zh="背景说明",
    )
    rt = _item(
        "2",
        title_zh="转推嵌套",
        is_retweet=True,
        rt_original_author="sama",
        rt_original_text="original body https://openai.com/x",
        quoted_author="gdb",
        quoted_text="nested quote",
        quoted_media=[{"type": "photo", "thumbnail_url": "https://p/q.jpg"}],
        media=[],
    )
    qrt = _item(
        "3",
        title_zh="引用视频",
        is_quote=True,
        qrt_comment="我的评论",
        quoted_author="jakub",
        quoted_text="quoted with video",
        quoted_media=[
            {
                "type": "video",
                "thumbnail_url": "https://p/v.jpg",
                "mp4_url": "https://v/v.mp4",
                "duration_ms": 15000,
            }
        ],
        card={
            "title": "Transitions.dev",
            "domain": "transitions.dev",
            "thumbnail_url": "https://p/c.jpg",
            "card_url": "https://t.co/x",
        },
        links=[{"short_url": "https://t.co/x", "expanded_url": "https://transitions.dev", "display_url": "transitions.dev"}],
    )
    thread = _item(
        "4",
        title_zh="串推三条",
        conversation_id="4",
        thread_parts=[
            {"tweet_id": "4", "text": "第一段", "media": [{"type": "photo", "thumbnail_url": "https://p/t1.jpg"}], "links": []},
            {"tweet_id": "5", "text": "第二段", "media": [], "links": []},
        ],
        thread_length=2,
    )
    gif = _item(
        "6",
        title_zh="动图",
        media=[
            {
                "type": "animated_gif",
                "thumbnail_url": "https://p/g.jpg",
                "mp4_url": "https://v/g.mp4",
            }
        ],
        asset_map={"https://v/g.mp4": "assets/2026-07-05/gg.mp4"},
    )
    article = _item(
        "7",
        title_zh="X 文章",
        article={
            "article_id": "900",
            "title": "文章标题",
            "preview_text": "预览文字",
            "cover_url": "https://p/cover.jpg",
            "content_state": {
                "blocks": [
                    {"type": "unstyled", "text": "正文第一段", "inlineStyleRanges": [], "entityRanges": []}
                ],
                "entityMap": [],
            },
            "media_entities": [],
        },
        asset_map={"https://p/cover.jpg": "assets/2026-07-05/cv.jpg"},
    )
    return [plain, rt, qrt, thread, gif, article]


def _render(tmp_path, items=None):
    cfg = SiteConfig(
        enabled=True,
        output_dir=str(tmp_path),
        articles_source_dir=str(tmp_path / "no-articles"),
        papers_source_dir=str(tmp_path / "no-papers"),
    )
    renderer = SiteRenderer(cfg)
    return renderer.render(items or _six_shapes(), "2026-07-05", 18)


def _digest_item_html(digest: str, tweet_id: str) -> str:
    """Return one rendered digest item without depending on an HTML parser."""
    return digest.split(f'id="t-{tweet_id}"', 1)[1].split("</article>", 1)[0]


def test_digest_page_structure(tmp_path):
    paths = _render(tmp_path)
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")

    assert paths[0].name == "2026-07-05.html"
    assert digest.count('class="item"') == 6
    assert digest.count('<a href="#t-') == 6 + 6  # signal band + toc
    assert 'id="t-1"' in digest and 'id="t-7"' in digest
    assert "从 18 条抓取中筛选 <b>6</b> 条" in digest
    assert "7月5日" in digest and "星期日" in digest


def test_asset_map_hit_and_fallback(tmp_path):
    _render(tmp_path)
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    # mapped photo uses local path; unmapped nested-quote photo falls back
    assert 'src="../assets/2026-07-05/aa.jpg"' in digest
    assert 'src="https://p/q.jpg"' in digest


def test_rt_and_qrt_cards(tmp_path):
    _render(tmp_path)
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert "@dotey 转推了" in digest
    assert "<b>@sama</b>" in digest and "<b>@gdb</b>" in digest
    # bare URL in original text becomes a link
    assert '<a href="https://openai.com/x">' in digest
    # QRT: own link card resolves t.co to real destination
    assert '<a class="linkcard" href="https://transitions.dev">' in digest
    # quoted video rendered as player with poster
    assert '<video controls preload="metadata" poster="https://p/v.jpg">' in digest


def test_thread_and_gif_cards(tmp_path):
    _render(tmp_path)
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert "串推 2 条" in digest
    assert digest.count('class="tick') == 2
    assert "第一段" in digest and "第二段" in digest
    # GIF: local mp4, autoplay loop, badge
    assert '<video autoplay loop muted playsinline src="../assets/2026-07-05/gg.mp4">' in digest
    assert '<span class="tag">GIF</span>' in digest


def test_short_plain_tweet_stays_open_and_long_plain_tweet_folds(tmp_path):
    short = _item("20", _content="一条简短推文")
    long = _item("21", _content="长" * 241)

    _render(tmp_path, [short, long])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")

    assert 'class="tweet-fold"' not in _digest_item_html(digest, "20")
    long_html = _digest_item_html(digest, "21")
    assert '<details class="tweet-fold">' in long_html
    assert '<span class="when-closed">展开原推文</span>' in long_html
    assert '<span class="when-open">收起原推文</span>' in long_html
    assert '<details class="tweet-fold" open>' not in long_html


def test_four_explicit_newlines_trigger_fold(tmp_path):
    item = _item("22", _content="第一行\n第二行\n第三行\n第四行\n第五行")

    _render(tmp_path, [item])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")

    assert '<details class="tweet-fold">' in _digest_item_html(digest, "22")


def test_thread_fold_preserves_media_priority_counts_and_full_order(tmp_path):
    item = _item(
        "23",
        thread_parts=[
            {
                "tweet_id": "23",
                "text": "线程第一段",
                "media": [
                    {"type": "photo", "thumbnail_url": "https://p/root.jpg"}
                ],
                "links": [],
            },
            {
                "tweet_id": "24",
                "text": "线程第二段",
                "media": [
                    {
                        "type": "video",
                        "thumbnail_url": "https://p/later.jpg",
                        "mp4_url": "https://v/later.mp4",
                    }
                ],
                "links": [],
            },
        ],
        quoted_author="quoted",
        quoted_text="线程头部引用内容",
        quoted_media=[
            {
                "type": "video",
                "thumbnail_url": "https://p/quote.jpg",
                "mp4_url": "https://v/quote.mp4",
            }
        ],
        asset_map={"https://p/root.jpg": "assets/2026-07-05/root.jpg"},
    )

    _render(tmp_path, [item])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    item_html = _digest_item_html(digest, "23")

    preview = item_html.split('class="tweet-fold-body"', 1)[0]
    assert 'src="../assets/2026-07-05/root.jpg"' in preview
    assert 'src="https://p/quote.jpg"' not in preview
    assert '<span class="media-more">+2</span>' in preview
    assert "2 段 · 1 张图片 · 2 个视频" in preview

    full = item_html.split('class="tweet-fold-body"', 1)[1]
    assert full.index("线程第一段") < full.index("../assets/2026-07-05/root.jpg")
    assert full.index("../assets/2026-07-05/root.jpg") < full.index("https://p/quote.jpg")
    assert full.index("https://p/quote.jpg") < full.index("线程第二段")
    assert full.index("线程第二段") < full.index("https://p/later.jpg")


def test_quote_video_uses_static_preview_and_non_autoplay_full_player(tmp_path):
    item = _item(
        "25",
        is_quote=True,
        qrt_comment="推荐这个演示",
        quoted_author="demo",
        quoted_text="引用视频正文",
        quoted_media=[
            {
                "type": "animated_gif",
                "thumbnail_url": "https://p/demo.jpg",
                "mp4_url": "https://v/demo.mp4",
            }
        ],
        asset_map={"https://p/demo.jpg": "assets/2026-07-05/demo.jpg"},
    )

    _render(tmp_path, [item])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    item_html = _digest_item_html(digest, "25")
    preview, full = item_html.split('class="tweet-fold-body"', 1)

    assert '<img src="../assets/2026-07-05/demo.jpg"' in preview
    assert '<span class="media-play" aria-hidden="true">▶</span>' in preview
    assert "1 个视频" in preview
    assert "<video" not in preview
    assert '<video controls preload="metadata" poster="../assets/2026-07-05/demo.jpg">' in full
    assert " autoplay" not in full


def test_video_without_thumbnail_has_preview_placeholder(tmp_path):
    item = _item(
        "26",
        is_quote=True,
        qrt_comment="只有视频地址",
        quoted_author="demo",
        quoted_text="无封面视频",
        quoted_media=[{"type": "video", "mp4_url": "https://v/no-poster.mp4"}],
    )

    _render(tmp_path, [item])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    item_html = _digest_item_html(digest, "26")

    assert 'class="tweet-preview-media media-placeholder"' in item_html
    assert '<span class="media-placeholder-label">视频</span>' in item_html


def test_fold_preview_escapes_text_without_interactive_links(tmp_path):
    item = _item(
        "27",
        _content=("<script>bad()</script> https://example.com " + "长" * 241),
    )

    _render(tmp_path, [item])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    item_html = _digest_item_html(digest, "27")
    preview = item_html.split('class="tweet-fold-body"', 1)[0]

    assert "<script>bad()</script>" not in preview
    assert "&lt;script&gt;bad()&lt;/script&gt;" in preview
    assert '<a href="https://example.com">' not in preview


def test_folds_and_meta(tmp_path):
    _render(tmp_path)
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert "<details><summary>背景</summary>" in digest
    assert "在 X 打开" in digest
    assert "#AI" in digest


def test_article_card_and_page(tmp_path):
    paths = _render(tmp_path)
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert '<a class="articlecard" href="article-900.html">' in digest
    assert "全文已本地化" in digest

    article_page = tmp_path / "daily" / "article-900.html"
    assert article_page in paths
    content = article_page.read_text(encoding="utf-8")
    assert "<p>正文第一段</p>" in content
    # cover resolved with ../ prefix from articles/ subdir
    assert 'src="../assets/2026-07-05/cv.jpg"' in content
    assert 'href="2026-07-05.html#t-7"' in content
    assert 'href="../papers/index.html">论文库</a>' in content


def test_article_without_fulltext_links_to_x(tmp_path):
    item = _item(
        "8",
        title_zh="未抓到全文",
        article={"article_id": "901", "title": "仅预览", "preview_text": "p"},
    )
    _render(tmp_path, [item])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert '<a class="articlecard" href="https://x.com/dotey/status/8">' in digest
    assert not (tmp_path / "daily" / "article-901.html").exists()


def test_index_manifest_accumulates(tmp_path):
    _render(tmp_path)
    cfg = SiteConfig(enabled=True, output_dir=str(tmp_path))
    SiteRenderer(cfg).render([_item("9", title_zh="次日条目")], "2026-07-06", 5)

    manifest = json.loads((tmp_path / "site_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"2026-07-05", "2026-07-06"}

    index = (tmp_path / "daily" / "index.html").read_text(encoding="utf-8")
    assert index.index("2026-07-06.html") < index.index("2026-07-05.html")
    assert "2026 年 7 月" in index
    assert "次日条目" in index


def test_root_index_redirects_to_latest(tmp_path):
    _render(tmp_path)
    cfg = SiteConfig(enabled=True, output_dir=str(tmp_path))
    SiteRenderer(cfg).render([_item("9", title_zh="次日条目")], "2026-07-06", 5)

    root = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "url=daily/2026-07-06.html" in root
    assert 'http-equiv="refresh"' in root


def test_root_index_uses_canonical_base_url_when_configured(tmp_path):
    renderer = SiteRenderer(
        SiteConfig(
            enabled=True,
            output_dir=str(tmp_path),
            base_url="https://www.signalfeed.site/",
        )
    )

    root = renderer._root_index_page({"2026-07-06": {}})

    assert "url=https://www.signalfeed.site/daily/2026-07-06.html" in root
    assert 'href="https://www.signalfeed.site/daily/2026-07-06.html"' in root


def test_path_helpers_return_sectioned_site_paths():
    assert daily_digest_path("2026-07-05").as_posix() == "daily/2026-07-05.html"
    assert daily_article_path("900").as_posix() == "daily/article-900.html"
    assert archive_index_path().as_posix() == "daily/index.html"
    assert root_index_path().as_posix() == "index.html"


def test_root_index_falls_back_to_daily_archive_without_history(tmp_path):
    renderer = SiteRenderer(SiteConfig(enabled=True, output_dir=str(tmp_path)))

    root = renderer._root_index_page({})

    assert "url=daily/index.html" in root


def test_render_migrates_legacy_daily_and_x_article_paths(tmp_path):
    (tmp_path / "2026-07-04.html").write_text(
        '<img src="assets/2026-07-04/photo.jpg">'
        '<a href="articles/900.html">article</a>',
        encoding="utf-8",
    )
    legacy_articles = tmp_path / "articles"
    legacy_articles.mkdir()
    (legacy_articles / "900.html").write_text(
        '<a href="../2026-07-04.html#t-1">back</a>', encoding="utf-8"
    )

    _render(tmp_path, [_item("1")])

    assert not (tmp_path / "2026-07-04.html").exists()
    migrated_digest = (tmp_path / "daily" / "2026-07-04.html").read_text(
        encoding="utf-8"
    )
    assert 'src="../assets/2026-07-04/photo.jpg"' in migrated_digest
    assert 'href="article-900.html"' in migrated_digest

    assert not (legacy_articles / "900.html").exists()
    migrated_article = (tmp_path / "daily" / "article-900.html").read_text(
        encoding="utf-8"
    )
    assert 'href="2026-07-04.html#t-1"' in migrated_article


def test_dynamic_text_is_escaped(tmp_path):
    evil = _item(
        "10",
        title_zh='<script>alert(1)</script>',
        detailed_summary_zh='<img onerror=x>',
        _content="body <script>bad</script>",
    )
    _render(tmp_path, [evil])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in digest
    assert "&lt;script&gt;" in digest
    assert "<img onerror" not in digest


def test_bare_article_link_stripped_when_card_present(tmp_path):
    item = _item(
        "11",
        title_zh="带文章链接",
        _content="推荐这篇 http://x.com/i/article/900 值得一读",
        article={"article_id": "900", "title": "文章", "preview_text": "p"},
    )
    _render(tmp_path, [item])
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert "/i/article/900" not in digest.split('class="articlecard"')[0].split('t-text')[-1]
    assert "推荐这篇" in digest and "值得一读" in digest


def test_digest_links_to_articles_library(tmp_path):
    _render(tmp_path)  # empty articles source → recent count 0
    digest = (tmp_path / "daily" / "2026-07-05.html").read_text(encoding="utf-8")
    assert 'href="../articles/index.html"' in digest
    assert "文章库 ↗" in digest
    assert "文章库本周" not in digest  # hidden when recent count is 0


def test_site_renderer_builds_paper_library_and_links_global_navigation(tmp_path):
    cfg = SiteConfig(
        enabled=True,
        output_dir=str(tmp_path),
        articles_source_dir=str(tmp_path / "no-articles"),
        papers_source_dir="papers",
    )
    paths = SiteRenderer(cfg).render(_six_shapes(), "2026-07-09", 18)

    paper_index = tmp_path / "papers" / "index.html"
    assert paper_index in paths
    index_html = paper_index.read_text(encoding="utf-8")
    assert index_html.count("data-paper-entry") == len(
        list(Path("papers").glob("*.md"))
    )

    digest = (tmp_path / "daily" / "2026-07-09.html").read_text(encoding="utf-8")
    archive = (tmp_path / "daily" / "index.html").read_text(encoding="utf-8")
    article_index = (tmp_path / "articles" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'href="../papers/index.html">论文库 ↗</a>' in digest
    assert 'href="../papers/index.html">论文库 ↗</a>' in archive
    assert 'href="../papers/index.html">论文库</a>' in article_index


def test_digest_shows_articles_weekly_count(tmp_path):
    cfg = SiteConfig(
        enabled=True,
        output_dir=str(tmp_path),
        articles_source_dir="tests/fixtures/articles",
    )
    SiteRenderer(cfg).render(_six_shapes(), "2026-07-09", 18)
    digest = (tmp_path / "daily" / "2026-07-09.html").read_text(encoding="utf-8")
    assert "文章库本周 +1" in digest  # fixture added 2026-07-08 within 7 days
    assert 'href="../articles/index.html">文章库本周 +1</a>' in digest


def test_daily_render_needs_only_compact_manifest_not_historical_pages(tmp_path):
    start = date(2025, 7, 23)
    history = {
        (start + timedelta(days=offset)).isoformat(): {"count": 1, "top": []}
        for offset in range(365)
    }
    (tmp_path / "site_manifest.json").write_text(
        json.dumps(history), encoding="utf-8"
    )
    cfg = SiteConfig(
        enabled=True,
        output_dir=str(tmp_path),
        articles_source_dir=str(tmp_path / "no-articles"),
    )

    paths = SiteRenderer(cfg).render_daily([], "2026-07-22", 0)

    assert tmp_path / "daily" / "2026-07-22.html" in paths
    assert not (tmp_path / "daily" / "2025-07-23.html").exists()
    assert not (tmp_path / "articles").exists()
    assert not (tmp_path / "papers").exists()
    digest = (tmp_path / "daily" / "2026-07-22.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="../assets/site/horizon.css">' in digest
    assert (tmp_path / "assets" / "site" / "horizon.css").is_file()

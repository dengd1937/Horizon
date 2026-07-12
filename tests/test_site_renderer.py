"""Tests for the static reading-site renderer (digest / article / index)."""

import json
from datetime import datetime, timezone

from src.models import ContentItem, SiteConfig, SourceType
from src.render.site import SiteRenderer


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
    )
    renderer = SiteRenderer(cfg)
    return renderer.render(items or _six_shapes(), "2026-07-05", 18)


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


def test_digest_shows_articles_weekly_count(tmp_path):
    cfg = SiteConfig(
        enabled=True,
        output_dir=str(tmp_path),
        articles_source_dir="tests/fixtures/articles",
    )
    SiteRenderer(cfg).render(_six_shapes(), "2026-07-09", 18)
    digest = (tmp_path / "daily" / "2026-07-09.html").read_text(encoding="utf-8")
    assert "文章库本周 +1" in digest  # fixture added 2026-07-08 within 7 days

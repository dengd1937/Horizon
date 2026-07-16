"""Tests for curated article parsing and rendering."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import yaml
from bs4 import BeautifulSoup

from src.models import SiteConfig
from src.render.assets import MediaDownloader
from src.render.curated import (
    ArticleValidationError,
    article_media_urls,
    count_recent,
    detail_page_html,
    index_page_html,
    place_new_articles_after_overview,
    load_article,
    load_articles,
    localize_article_media,
    new_articles_section,
    render_curated,
    slugify,
)
from src.render.site import SiteRenderer

FIXTURES = Path(__file__).parent / "fixtures" / "articles"
INVALID = Path(__file__).parent / "fixtures" / "articles-invalid"
PROJECT_ROOT = Path(__file__).parents[1]


def _downloader(tmp_path, handler, max_mb: int = 50) -> MediaDownloader:
    config = SiteConfig(enabled=True, output_dir=str(tmp_path), max_media_mb=max_mb)
    return MediaDownloader(config, transport=httpx.MockTransport(handler))


def _image_response(content: bytes = b"IMAGE") -> httpx.Response:
    return httpx.Response(
        200, headers={"content-type": "image/jpeg"}, content=content
    )


def test_load_articles_sorts_by_added_date_desc():
    articles = load_articles(FIXTURES)
    assert [a.slug for a in articles] == [
        "overreacted-io-20260708-the-tides-of-tech",
        "martinfowler-com-20260615-refactoring",
        "paulgraham-com-20260520-do-things",
    ]


def test_published_articles_use_controlled_tag_vocabulary():
    taxonomy = yaml.safe_load(
        (PROJECT_ROOT / "data" / "article-tags.yaml").read_text(encoding="utf-8")
    )
    names = [entry["name"] for entry in taxonomy["tags"]]
    rules = taxonomy["rules"]
    order = {name: index for index, name in enumerate(names)}

    assert taxonomy["version"] == 1
    assert len(names) == len(set(names))
    assert set(taxonomy["legacy_aliases"].values()) <= set(names)

    for article in load_articles(PROJECT_ROOT / "articles"):
        assert rules["minimum_per_article"] <= len(article.tags)
        assert len(article.tags) <= rules["maximum_per_article"]
        assert len(article.tags) == len(set(article.tags))
        assert set(article.tags) <= set(names)
        assert article.tags == sorted(article.tags, key=order.__getitem__)


def test_load_article_parses_all_fields():
    by_slug = {a.slug: a for a in load_articles(FIXTURES)}
    art = by_slug["overreacted-io-20260708-the-tides-of-tech"]
    assert art.title == "技术的潮汐"
    assert art.source_domain == "overreacted.io"
    assert art.source_url == "https://overreacted.io/the-tides-of-tech/"
    assert art.tags == ["技术", "随想"]
    assert art.cover is not None
    assert art.intro is not None
    assert "涨潮" in art.body_md


def test_optional_fields_absent_when_omitted():
    by_slug = {a.slug: a for a in load_articles(FIXTURES)}
    art = by_slug["martinfowler-com-20260615-refactoring"]
    assert art.cover is None
    assert art.intro is None
    assert art.tags == ["工程实践", "重构"]


def test_missing_required_field_raises():
    with pytest.raises(ArticleValidationError) as exc:
        load_article(INVALID / "missing-title.md")
    assert "title" in str(exc.value)


def test_slugify_is_stable_and_safe():
    assert (
        slugify("overreacted.io", "2026-07-08", "The Tides of Tech")
        == "overreacted-io-20260708-the-tides-of-tech"
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("source_url", "javascript:alert(1)", "source_url must be an absolute"),
        ("cover", "http://media.example/cover.jpg", "cover must be an absolute https"),
    ],
)
def test_unsafe_frontmatter_urls_are_rejected(tmp_path, field, value, expected):
    source = (FIXTURES / "overreacted-io-20260708-the-tides-of-tech.md").read_text(
        encoding="utf-8"
    )
    source = source.replace(
        "cover: https://media.example/overreacted-cover.jpg",
        f"{field}: {value}",
    )
    path = tmp_path / "overreacted-io-20260708-the-tides-of-tech.md"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ArticleValidationError, match=expected):
        load_article(path)


def test_non_https_body_image_is_rejected(tmp_path):
    source = (FIXTURES / "overreacted-io-20260708-the-tides-of-tech.md").read_text(
        encoding="utf-8"
    ).replace("https://media.example/overreacted-tide.jpg", "http://media.example/tide.jpg")
    path = tmp_path / "overreacted-io-20260708-the-tides-of-tech.md"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ArticleValidationError, match="body image must be an absolute https"):
        load_article(path)


def test_load_articles_missing_dir_returns_empty(tmp_path):
    assert load_articles(tmp_path / "nope") == []


def test_detail_page_newest_has_no_newer(tmp_path):
    articles = load_articles(FIXTURES)
    asyncio.run(
        localize_article_media(
            articles, _downloader(tmp_path, lambda r: _image_response())
        )
    )
    newest = articles[0]
    older = articles[1]
    html_ = detail_page_html(newest, older=older, newer=None)
    assert 'class="next"' not in html_
    assert f'href="{older.slug}.html"' in html_
    # cover rewritten to detail-page-relative
    assert 'src="../assets/articles/overreacted-io-20260708-the-tides-of-tech/' in html_
    # source link + reprint notice
    assert "阅读原文" in html_
    assert "本文转载自 overreacted.io" in html_
    # body markdown rendered
    assert "<ul>" in html_
    assert "<blockquote>" in html_
    assert ".prose img, .prose video" in html_
    assert "width: 100%; max-width: 100%; height: auto" in html_
    # inline body image rewritten to ../assets/
    assert 'src="../assets/articles/overreacted-io-20260708-the-tides-of-tech/' in html_


def test_detail_page_oldest_has_no_older():
    articles = load_articles(FIXTURES)
    oldest = articles[-1]
    newer = articles[-2]
    html_ = detail_page_html(oldest, older=None, newer=newer)
    assert 'class="prev"' not in html_
    assert f'href="{newer.slug}.html"' in html_


def test_article_media_localization_only_collects_images_and_writes_files(tmp_path):
    articles = load_articles(FIXTURES)
    article = articles[0]
    assert article_media_urls(article) == [
        "https://media.example/overreacted-cover.jpg",
        "https://media.example/overreacted-tide.jpg",
    ]

    downloaded = asyncio.run(
        localize_article_media(
            articles, _downloader(tmp_path, lambda r: _image_response())
        )
    )

    assert downloaded == 2
    assert len(article.asset_map) == 2
    for path in article.asset_map.values():
        assert path.startswith(f"assets/articles/{article.slug}/")
        assert (tmp_path / path).read_bytes() == b"IMAGE"
    html_ = detail_page_html(article, older=None, newer=None)
    assert "../assets/articles/" in html_
    assert 'href="https://example.com"' in html_


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),
        httpx.Response(
            200,
            headers={"content-type": "image/jpeg"},
            content=b"x" * (2 * 1024 * 1024),
        ),
    ],
)
def test_article_media_failure_or_oversize_keeps_original_https_url(tmp_path, response):
    article = load_articles(FIXTURES)[0]
    max_mb = 1 if response.status_code == 200 else 50
    downloaded = asyncio.run(
        localize_article_media(
            [article], _downloader(tmp_path, lambda r: response, max_mb=max_mb)
        )
    )

    assert downloaded == 0
    assert article.asset_map == {}
    html_ = detail_page_html(article, older=None, newer=None)
    assert 'src="https://media.example/overreacted-cover.jpg"' in html_
    assert 'src="https://media.example/overreacted-tide.jpg"' in html_


def test_invalid_articles_do_not_write_partial_site_pages(tmp_path):
    config = SiteConfig(
        enabled=True,
        output_dir=str(tmp_path / "site"),
        articles_source_dir=str(INVALID),
    )

    with pytest.raises(ArticleValidationError, match="title"):
        SiteRenderer(config).render([], "2026-07-09", 0)

    assert not list((tmp_path / "site").rglob("*.html"))


def test_detail_page_sanitizes_active_html_and_unsafe_links():
    article = load_articles(FIXTURES)[0]
    article.body_md = (
        "# 安全正文\n\n"
        '<script>globalThis.HORIZON_XSS = 1</script>\n\n'
        '[危险链接](javascript:alert(1))\n\n'
        '<video controls onclick="alert(1)" '
        'src="https://media.example/demo.mp4"></video>\n\n'
        '<img src="https://127.0.0.1/internal" alt="内网">'
    )

    html_ = detail_page_html(article, older=None, newer=None)

    assert "<script" not in html_
    assert "javascript:" not in html_
    assert "onclick" not in html_
    assert '<video controls="" src="https://media.example/demo.mp4"></video>' in html_
    assert "https://127.0.0.1/internal" not in html_
    assert "Content-Security-Policy" in html_
    assert "script-src 'none'" in html_


def test_index_page_renders_progressive_filter_controls_and_safe_data():
    articles = load_articles(FIXTURES)
    html_ = index_page_html(articles)
    soup = BeautifulSoup(html_, "html.parser")

    root = soup.select_one("[data-article-library]")
    controls = soup.select_one("[data-article-filter]")
    assert root is not None
    assert controls is not None and controls.has_attr("hidden")
    assert soup.select_one('input[type="search"][data-article-search]') is not None
    assert soup.select_one("[data-article-reset]").has_attr("hidden")
    assert soup.select_one("[data-article-results]").get_text(strip=True) == "共 3 篇文章"

    buttons = soup.select("[data-article-tag]")
    assert buttons[0]["data-tag"] == ""
    assert buttons[0]["aria-pressed"] == "true"
    assert buttons[0].get_text(" ", strip=True) == "全部 3"
    assert [button["data-tag"] for button in buttons[1:]] == sorted(
        {tag for article in articles for tag in article.tags}, key=str.casefold
    )

    entries = soup.select("[data-article-entry]")
    assert len(entries) == len(articles)
    for entry, article in zip(entries, articles):
        assert json.loads(entry["data-tags"]) == article.tags
    assert len(soup.select("[data-article-group]")) == 3

    script = soup.select_one('script[src="article-index.js"]')
    assert script is not None and script.has_attr("defer")
    csp = soup.select_one('meta[http-equiv="Content-Security-Policy"]')["content"]
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src", 1)[1]


def test_index_filter_tags_hide_universal_count_once_and_sort_deterministically():
    base = load_articles(FIXTURES)[0]
    articles = [
        replace(base, slug="one", tags=["共同", "Beta", "Alpha", "Beta"]),
        replace(base, slug="two", tags=["共同", "Beta", "Gamma"]),
        replace(base, slug="three", tags=["共同", "Alpha", "Gamma"]),
    ]
    soup = BeautifulSoup(index_page_html(articles), "html.parser")
    buttons = soup.select("[data-article-tag]")

    assert [button["data-tag"] for button in buttons] == [
        "",
        "Alpha",
        "Beta",
        "Gamma",
    ]
    assert all(
        button.select_one("span").get_text(strip=True) == "2"
        for button in buttons[1:]
    )
    assert not soup.select('[data-article-tag][data-tag="共同"]')


def test_index_data_tags_escape_attribute_special_characters():
    base = load_articles(FIXTURES)[0]
    tag = 'R&D "tools" <safe>'
    html_ = index_page_html([replace(base, tags=[tag])])
    soup = BeautifulSoup(html_, "html.parser")

    assert json.loads(soup.select_one("[data-article-entry]")["data-tags"]) == [tag]
    assert 'data-tags="[&quot;R&amp;D \\&quot;tools\\&quot; &lt;safe&gt;&quot;]"' in html_
    assert soup.find("safe") is None


def test_render_curated_produces_index_and_details(tmp_path):
    articles = load_articles(FIXTURES)
    paths = render_curated(tmp_path, articles)
    arts = tmp_path / "articles"
    assert (arts / "index.html") in paths
    script = arts / "article-index.js"
    assert script.is_file()
    assert "data-article-entry" in script.read_text(encoding="utf-8")
    assert script not in paths
    for a in articles:
        assert (arts / f"{a.slug}.html") in paths
    idx = (arts / "index.html").read_text(encoding="utf-8")
    assert "2026 年 7 月" in idx
    assert "2026 年 6 月" in idx
    assert "2026 年 5 月" in idx
    assert idx.index("2026 年 7 月") < idx.index("2026 年 5 月")


def test_render_curated_empty_state(tmp_path):
    paths = render_curated(tmp_path, [])
    idx = (tmp_path / "articles" / "index.html").read_text(encoding="utf-8")
    assert "暂无文章" in idx
    assert "data-article-filter" not in idx
    assert '<script defer src="article-index.js"></script>' not in idx
    assert "script-src 'none'" in idx
    assert paths == [tmp_path / "articles" / "index.html"]


def test_count_recent_window():
    articles = load_articles(FIXTURES)  # added: 2026-07-08, 2026-06-15, 2026-05-20
    assert count_recent(articles, today="2026-07-09", days=7) == 1   # only 07-08
    assert count_recent(articles, today="2026-07-09", days=60) == 3  # all three
    assert count_recent(articles, today="2026-04-01", days=7) == 0   # before any


def test_count_recent_uses_report_date_utc_rolling_seven_day_window():
    article = load_articles(FIXTURES)[0]
    articles = [
        replace(article, added_date="2026-07-03"),  # first included date
        replace(article, added_date="2026-07-09"),  # report date itself
        replace(article, added_date="2026-07-02"),  # just outside the window
        replace(article, added_date="2026-07-10"),  # future addition
    ]

    assert count_recent(articles, today="2026-07-09") == 2
    assert count_recent(articles, today="2026-07-09", days=1) == 1
    with pytest.raises(ValueError, match="at least 1"):
        count_recent(articles, today="2026-07-09", days=0)


def test_count_recent_empty():
    assert count_recent([], today="2026-07-09") == 0


def test_new_articles_section_filters_and_formats():
    articles = load_articles(FIXTURES)  # added: 07-08, 06-15, 05-20
    section = new_articles_section(
        articles, base_url="https://h.example/", since="2026-07-07", today="2026-07-09"
    )
    assert "## 本期新增精选文章" in section
    assert "技术的潮汐" in section
    assert "overreacted.io" in section
    assert (
        "https://h.example/articles/overreacted-io-20260708-the-tides-of-tech.html"
        in section
    )
    assert "martinfowler" not in section
    assert "paulgraham" not in section


def test_new_articles_section_empty_when_none():
    articles = load_articles(FIXTURES)
    section = new_articles_section(
        articles, base_url="https://h.example", since="2026-07-09", today="2026-07-09"
    )
    assert section == ""


def test_new_articles_section_is_placed_after_overview_before_daily_items():
    summary = "# Daily\n\n> 今日概览\n\n---\n\n1. 今日动态"
    section = "\n\n## 本期新增精选文章\n\n- **测试文章**"

    result = place_new_articles_after_overview(summary, section)

    assert result.index("# Daily") < result.index("今日概览")
    assert result.index("今日概览") < result.index("本期新增精选文章")
    assert result.index("本期新增精选文章") < result.index("---")
    assert result.index("---") < result.index("1. 今日动态")


def test_placing_an_empty_new_articles_section_leaves_summary_unchanged():
    summary = "# Daily\n\n> 今日概览\n\n---\n\n1. 今日动态"

    assert place_new_articles_after_overview(summary, "") == summary


def test_new_articles_section_keeps_same_day_additions_without_resending_slugs():
    articles = load_articles(FIXTURES)
    newest = articles[0]

    section = new_articles_section(
        articles,
        base_url="https://h.example",
        since="2026-07-08",
        today="2026-07-09",
    )
    assert newest.title in section

    delivered_section = new_articles_section(
        articles,
        base_url="https://h.example",
        since="2026-07-08",
        today="2026-07-09",
        delivered_slugs={newest.slug},
    )
    assert delivered_section == ""

"""Tests for curated article parsing and rendering."""

from pathlib import Path

import pytest

from src.render.curated import (
    ArticleValidationError,
    count_recent,
    detail_page_html,
    load_article,
    load_articles,
    new_articles_section,
    render_curated,
)

FIXTURES = Path(__file__).parent / "fixtures" / "articles"
INVALID = Path(__file__).parent / "fixtures" / "articles-invalid"


def test_load_articles_sorts_by_added_date_desc():
    articles = load_articles(FIXTURES)
    assert [a.slug for a in articles] == [
        "overreacted-io-20260708-the-tides-of-tech",
        "martinfowler-com-20260615-refactoring",
        "paulgraham-com-20260520-do-things",
    ]


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


def test_load_articles_missing_dir_returns_empty(tmp_path):
    assert load_articles(tmp_path / "nope") == []


def test_detail_page_newest_has_no_newer():
    articles = load_articles(FIXTURES)
    newest = articles[0]
    older = articles[1]
    html_ = detail_page_html(newest, older=older, newer=None)
    assert 'class="next"' not in html_
    assert f'href="{older.slug}.html"' in html_
    # cover rewritten to detail-page-relative
    assert 'src="../assets/articles/' in html_
    # source link + reprint notice
    assert "阅读原文" in html_
    assert "本文转载自 overreacted.io" in html_
    # body markdown rendered
    assert "<ul>" in html_
    assert "<blockquote>" in html_
    # inline body image rewritten to ../assets/
    assert (
        'src="../assets/articles/overreacted-io-20260708-the-tides-of-tech/tide.jpg"'
        in html_
    )


def test_detail_page_oldest_has_no_older():
    articles = load_articles(FIXTURES)
    oldest = articles[-1]
    newer = articles[-2]
    html_ = detail_page_html(oldest, older=None, newer=newer)
    assert 'class="prev"' not in html_
    assert f'href="{newer.slug}.html"' in html_


def test_render_curated_produces_index_and_details(tmp_path):
    articles = load_articles(FIXTURES)
    paths = render_curated(tmp_path, articles)
    arts = tmp_path / "articles"
    assert (arts / "index.html") in paths
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
    assert paths == [tmp_path / "articles" / "index.html"]


def test_count_recent_window():
    articles = load_articles(FIXTURES)  # added: 2026-07-08, 2026-06-15, 2026-05-20
    assert count_recent(articles, today="2026-07-09", days=7) == 1   # only 07-08
    assert count_recent(articles, today="2026-07-09", days=60) == 3  # all three
    assert count_recent(articles, today="2026-04-01", days=7) == 0   # before any


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

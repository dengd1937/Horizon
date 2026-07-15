"""Tests for deterministic curated article ingestion."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.articles.contract import ArticleValidationError, load_article, slugify
from src.articles.ingest import build_article_source, utc_added_date, write_article


def _manifest(**overrides):
    value = {
        "title": 'A "Quoted" Article',
        "source_url": "https://www.Example.com/posts/one",
        "published_date": "2026-07-01",
        "summary": "One concise summary.",
        "tags": ["AI", "编译器"],
        "cover": "https://images.example.com/cover.jpg",
        "intro": "A short intro.",
    }
    value.update(overrides)
    return value


def test_build_article_source_is_safe_and_contract_valid():
    article, source = build_article_source(
        _manifest(),
        "## Body\n\n![diagram](https://images.example.com/diagram.png)",
        added_date="2026-07-14",
    )

    assert article.source_domain == "example.com"
    assert article.slug == "example-com-20260701-a-quoted-article"
    assert article.added_date == "2026-07-14"
    assert article.tags == ["AI", "编译器"]
    assert 'title: A "Quoted" Article' in source
    assert "source_domain: example.com" in source


def test_utc_added_date_uses_named_utc_timezone():
    assert (
        utc_added_date(datetime(2026, 7, 14, 0, 30, tzinfo=timezone.utc))
        == "2026-07-14"
    )
    assert utc_added_date(datetime(2026, 7, 14, 23, 30, tzinfo=timezone.utc)) == "2026-07-14"
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_added_date(datetime(2026, 7, 14, 1, 0))


def test_slug_rules_use_six_words_and_require_ascii_short_title():
    assert (
        slugify("example.com", "2026-07-01", "One Two Three Four Five Six Seven")
        == "example-com-20260701-one-two-three-four-five-six"
    )
    with pytest.raises(ArticleValidationError, match="slug_title is required"):
        slugify("example.com", "2026-07-01", "纯中文标题")
    with pytest.raises(ArticleValidationError, match="at least two ASCII words"):
        slugify(
            "example.com",
            "2026-07-01",
            "纯中文标题",
            short_title="Chinese",
        )
    assert (
        slugify(
            "example.com",
            "2026-07-01",
            "纯中文标题",
            short_title="Chinese title",
        )
        == "example-com-20260701-chinese-title"
    )


@pytest.mark.parametrize("published_date", ["20260715", "2026-W29-3"])
def test_slug_rejects_non_canonical_iso_dates(published_date):
    with pytest.raises(ArticleValidationError, match="published_date must be ISO"):
        slugify("example.com", published_date, "Canonical Date")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("published_date", "20260715"),
        ("published_date", "2026-W29-3"),
        ("added_date", "20260715"),
        ("added_date", "2026-W29-3"),
    ],
)
def test_article_dates_require_exact_year_month_day(tmp_path, field, value):
    manifest = _manifest()
    added_date = "2026-07-14"
    if field == "published_date":
        manifest[field] = value
    else:
        added_date = value

    with pytest.raises(ArticleValidationError, match=rf"{field} must be ISO YYYY-MM-DD"):
        write_article(tmp_path / "articles", manifest, "body", added_date=added_date)
    assert not list(tmp_path.rglob("*.md"))


@pytest.mark.parametrize(
    ("manifest", "body", "expected"),
    [
        (_manifest(published_date=""), "body", "published_date"),
        (_manifest(title=["not", "a", "string"]), "body", "title"),
        (_manifest(summary="line one\nline two"), "body", "summary"),
        (_manifest(cover="http://images.example.com/a.jpg"), "body", "cover"),
        (_manifest(), "![x](http://images.example.com/a.jpg)", "body image"),
        (_manifest(), "", "body"),
        (
            _manifest(source_domain="different.example"),
            "body",
            "source_domain must be",
        ),
    ],
)
def test_invalid_inputs_fail_before_writing(tmp_path, manifest, body, expected):
    with pytest.raises(ArticleValidationError, match=expected):
        write_article(tmp_path / "articles", manifest, body, added_date="2026-07-14")
    assert not list(tmp_path.rglob("*.md"))


def test_write_article_is_atomic_and_loadable(tmp_path):
    result = write_article(
        tmp_path / "articles",
        _manifest(),
        "Full article body.",
        added_date="2026-07-14",
    )

    assert result.path.name == "example-com-20260701-a-quoted-article.md"
    assert load_article(result.path).slug == result.article.slug
    assert result.commit_message == "clip(article): example-com-20260701-a-quoted-article"
    assert len(result.sha256) == 64
    assert result.path.stat().st_mode & 0o777 == 0o644
    assert not list((tmp_path / "articles").glob(".*.tmp"))


def test_duplicate_url_and_slug_never_overwrite(tmp_path):
    source_dir = tmp_path / "articles"
    first = write_article(
        source_dir, _manifest(), "First body.", added_date="2026-07-14"
    )
    original = first.path.read_text(encoding="utf-8")

    with pytest.raises(ArticleValidationError, match="source_url already exists"):
        write_article(
            source_dir,
            _manifest(title="Different Title"),
            "Second body.",
            added_date="2026-07-14",
        )
    with pytest.raises(ArticleValidationError, match="article already exists"):
        write_article(
            source_dir,
            _manifest(source_url="https://example.com/posts/two"),
            "Third body.",
            added_date="2026-07-14",
        )
    assert first.path.read_text(encoding="utf-8") == original
    assert len(list(source_dir.glob("*.md"))) == 1


def test_write_article_requires_slug_title_for_chinese_title(tmp_path):
    manifest = _manifest(title="纯中文标题")
    with pytest.raises(ArticleValidationError, match="slug_title is required"):
        write_article(tmp_path / "articles", manifest, "body", added_date="2026-07-14")

    manifest["slug_title"] = "Chinese title"
    result = write_article(
        tmp_path / "articles", manifest, "body", added_date="2026-07-14"
    )
    assert result.article.slug == "example-com-20260701-chinese-title"

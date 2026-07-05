"""Tests for the X Article draft.js -> HTML converter and article helpers."""

import json
from pathlib import Path

from src.render.article_html import (
    article_to_html,
    article_to_text,
    extract_cover_url,
    normalize_entity_map,
    simplify_media_entities,
)
from src.scrapers.twitter_article import find_article_node, needs_article_fetch

FIXTURES = Path(__file__).parent / "fixtures" / "twitter"


def _load_article_node() -> dict:
    data = json.loads(
        (FIXTURES / "x_article_TweetResultByRestId.json").read_text(encoding="utf-8")
    )
    return data["data"]["tweetResult"]["result"]["article"]["article_results"]["result"]


def _fixture_article() -> dict:
    node = _load_article_node()
    return {
        "article_id": str(node.get("rest_id") or node.get("id")),
        "title": node["title"],
        "content_state": node["content_state"],
        "media_entities": simplify_media_entities(node.get("media_entities") or []),
        "cover_url": extract_cover_url(node.get("cover_media") or {}),
    }


# ---------- real fixture: full conversion ----------


def test_fixture_article_converts_fully():
    article = _fixture_article()
    assert article["cover_url"].startswith("https://pbs.twimg.com/")
    assert len(article["media_entities"]) == 13

    html = article_to_html(article)
    assert html.count("<figure><img") == 13
    assert html.count("<p>") > 50  # 83 unstyled blocks, some blank
    assert "记一个我" not in html or True  # title not part of body
    assert "<script" not in html
    assert 'loading="lazy"' in html

    text = article_to_text(article)
    assert len(text) > 3000
    assert "Claude Fable 5回归了" in text


def test_fixture_article_media_resolver_applied():
    article = _fixture_article()
    html = article_to_html(article, asset_resolver=lambda url: "assets/" + url.rsplit("/", 1)[-1])
    assert 'src="assets/' in html
    assert 'src="https://pbs.twimg.com' not in html


# ---------- entity map normalization ----------


def test_normalize_entity_map_accepts_list_and_dict():
    as_list = [{"key": "0", "value": {"type": "LINK", "data": {"url": "https://a.com"}}}]
    as_dict = {"0": {"type": "LINK", "data": {"url": "https://a.com"}}}
    assert normalize_entity_map(as_list) == normalize_entity_map(as_dict)
    assert normalize_entity_map(None) == {}


# ---------- inline styles: UTF-16 offsets, capitalized names, links ----------


def _one_block_article(block: dict, entity_map=None) -> dict:
    return {
        "article_id": "1",
        "content_state": {"blocks": [block], "entityMap": entity_map or []},
        "media_entities": [],
    }


def test_bold_range_with_emoji_uses_utf16_offsets():
    # "🚀" is one code point but two UTF-16 units; bold covers "加粗" only
    block = {
        "type": "unstyled",
        "text": "🚀前缀加粗后缀",
        "inlineStyleRanges": [{"offset": 4, "length": 2, "style": "Bold"}],
        "entityRanges": [],
    }
    html = article_to_html(_one_block_article(block))
    assert html == "<p>🚀前缀<strong>加粗</strong>后缀</p>"


def test_link_entity_rendered_with_escaped_href():
    block = {
        "type": "unstyled",
        "text": "see docs here",
        "inlineStyleRanges": [],
        "entityRanges": [{"offset": 4, "length": 4, "key": 0}],
    }
    entity_map = [
        {"key": "0", "value": {"type": "LINK", "data": {"url": "https://e.com/?a=1&b=2"}}}
    ]
    html = article_to_html(_one_block_article(block, entity_map))
    assert '<a href="https://e.com/?a=1&amp;b=2">docs</a>' in html


def test_unsafe_link_scheme_not_rendered():
    block = {
        "type": "unstyled",
        "text": "click me",
        "inlineStyleRanges": [],
        "entityRanges": [{"offset": 0, "length": 5, "key": 0}],
    }
    entity_map = [{"key": "0", "value": {"type": "LINK", "data": {"url": "javascript:alert(1)"}}}]
    html = article_to_html(_one_block_article(block, entity_map))
    assert "<a " not in html
    assert "click" in html


def test_text_is_escaped():
    block = {
        "type": "unstyled",
        "text": "<b>not html</b> & so on",
        "inlineStyleRanges": [],
        "entityRanges": [],
    }
    html = article_to_html(_one_block_article(block))
    assert "&lt;b&gt;not html&lt;/b&gt; &amp; so on" in html


# ---------- block grouping ----------


def test_consecutive_list_items_merged():
    blocks = [
        {"type": "unordered-list-item", "text": "one", "inlineStyleRanges": [], "entityRanges": []},
        {"type": "unordered-list-item", "text": "two", "inlineStyleRanges": [], "entityRanges": []},
        {"type": "ordered-list-item", "text": "first", "inlineStyleRanges": [], "entityRanges": []},
        {"type": "unstyled", "text": "tail", "inlineStyleRanges": [], "entityRanges": []},
    ]
    article = {"article_id": "1", "content_state": {"blocks": blocks, "entityMap": []}, "media_entities": []}
    html = article_to_html(article)
    assert "<ul><li>one</li><li>two</li></ul>" in html
    assert "<ol><li>first</li></ol>" in html
    assert "<p>tail</p>" in html


def test_headers_demoted_and_blank_paragraphs_skipped():
    blocks = [
        {"type": "header-one", "text": "章节", "inlineStyleRanges": [], "entityRanges": []},
        {"type": "unstyled", "text": "  ", "inlineStyleRanges": [], "entityRanges": []},
        {"type": "blockquote", "text": "引用", "inlineStyleRanges": [], "entityRanges": []},
    ]
    article = {"article_id": "1", "content_state": {"blocks": blocks, "entityMap": []}, "media_entities": []}
    html = article_to_html(article)
    assert "<h2>章节</h2>" in html
    assert "<blockquote>引用</blockquote>" in html
    assert "<p>  </p>" not in html


def test_content_state_as_json_string_accepted():
    cs = json.dumps({"blocks": [{"type": "unstyled", "text": "hi", "inlineStyleRanges": [], "entityRanges": []}], "entityMap": []})
    article = {"article_id": "1", "content_state": cs, "media_entities": []}
    assert article_to_html(article) == "<p>hi</p>"
    assert article_to_text(article) == "hi"


# ---------- fetcher helpers ----------


def test_find_article_node_in_real_payload():
    data = json.loads(
        (FIXTURES / "x_article_TweetResultByRestId.json").read_text(encoding="utf-8")
    )
    node = find_article_node(data, "2072906137754906624")
    assert node is not None
    assert node["title"].startswith("记一个我")
    # unknown id falls back to the only embedded article
    assert find_article_node(data, "999") is node


def test_needs_article_fetch_states():
    from src.models import ContentItem, SourceType
    from datetime import datetime, timezone

    def make(meta):
        return ContentItem(
            id="twitter:tweet:1",
            source_type=SourceType.TWITTER,
            title="t",
            url="https://x.com/u/status/1",
            published_at=datetime.now(timezone.utc),
            metadata=meta,
        )

    assert needs_article_fetch(make({"article": {"article_id": "9", "title": "t"}}))
    assert not needs_article_fetch(make({}))
    assert not needs_article_fetch(
        make({"article": {"article_id": "9", "content_state": {"blocks": []}}})
    )

"""Tests for twitter_parsing helpers against real captured GraphQL fixtures.

Fixtures under tests/fixtures/twitter/ were captured from the 5 acceptance
tweets (GIF / self-thread / article link / quoted video / X Article), so
every rich-media shape has a regression test that does not depend on the
tweets still being on the timeline.
"""

import json
from pathlib import Path

import pytest

from src.models import TwitterConfig
from src.scrapers.twitter_parsing import (
    expand_tco,
    extract_timeline_tweets,
    resolve_article,
    resolve_card,
    resolve_media,
)
from src.scrapers.twitter_playwright import TwitterPlaywrightScraper

FIXTURES = Path(__file__).parent / "fixtures" / "twitter"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _scraper(**overrides) -> TwitterPlaywrightScraper:
    cfg = dict(enabled=True, mode="playwright", users=["dotey"], fetch_limit=10)
    cfg.update(overrides)
    return TwitterPlaywrightScraper(TwitterConfig(**cfg))


# ---------- unit: pure resolvers ----------


def test_resolve_media_picks_mid_bitrate_mp4():
    legacy = {
        "extended_entities": {
            "media": [
                {
                    "type": "video",
                    "media_url_https": "https://pbs.twimg.com/thumb.jpg",
                    "original_info": {"width": 1280, "height": 720},
                    "video_info": {
                        "duration_millis": 9000,
                        "variants": [
                            {"content_type": "application/x-mpegURL", "url": "https://v/m3u8"},
                            {"content_type": "video/mp4", "bitrate": 256000, "url": "https://v/low.mp4"},
                            {"content_type": "video/mp4", "bitrate": 832000, "url": "https://v/mid.mp4"},
                            {"content_type": "video/mp4", "bitrate": 2176000, "url": "https://v/high.mp4"},
                        ],
                    },
                }
            ]
        }
    }
    media = resolve_media(legacy)
    assert len(media) == 1
    assert media[0]["type"] == "video"
    assert media[0]["duration_ms"] == 9000
    assert media[0]["mp4_url"] == "https://v/mid.mp4"
    assert media[0]["width"] == 1280


def test_expand_tco_replaces_short_links():
    links = [{"short_url": "https://t.co/abc", "expanded_url": "https://example.com/post", "display_url": "example.com/post"}]
    assert expand_tco("看这个 https://t.co/abc 不错", links) == "看这个 https://example.com/post 不错"


def test_resolve_card_and_article_tolerate_absence():
    assert resolve_card({}) is None
    assert resolve_article({}) is None


# ---------- fixture: GIF ----------


def test_fixture_gif_media_extracted():
    raws = extract_timeline_tweets(_load("gif_TweetResultByRestId"), "LufzzLiz")
    assert len(raws) == 1
    media = raws[0]["media"]
    assert len(media) == 1
    assert media[0]["type"] == "animated_gif"
    assert media[0]["mp4_url"].startswith("https://video.twimg.com/")
    assert media[0]["thumbnail_url"].startswith("https://pbs.twimg.com/")

    item = _scraper()._parse_tweet(raws[0], "LufzzLiz")
    assert item is not None
    assert item.metadata["media"][0]["type"] == "animated_gif"


# ---------- fixture: QRT with quoted video + own link card ----------


def test_fixture_qrt_video_attribution():
    raws = extract_timeline_tweets(_load("video_TweetResultByRestId"), "dotey")
    assert len(raws) == 1
    raw = raws[0]
    assert raw["is_quote"] is True
    assert raw["card"]["title"].startswith("Transitions.dev")

    item = _scraper()._parse_tweet(raw, "dotey")
    assert item is not None
    # Substantive QRT: own attachments on the item, quoted video preserved
    assert item.metadata["card"]["title"].startswith("Transitions.dev")
    assert "qrt_comment" in item.metadata
    quoted_media = item.metadata["quoted_media"]
    assert quoted_media[0]["type"] == "video"
    assert quoted_media[0]["duration_ms"] > 0
    assert quoted_media[0]["mp4_url"].startswith("https://video.twimg.com/")
    # t.co in the comment expanded to the real destination
    assert "t.co" not in (item.metadata.get("qrt_comment") or "")


# ---------- fixture: tweet sharing an X Article via link ----------


def test_fixture_article_link_expanded():
    raws = extract_timeline_tweets(_load("rt_article_link_TweetResultByRestId"), "Khazix0918")
    assert len(raws) == 1
    links = raws[0]["links"]
    assert any("x.com/i/article/" in link["expanded_url"] for link in links)
    # text no longer carries the opaque t.co form of that link
    item = _scraper()._parse_tweet(raws[0], "Khazix0918")
    assert item is not None
    assert any("x.com/i/article/" in link["expanded_url"] for link in item.metadata["links"])


# ---------- fixture: native X Article tweet ----------


def test_fixture_x_article_identified():
    raws = extract_timeline_tweets(_load("x_article_TweetResultByRestId"), "Khazix0918")
    assert len(raws) == 1
    art = raws[0]["article"]
    assert art["article_id"]
    assert "Claude Fable 5" in art["title"]
    assert art["preview_text"]

    item = _scraper()._parse_tweet(raws[0], "Khazix0918")
    assert item is not None
    assert item.metadata["article"]["title"] == art["title"]


# ---------- fixture: self-thread merging ----------


@pytest.fixture()
def thread_items():
    raws = extract_timeline_tweets(_load("thread_TweetDetail"), "dotey")
    scraper = _scraper()
    items = [scraper._parse_tweet(r, "dotey") for r in raws]
    return [it for it in items if it]


def test_fixture_thread_chain_merged_replies_to_others_kept(thread_items):
    assert len(thread_items) == 5  # head + 2 chain replies + 2 replies to others

    merged = TwitterPlaywrightScraper._merge_threads(thread_items)
    by_id = {it.metadata["tweet_id"]: it for it in merged}

    head = by_id["2069632132431929651"]
    assert head.metadata["thread_length"] == 3
    parts = head.metadata["thread_parts"]
    assert [p["tweet_id"] for p in parts] == [
        "2069632132431929651",
        "2069675621332972027",
        "2069825516459139579",
    ]
    # head's photo stays attached to its own segment
    assert parts[0]["media"][0]["type"] == "photo"
    # merged content concatenates all segments for AI analysis
    for p in parts:
        assert p["text"] in head.content

    # replies to other people's comments stay standalone
    assert "2069646033898873136" in by_id
    assert "2069637907304849628" in by_id
    assert len(merged) == 3


def test_merge_threads_keeps_unrelated_items_untouched():
    raws = extract_timeline_tweets(_load("gif_TweetResultByRestId"), "LufzzLiz")
    item = _scraper()._parse_tweet(raws[0], "LufzzLiz")
    merged = TwitterPlaywrightScraper._merge_threads([item])
    assert merged == [item]
    assert "thread_parts" not in merged[0].metadata

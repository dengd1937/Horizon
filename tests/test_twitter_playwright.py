"""Tests for the Playwright Twitter scraper: QRT/RT parsing, extraction, dedup."""

from src.models import TwitterConfig
from src.scrapers.twitter_playwright import (
    TwitterPlaywrightScraper,
    _visible_char_count,
    extract_timeline_tweets,
)

CREATED = "Wed Jul 01 03:49:18 +0000 2026"


def _scraper(**overrides) -> TwitterPlaywrightScraper:
    cfg = dict(enabled=True, mode="playwright", users=["dotey"], fetch_limit=10)
    cfg.update(overrides)
    return TwitterPlaywrightScraper(TwitterConfig(**cfg))


def _user(name: str) -> dict:
    # Mirrors the 2025+ GraphQL schema: screen_name lives under result.core
    return {"user_results": {"result": {"rest_id": f"u-{name}", "core": {"screen_name": name}}}}


def _tweet_result(
    tweet_id: str,
    author: str,
    full_text: str,
    *,
    note_text: str | None = None,
    quoted: dict | None = None,
    retweeted: dict | None = None,
) -> dict:
    result = {
        "rest_id": tweet_id,
        "core": _user(author),
        "legacy": {
            "full_text": full_text,
            "created_at": CREATED,
            "is_quote_status": quoted is not None,
        },
    }
    if note_text is not None:
        result["note_tweet"] = {"note_tweet_results": {"result": {"text": note_text}}}
    if quoted is not None:
        result["quoted_status_result"] = {"result": quoted}
        result["legacy"]["quoted_status_id_str"] = quoted["rest_id"]
    if retweeted is not None:
        result["legacy"]["retweeted_status_result"] = {"result": retweeted}
        result["legacy"]["retweeted_status_id_str"] = retweeted["rest_id"]
    return result


def _timeline(*tweet_results: dict) -> dict:
    entries = [
        {"content": {"itemContent": {"tweet_results": {"result": tr}}}}
        for tr in tweet_results
    ]
    return {
        "data": {
            "user": {
                "result": {
                    "timeline": {
                        "timeline": {
                            "instructions": [
                                {"type": "TimelineAddEntries", "entries": entries}
                            ]
                        }
                    }
                }
            }
        }
    }


# ---------- _visible_char_count ----------


def test_visible_char_count_strips_urls_mentions_emoji():
    assert _visible_char_count("重要 https://t.co/abc @foo 👀!!") == 2
    assert _visible_char_count("👀🔥") == 0
    assert _visible_char_count("Must read") == 8
    assert _visible_char_count("这个更新非常重要值得一读") == 12


# ---------- extract_timeline_tweets ----------


def test_extract_prefers_note_tweet_full_text():
    long_text = "完整长文" * 100
    tl = _timeline(_tweet_result("1", "dotey", "截断的短文…", note_text=long_text))
    raws = extract_timeline_tweets(tl, "dotey")
    assert len(raws) == 1
    assert raws[0]["text"] == long_text


def test_extract_does_not_surface_quoted_original_as_standalone():
    quoted = _tweet_result("100", "AnthropicAI", "original announcement")
    qrt = _tweet_result("200", "dotey", "我的评论内容足够长了吧", quoted=quoted)
    raws = extract_timeline_tweets(_timeline(qrt), "dotey")
    assert [r["tweet_id"] for r in raws] == ["200"]
    quoted_view = raws[0]["quoted"]
    assert quoted_view["tweet_id"] == "100"
    assert quoted_view["author"] == "AnthropicAI"
    assert quoted_view["text"] == "original announcement"


def test_extract_skips_foreign_author():
    promo = _tweet_result("300", "advertiser", "buy our stuff")
    mine = _tweet_result("301", "dotey", "hello world")
    raws = extract_timeline_tweets(_timeline(promo, mine), "dotey")
    assert [r["tweet_id"] for r in raws] == ["301"]


def test_extract_rt_captures_original_note_text_and_nested_quote():
    inner = _tweet_result("50", "openai", "inner announcement")
    orig = _tweet_result(
        "100", "someone", "trunc…", note_text="full original body", quoted=inner
    )
    rt = _tweet_result("200", "dotey", "RT @someone: trunc…", retweeted=orig)
    raws = extract_timeline_tweets(_timeline(rt), "dotey")
    assert len(raws) == 1
    raw = raws[0]
    assert raw["is_retweet"] is True
    assert raw["is_quote"] is False
    assert raw["rt_original"]["author"] == "someone"
    assert raw["rt_original"]["text"] == "full original body"
    assert raw["rt_original"]["quoted"]["tweet_id"] == "50"


# ---------- _parse_tweet: QRT ----------


def test_parse_substantive_qrt_merges_comment_and_quote():
    quoted = _tweet_result("100", "AnthropicAI", "Fable 5 redeploy\nsecond line")
    qrt = _tweet_result("200", "dotey", "这是一段足够长的有料评论内容", quoted=quoted)
    raw = extract_timeline_tweets(_timeline(qrt), "dotey")[0]
    item = _scraper()._parse_tweet(raw, "dotey")
    assert item is not None
    assert item.title.startswith("@dotey: 这是一段")
    assert "这是一段足够长的有料评论内容" in item.content
    assert "> 引用 @AnthropicAI: Fable 5 redeploy" in item.content
    assert "> second line" in item.content
    assert item.metadata["is_quote"] is True
    assert item.metadata["quoted_tweet_id"] == "100"
    assert item.metadata["quoted_author"] == "AnthropicAI"
    assert str(item.url) == "https://x.com/dotey/status/200"


def test_parse_water_qrt_degrades_to_repost():
    quoted = _tweet_result("100", "AnthropicAI", "original text here")
    qrt = _tweet_result("200", "dotey", "重要 👀 https://t.co/x", quoted=quoted)
    raw = extract_timeline_tweets(_timeline(qrt), "dotey")[0]
    item = _scraper()._parse_tweet(raw, "dotey")
    assert item is not None
    assert item.content == "original text here"
    assert item.title.startswith("@dotey 转推 @AnthropicAI:")
    assert item.metadata["quoted_tweet_id"] == "100"


def test_parse_water_qrt_with_unavailable_quote_is_dropped():
    qrt = _tweet_result("200", "dotey", "👀")
    qrt["legacy"]["is_quote_status"] = True
    qrt["legacy"]["quoted_status_id_str"] = "100"
    raw = extract_timeline_tweets(_timeline(qrt), "dotey")[0]
    assert raw["is_quote"] is True
    assert _scraper()._parse_tweet(raw, "dotey") is None


def test_parse_substantive_qrt_with_unavailable_quote_keeps_comment():
    qrt = _tweet_result("200", "dotey", "这条被引用的推文已经删除但我的评论很长")
    qrt["legacy"]["is_quote_status"] = True
    qrt["legacy"]["quoted_status_id_str"] = "100"
    raw = extract_timeline_tweets(_timeline(qrt), "dotey")[0]
    item = _scraper()._parse_tweet(raw, "dotey")
    assert item is not None
    assert item.content.endswith("> 引用推文不可用")


def test_qrt_threshold_is_configurable():
    quoted = _tweet_result("100", "AnthropicAI", "original")
    qrt = _tweet_result("200", "dotey", "短评四个字", quoted=quoted)
    raw = extract_timeline_tweets(_timeline(qrt), "dotey")[0]

    strict = _scraper()._parse_tweet(raw, "dotey")  # threshold 10 -> repost
    assert strict.content == "original"

    loose = _scraper(qrt_comment_min_chars=3)._parse_tweet(raw, "dotey")
    assert "短评四个字" in loose.content
    assert "> 引用 @AnthropicAI: original" in loose.content


# ---------- _parse_tweet: RT ----------


def test_parse_pure_rt_uses_original_full_text():
    orig = _tweet_result("100", "laike9m_", "trunc…", note_text="the full original body")
    rt = _tweet_result("200", "dotey", "RT @laike9m_: trunc…", retweeted=orig)
    raw = extract_timeline_tweets(_timeline(rt), "dotey")[0]
    item = _scraper()._parse_tweet(raw, "dotey")
    assert item is not None
    assert item.content == "the full original body"
    assert item.title.startswith("@dotey 转推 @laike9m_:")
    assert item.metadata["is_retweet"] is True
    assert item.metadata["rt_original_id"] == "100"
    assert item.metadata["rt_original_author"] == "laike9m_"


def test_parse_rt_of_qrt_includes_nested_quote_block():
    inner = _tweet_result("50", "openai", "inner announcement")
    orig = _tweet_result("100", "someone", "commentary", quoted=inner)
    rt = _tweet_result("200", "dotey", "RT @someone: commentary", retweeted=orig)
    raw = extract_timeline_tweets(_timeline(rt), "dotey")[0]
    item = _scraper()._parse_tweet(raw, "dotey")
    assert item is not None
    assert item.content.startswith("commentary")
    assert "> 引用 @openai: inner announcement" in item.content
    assert item.metadata["quoted_tweet_id"] == "50"


def test_parse_rt_fallback_without_embedded_original():
    raw = {
        "tweet_id": "1",
        "text": "RT @foo: some short body",
        "datetime": "2026-07-01T00:00:00+00:00",
        "is_retweet": True,
        "rt_original": None,
        "is_quote": False,
        "quoted": None,
        "images": [],
    }
    item = _scraper()._parse_tweet(raw, "dotey")
    assert item is not None
    assert item.content == "some short body"
    assert "@dotey 转推 @foo:" in item.title


# ---------- _drop_absorbed_originals ----------


def test_drop_absorbed_originals():
    scraper = _scraper()
    quoted = _tweet_result("100", "AnthropicAI", "the announcement")
    qrt = _tweet_result("200", "dotey", "这是一段足够长的有料评论内容", quoted=quoted)
    standalone = _tweet_result("100", "AnthropicAI", "the announcement")
    other = _tweet_result("300", "karpathy", "unrelated tweet")

    items = [
        scraper._parse_tweet(extract_timeline_tweets(_timeline(qrt), "dotey")[0], "dotey"),
        scraper._parse_tweet(
            extract_timeline_tweets(_timeline(standalone), "AnthropicAI")[0], "AnthropicAI"
        ),
        scraper._parse_tweet(
            extract_timeline_tweets(_timeline(other), "karpathy")[0], "karpathy"
        ),
    ]
    assert all(items)

    kept = TwitterPlaywrightScraper._drop_absorbed_originals(items)
    kept_ids = [it.metadata["tweet_id"] for it in kept]
    assert kept_ids == ["200", "300"]

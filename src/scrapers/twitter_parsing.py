"""Pure parsing helpers for Twitter GraphQL payloads (Playwright mode).

Stateless functions that flatten raw GraphQL tweet results into the raw
dicts consumed by TwitterPlaywrightScraper._parse_tweet. No I/O here so
everything is unit-testable against captured fixtures, and reusable by
other fetch modes later.
"""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+")
_MENTION_RE = re.compile(r"@\w+")
_WORD_RE = re.compile(r"\w")
_RT_PREFIX_RE = re.compile(r"^RT @(\w+):\s*")

_MEDIA_TYPES = {"photo", "video", "animated_gif"}


def _visible_char_count(text: str) -> int:
    """Count meaningful characters after stripping URLs and @mentions.

    Only word characters are counted (CJK included), so emoji,
    punctuation and whitespace never push a comment over the threshold.
    """
    cleaned = _MENTION_RE.sub("", _URL_RE.sub("", text))
    return len(_WORD_RE.findall(cleaned))


def _head(text: str, limit: int = 50) -> str:
    body = text[:limit].replace("\n", " ").strip()
    if len(text) > limit:
        body += "..."
    return body


def _format_quote_block(author: str, text: str) -> str:
    lines = (text or "").strip().split("\n")
    block = [f"> 引用 @{author or 'unknown'}: {lines[0]}"]
    block.extend(f"> {line}" for line in lines[1:])
    return "\n".join(block)


def _unwrap_tweet_result(result) -> dict:
    """Unwrap TweetWithVisibilityResults wrappers; tolerate missing data."""
    if not isinstance(result, dict):
        return {}
    if result.get("__typename") == "TweetWithVisibilityResults":
        inner = result.get("tweet")
        return inner if isinstance(inner, dict) else {}
    return result


def _resolve_full_text(tweet_result: dict) -> str:
    """Prefer the untruncated note_tweet (long-form) text over legacy.full_text."""
    note_text = (
        (tweet_result.get("note_tweet") or {})
        .get("note_tweet_results", {})
        .get("result", {})
        .get("text")
    )
    return note_text or (tweet_result.get("legacy") or {}).get("full_text", "")


def _resolve_screen_name(tweet_result: dict) -> str:
    user = (tweet_result.get("core") or {}).get("user_results", {}).get("result", {})
    return (
        (user.get("core") or {}).get("screen_name")
        or (user.get("legacy") or {}).get("screen_name")
        or ""
    )


def _raw_media_entries(legacy: dict) -> list[dict]:
    return (legacy.get("extended_entities") or {}).get("media", []) or (
        legacy.get("entities") or {}
    ).get("media", [])


def _pick_mp4_variant(variants: list[dict], media_type: str) -> str:
    """Pick a playable mp4 url: GIFs have one variant, videos get mid bitrate."""
    mp4s = [
        v
        for v in variants
        if v.get("content_type") == "video/mp4" and v.get("url")
    ]
    if not mp4s:
        return ""
    if media_type == "animated_gif" or len(mp4s) == 1:
        return mp4s[0]["url"]
    mp4s.sort(key=lambda v: v.get("bitrate") or 0)
    return mp4s[len(mp4s) // 2]["url"]


def resolve_media(legacy: dict) -> list[dict]:
    """Extract all photo/video/animated_gif media from a tweet's legacy dict."""
    out: list[dict] = []
    for m in _raw_media_entries(legacy):
        mtype = m.get("type")
        if mtype not in _MEDIA_TYPES or not m.get("media_url_https"):
            continue
        original = m.get("original_info") or {}
        entry: dict = {
            "type": mtype,
            "thumbnail_url": m["media_url_https"],
            "width": original.get("width", 0),
            "height": original.get("height", 0),
        }
        if mtype in ("video", "animated_gif"):
            info = m.get("video_info") or {}
            entry["duration_ms"] = info.get("duration_millis", 0)
            entry["mp4_url"] = _pick_mp4_variant(info.get("variants") or [], mtype)
        out.append(entry)
    return out


def resolve_links(tweet_result: dict) -> list[dict]:
    """Collect t.co -> real-url mappings from legacy and note_tweet entities."""
    legacy = tweet_result.get("legacy") or {}
    urls = (legacy.get("entities") or {}).get("urls", []) or []
    note_urls = (
        (
            (tweet_result.get("note_tweet") or {})
            .get("note_tweet_results", {})
            .get("result", {})
            .get("entity_set")
            or {}
        ).get("urls", [])
        or []
    )
    out: list[dict] = []
    seen: set[str] = set()
    for u in [*urls, *note_urls]:
        short = u.get("url", "")
        expanded = u.get("expanded_url", "")
        if not short or not expanded or short in seen:
            continue
        seen.add(short)
        out.append(
            {
                "short_url": short,
                "expanded_url": expanded,
                "display_url": u.get("display_url", ""),
            }
        )
    return out


def resolve_card(tweet_result: dict) -> Optional[dict]:
    """Extract link-card preview (title/description/domain/thumbnail)."""
    bindings = ((tweet_result.get("card") or {}).get("legacy") or {}).get(
        "binding_values"
    )
    values: dict[str, str] = {}
    if isinstance(bindings, list):
        pairs = [(b.get("key"), b.get("value") or {}) for b in bindings]
    elif isinstance(bindings, dict):
        pairs = list(bindings.items())
    else:
        return None
    for key, val in pairs:
        if not key or not isinstance(val, dict):
            continue
        if val.get("type") == "STRING":
            values[key] = val.get("string_value", "")
        elif val.get("type") == "IMAGE":
            values[key] = (val.get("image_value") or {}).get("url", "")

    title = values.get("title", "")
    if not title:
        return None
    thumbnail = (
        values.get("thumbnail_image_large")
        or values.get("thumbnail_image")
        or values.get("summary_photo_image_large")
        or values.get("summary_photo_image")
        or ""
    )
    return {
        "title": title,
        "description": values.get("description", ""),
        "domain": values.get("vanity_url", "") or values.get("domain", ""),
        "thumbnail_url": thumbnail,
        "card_url": values.get("card_url", ""),
    }


def resolve_article(tweet_result: dict) -> Optional[dict]:
    """Identify an attached X Article (long-form post). Full text is fetched later."""
    art = (
        ((tweet_result.get("article") or {}).get("article_results") or {}).get(
            "result"
        )
        or {}
    )
    article_id = str(art.get("rest_id") or art.get("id") or "")
    title = art.get("title", "")
    if not article_id and not title:
        return None
    return {
        "article_id": article_id,
        "title": title,
        "preview_text": art.get("preview_text", ""),
    }


def _strip_media_urls(text: str, legacy: dict) -> str:
    """Remove trailing t.co placeholders that stand in for attached media."""
    for m in _raw_media_entries(legacy):
        placeholder = m.get("url")
        if placeholder:
            text = text.replace(placeholder, "")
    return text.strip()


def expand_tco(text: str, links: list[dict]) -> str:
    """Replace t.co short links with their real destination in tweet text.

    t.co itself is unreachable without a proxy, and real domains also give
    the AI analyzer meaningful signal instead of opaque short links.
    """
    for link in links:
        short, expanded = link.get("short_url", ""), link.get("expanded_url", "")
        if short and expanded:
            text = text.replace(short, expanded)
    return text


def _clean_tweet_text(tweet_result: dict) -> str:
    """Full text with media placeholders stripped and t.co links expanded."""
    legacy = tweet_result.get("legacy") or {}
    text = _strip_media_urls(_resolve_full_text(tweet_result), legacy)
    return expand_tco(text, resolve_links(tweet_result))


def _summarize_embedded(container) -> Optional[dict]:
    """Compact view of an embedded quoted/retweeted tweet, incl. media/links."""
    tweet_result = _unwrap_tweet_result((container or {}).get("result"))
    rest_id = tweet_result.get("rest_id")
    if not rest_id:
        return None
    return {
        "tweet_id": str(rest_id),
        "author": _resolve_screen_name(tweet_result),
        "text": _clean_tweet_text(tweet_result),
        "media": resolve_media(tweet_result.get("legacy") or {}),
        "links": resolve_links(tweet_result),
        "card": resolve_card(tweet_result),
        "article": resolve_article(tweet_result),
    }


def _build_raw_tweet(tweet_result: dict) -> Optional[dict]:
    """Flatten one GraphQL tweet result into the raw dict consumed by _parse_tweet."""
    legacy = tweet_result.get("legacy") or {}
    rest_id = tweet_result.get("rest_id")
    if not rest_id:
        return None

    text = _clean_tweet_text(tweet_result)
    created_at = legacy.get("created_at", "")
    try:
        dt_iso = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").isoformat()
    except (ValueError, TypeError):
        dt_iso = created_at

    rt_result = _unwrap_tweet_result(
        (legacy.get("retweeted_status_result") or {}).get("result")
    )
    rt_original: Optional[dict] = None
    if rt_result.get("rest_id"):
        rt_original = {
            "tweet_id": str(rt_result["rest_id"]),
            "author": _resolve_screen_name(rt_result),
            "text": _clean_tweet_text(rt_result),
            "media": resolve_media(rt_result.get("legacy") or {}),
            "links": resolve_links(rt_result),
            "card": resolve_card(rt_result),
            "article": resolve_article(rt_result),
            "quoted": _summarize_embedded(rt_result.get("quoted_status_result")),
        }
    raw_full_text = legacy.get("full_text", "")
    is_retweet = bool(
        rt_original
        or legacy.get("retweeted_status_id_str")
        or raw_full_text.startswith("RT @")
    )

    quoted = (
        None
        if is_retweet
        else _summarize_embedded(tweet_result.get("quoted_status_result"))
    )
    quoted_id = ""
    if not is_retweet:
        quoted_id = str(
            legacy.get("quoted_status_id_str") or (quoted or {}).get("tweet_id") or ""
        )
    is_quote = bool(
        not is_retweet and (legacy.get("is_quote_status") or quoted_id or quoted)
    )

    return {
        "tweet_id": str(rest_id),
        "author": _resolve_screen_name(tweet_result),
        "text": text,
        "raw_text": raw_full_text,
        "datetime_raw": created_at,
        "datetime": dt_iso,
        "media": resolve_media(legacy),
        "links": resolve_links(tweet_result),
        "card": resolve_card(tweet_result),
        "article": resolve_article(tweet_result),
        "conversation_id": str(legacy.get("conversation_id_str") or ""),
        "in_reply_to_status_id": str(legacy.get("in_reply_to_status_id_str") or ""),
        "in_reply_to_screen_name": legacy.get("in_reply_to_screen_name") or "",
        "is_retweet": is_retweet,
        "rt_original": rt_original,
        "is_quote": is_quote,
        "quoted_tweet_id": quoted_id,
        "quoted": quoted,
    }


def extract_timeline_tweets(data: dict, username: str) -> list[dict]:
    """Collect timeline tweets from a UserTweets GraphQL payload.

    Recursion stops once a tweet object is consumed, so quoted/retweeted
    originals embedded inside it never surface as standalone tweets.
    Tweets authored by other accounts (injected/promoted content) are
    skipped; tweets with unreadable author info are kept.
    """
    tweets: list[dict] = []
    expected = username.lower()

    def walk(obj) -> None:
        if isinstance(obj, dict):
            legacy = obj.get("legacy")
            if obj.get("rest_id") and isinstance(legacy, dict) and "full_text" in legacy:
                raw = _build_raw_tweet(obj)
                if raw:
                    author = raw["author"]
                    if author and author.lower() != expected:
                        logger.debug(
                            "Skipping foreign tweet %s by @%s on @%s timeline",
                            raw["tweet_id"], author, username,
                        )
                    else:
                        tweets.append(raw)
                return
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for entry in obj:
                walk(entry)

    walk(data)
    return tweets

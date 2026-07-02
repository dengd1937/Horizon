"""Twitter scraper using Playwright + Cookie (replaces Apify)."""

import asyncio
import hashlib
import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..models import ContentItem, SourceType, TwitterConfig
from .base import BaseScraper

logger = logging.getLogger(__name__)

# Optional Playwright imports — gracefully degraded if not installed
try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Stealth = None  # type: ignore[misc,assignment]


def _get_proxy() -> str:
    """Resolve proxy from common env vars (PROXY, http_proxy, all_proxy)."""
    for key in ("PROXY", "https_proxy", "http_proxy", "all_proxy"):
        val = os.getenv(key, "").strip()
        if val:
            return val
    return ""


PROXY = _get_proxy()


def _load_browser_cookies(file_path: str) -> list[dict]:
    """Read browser-exported cookie JSON and convert to Playwright format."""
    if not Path(file_path).exists():
        return []
    with open(file_path, encoding="utf-8") as f:
        cookies = json.load(f)
    pw_cookies = []
    for c in cookies:
        pc: dict = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", False),
        }
        if c.get("expirationDate"):
            pc["expires"] = c["expirationDate"]
        pw_cookies.append(pc)
    return pw_cookies


_URL_RE = re.compile(r"https?://\S+")
_MENTION_RE = re.compile(r"@\w+")
_WORD_RE = re.compile(r"\w")
_RT_PREFIX_RE = re.compile(r"^RT @(\w+):\s*")


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


def _resolve_images(legacy: dict) -> list[str]:
    media = (
        (legacy.get("extended_entities") or {}).get("media", [])
        or (legacy.get("entities") or {}).get("media", [])
    )
    return [
        m["media_url_https"]
        for m in media
        if m.get("type") == "photo" and m.get("media_url_https")
    ]


def _summarize_embedded(container) -> Optional[dict]:
    """Compact {tweet_id, author, text} view of an embedded quoted/retweeted tweet."""
    tweet_result = _unwrap_tweet_result((container or {}).get("result"))
    rest_id = tweet_result.get("rest_id")
    if not rest_id:
        return None
    return {
        "tweet_id": str(rest_id),
        "author": _resolve_screen_name(tweet_result),
        "text": _resolve_full_text(tweet_result),
    }


def _build_raw_tweet(tweet_result: dict) -> Optional[dict]:
    """Flatten one GraphQL tweet result into the raw dict consumed by _parse_tweet."""
    legacy = tweet_result.get("legacy") or {}
    rest_id = tweet_result.get("rest_id")
    if not rest_id:
        return None

    text = _resolve_full_text(tweet_result)
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
            "text": _resolve_full_text(rt_result),
            "quoted": _summarize_embedded(rt_result.get("quoted_status_result")),
        }
    is_retweet = bool(
        rt_original or legacy.get("retweeted_status_id_str") or text.startswith("RT @")
    )

    quoted = None if is_retweet else _summarize_embedded(tweet_result.get("quoted_status_result"))
    quoted_id = ""
    if not is_retweet:
        quoted_id = str(legacy.get("quoted_status_id_str") or (quoted or {}).get("tweet_id") or "")
    is_quote = bool(not is_retweet and (legacy.get("is_quote_status") or quoted_id or quoted))

    return {
        "tweet_id": str(rest_id),
        "author": _resolve_screen_name(tweet_result),
        "text": text,
        "datetime_raw": created_at,
        "datetime": dt_iso,
        "images": _resolve_images(legacy),
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


class TwitterPlaywrightScraper(BaseScraper):
    """Fetch tweets via Playwright + Cookie using GraphQL interception (free alternative to Apify)."""

    def __init__(self, config: TwitterConfig, http_client=None):
        super().__init__(config.model_dump(), http_client)
        self.twitter_config = config

    async def fetch(self, since: datetime) -> List[ContentItem]:
        if not self.twitter_config.enabled:
            return []

        users = [u.strip().lstrip("@") for u in self.twitter_config.users if u.strip()]
        if not users:
            logger.debug("No Twitter users configured, skipping.")
            return []

        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(
                "Playwright not installed. Run: uv sync --extra twitter && uv run playwright install chromium"
            )
            return []

        cookie_dir = Path(self.twitter_config.cookie_dir)
        pattern = self.twitter_config.cookie_file_pattern
        cookie_files = sorted(cookie_dir.glob(pattern))
        if not cookie_files:
            logger.warning("No cookie files found matching %s in %s", pattern, cookie_dir)
            return []

        logger.info(
            "Fetching Twitter (Playwright) for %d users using %d cookie sets",
            len(users),
            len(cookie_files),
        )

        all_items: List[ContentItem] = []
        failed_users: list[tuple[str, int]] = []
        lock = asyncio.Lock()

        async with Stealth().use_async(async_playwright()) as p:  # type: ignore[union-attr]
            launch_kwargs: dict = {"headless": True}
            if PROXY:
                launch_kwargs["proxy"] = {"server": PROXY}
            browser = await p.chromium.launch(**launch_kwargs)

            contexts = []
            for i, cf in enumerate(cookie_files):
                cookies = _load_browser_cookies(str(cf))
                ctx = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/13{i}.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    timezone_id="UTC",
                    color_scheme="dark",
                )
                if cookies:
                    await ctx.add_cookies(cookies)
                contexts.append(ctx)

            # Warm-up each context by visiting x.com/home
            for i, ctx in enumerate(contexts):
                page = await ctx.new_page()
                try:
                    await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                    logger.info("Cookie #%d warm-up done", i + 1)
                except Exception as exc:
                    logger.warning("Cookie #%d warm-up failed: %s", i + 1, exc)
                finally:
                    await page.close()

            num_contexts = len(contexts)

            async def process_queue(context_idx: int, queue: list[str], is_retry: bool = False):
                ctx = contexts[context_idx]
                consecutive_failures = 0

                for username in queue:
                    wait_time = (
                        random.uniform(5.0, 10.0) if not is_retry else random.uniform(10.0, 20.0)
                    )
                    await asyncio.sleep(wait_time)

                    if consecutive_failures >= 5:
                        logger.warning("Context #%d cooling down (30s)", context_idx + 1)
                        await asyncio.sleep(30)
                        consecutive_failures = 0

                    logger.info("Scraping @%s with cookie #%d...", username, context_idx + 1)
                    tweets = await self._scrape_user(ctx, username, since)

                    if tweets is not None:
                        logger.info("  -> @%s: %d tweets found", username, len(tweets))
                        consecutive_failures = 0
                        parsed = [item for item in (self._parse_tweet(t, username) for t in tweets) if item]
                        async with lock:
                            all_items.extend(parsed)
                    else:
                        consecutive_failures += 1
                        if not is_retry:
                            async with lock:
                                failed_users.append((username, context_idx))

            # Round-robin assign users to context queues
            queues: list[list[str]] = [[] for _ in range(num_contexts)]
            for i, username in enumerate(users):
                queues[i % num_contexts].append(username)

            # First pass — all queues in parallel
            await asyncio.gather(*[process_queue(i, q) for i, q in enumerate(queues)])

            # Retry failed users with a different context
            if failed_users:
                logger.info("Retrying %d failed Twitter accounts with alternate cookies", len(failed_users))
                await asyncio.sleep(20)
                retry_queues: list[list[str]] = [[] for _ in range(num_contexts)]
                for username, original_idx in failed_users:
                    new_idx = (original_idx + 1) % num_contexts if num_contexts >= 2 else 0
                    retry_queues[new_idx].append(username)

                await asyncio.gather(*[
                    process_queue(i, q, is_retry=True)
                    for i, q in enumerate(retry_queues)
                    if q
                ])

            for ctx in contexts:
                await ctx.close()
            await browser.close()

        deduped = self._drop_absorbed_originals(all_items)
        if len(deduped) < len(all_items):
            logger.info(
                "Dropped %d standalone originals already embedded in QRT/RT items",
                len(all_items) - len(deduped),
            )
        logger.info("Fetched %d tweets via Playwright.", len(deduped))
        return deduped

    @staticmethod
    def _drop_absorbed_originals(items: List[ContentItem]) -> List[ContentItem]:
        """Drop standalone tweets already embedded in another item's QRT/RT block.

        When a monitored account's tweet is quoted/retweeted by another
        monitored account, the QRT/RT item is the information superset
        (comment + original), so the standalone original is redundant.
        """
        absorbed: dict[str, str] = {}
        for item in items:
            own_id = str(item.metadata.get("tweet_id", ""))
            for key in ("quoted_tweet_id", "rt_original_id"):
                ref = str(item.metadata.get(key) or "")
                if ref and ref != own_id:
                    absorbed[ref] = own_id

        if not absorbed:
            return items

        kept: List[ContentItem] = []
        for item in items:
            own_id = str(item.metadata.get("tweet_id", ""))
            if own_id in absorbed:
                logger.info(
                    "Dropping standalone tweet %s (embedded in %s)",
                    own_id,
                    absorbed[own_id],
                )
                continue
            kept.append(item)
        return kept

    async def _scrape_user(self, ctx, username: str, since: datetime) -> Optional[list[dict]]:
        """Scrape a single user's tweets via GraphQL interception."""
        page = await ctx.new_page()
        graphql_tweets: list[dict] = []

        async def handle_response(response):
            if "UserTweets" not in response.url and "UserByScreenName" not in response.url:
                return
            try:
                data = await response.json()
                graphql_tweets.extend(extract_timeline_tweets(data, username))
            except Exception as exc:
                logger.debug("GraphQL parse error: %s", exc)

        page.on("response", handle_response)

        # Block heavy resources
        async def route_handler(route):
            if route.request.resource_type in ("media", "image", "video"):
                await route.abort()
            else:
                url = route.request.url.lower()
                if any(k in url for k in ("google-analytics", "doubleclick", "scribe.twitter.com")):
                    await route.abort()
                else:
                    await route.continue_()

        await page.route("**/*", route_handler)

        try:
            await asyncio.sleep(random.uniform(2, 4))

            for attempt in range(3):
                if attempt > 0:
                    await asyncio.sleep(random.uniform(5, 10))
                try:
                    await page.goto(
                        f"https://x.com/{username}",
                        wait_until="domcontentloaded",
                        timeout=25000,
                    )
                    break
                except Exception as exc:
                    if "Timeout" in str(exc):
                        logger.debug("Page load slow (attempt %d/3)", attempt + 1)
                        if attempt == 2:
                            break
                    else:
                        if attempt == 2:
                            raise
                        logger.debug("Page visit error (attempt %d/3): %s", attempt + 1, exc)

            await asyncio.sleep(5)
            start_time = asyncio.get_event_loop().time()

            # Quick diagnostic: check if page requires login
            body_text = await page.evaluate("document.body ? document.body.innerText : ''")
            if body_text and any(k in body_text.lower() for k in ("log in", "sign up", "create account")):
                logger.warning("  -> @%s page shows login gate — cookie may be invalid", username)

            while (asyncio.get_event_loop().time() - start_time) < 60:
                if graphql_tweets:
                    result = []
                    seen = set()
                    for t in graphql_tweets:
                        uid = t.get("tweet_id") or hashlib.md5(t["text"].encode()).hexdigest()
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            tweet_time = datetime.fromisoformat(t["datetime"])
                            if tweet_time < since:
                                continue
                        except Exception:
                            continue
                        result.append(t)

                    if result:
                        logger.info("  -> @%s: %d tweets within time window", username, len(result))
                        return result[: self.twitter_config.fetch_limit]
                    logger.info("  -> @%s: intercepted %d tweets but all outside time window", username, len(graphql_tweets))
                    return []

                # Check for error pages
                body_text = await page.evaluate("document.body ? document.body.innerText : ''")
                if body_text and any(
                    kw in body_text
                    for kw in ("Retry", "Something went wrong", "出错了", "重新加载")
                ):
                    await page.reload(wait_until="load", timeout=30000)
                    await asyncio.sleep(5)

                # Simulate human browsing
                await page.mouse.move(random.randint(100, 600), random.randint(100, 600))
                await page.evaluate(f"window.scrollBy(0, {random.randint(300, 700)})")
                await asyncio.sleep(random.uniform(2, 4))

                at_bottom = await page.evaluate(
                    "window.innerHeight + window.scrollY >= document.body.scrollHeight"
                )
                if at_bottom and (asyncio.get_event_loop().time() - start_time) > 20:
                    break

            if not graphql_tweets:
                logger.warning("  -> @%s: no GraphQL data intercepted (cookie or page issue)", username)
                return None
            return []

        except Exception as exc:
            logger.warning("Failed to scrape @%s: %s", username, exc)
            return None
        finally:
            await page.close()

    def _parse_tweet(self, tweet: dict, username: str) -> Optional[ContentItem]:
        """Convert raw tweet dict to Horizon ContentItem.

        QRT/RT rules:
        - Pure RT: content is the retweeted original's full text.
        - QRT with a substantive comment (>= qrt_comment_min_chars visible
          chars): comment plus the quoted original as a "> 引用 @..." block.
        - QRT with a short comment: degrades to a plain repost of the original.
        """
        try:
            tweet_id = str(tweet.get("tweet_id", ""))
            if not tweet_id:
                return None

            created_at_raw = tweet.get("datetime", "")
            try:
                published_at = datetime.fromisoformat(created_at_raw)
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None

            text = tweet.get("text", "")
            metadata: dict = {
                "tweet_id": tweet_id,
                "is_retweet": bool(tweet.get("is_retweet", False)),
                "is_quote": bool(tweet.get("is_quote", False)),
                "images": tweet.get("images", []),
                "category": "ai-news",
            }

            if tweet.get("is_retweet"):
                original = tweet.get("rt_original") or {}
                orig_text = (original.get("text") or _RT_PREFIX_RE.sub("", text)).strip()
                if not orig_text:
                    return None
                prefix_match = _RT_PREFIX_RE.match(text)
                orig_author = original.get("author") or (
                    prefix_match.group(1) if prefix_match else "unknown"
                )
                content = orig_text
                nested = original.get("quoted")
                if nested:
                    content += "\n\n" + _format_quote_block(
                        nested.get("author", ""), nested.get("text", "")
                    )
                    metadata["quoted_tweet_id"] = nested.get("tweet_id", "")
                    metadata["quoted_author"] = nested.get("author", "")
                title = f"@{username} 转推 @{orig_author}: {_head(orig_text)}"
                metadata["rt_original_id"] = original.get("tweet_id", "")
                metadata["rt_original_author"] = orig_author
            elif tweet.get("is_quote"):
                comment = text.strip()
                quoted = tweet.get("quoted")
                quoted_text = ((quoted or {}).get("text") or "").strip()
                substantive = (
                    _visible_char_count(comment)
                    >= self.twitter_config.qrt_comment_min_chars
                )
                metadata["quoted_tweet_id"] = tweet.get("quoted_tweet_id", "")
                if quoted_text:
                    metadata["quoted_author"] = quoted.get("author", "")
                    if substantive:
                        content = comment + "\n\n" + _format_quote_block(
                            quoted.get("author", ""), quoted_text
                        )
                        title = f"@{username}: {_head(comment)}"
                    else:
                        content = quoted_text
                        title = (
                            f"@{username} 转推 @{quoted.get('author') or 'unknown'}: "
                            f"{_head(quoted_text)}"
                        )
                else:
                    # Quoted tweet unavailable (deleted/protected/empty)
                    if not substantive:
                        logger.debug(
                            "Dropping QRT %s: short comment, quoted tweet unavailable",
                            tweet_id,
                        )
                        return None
                    content = comment + "\n\n> 引用推文不可用"
                    title = f"@{username}: {_head(comment)}"
            else:
                body = text.strip()
                if not body:
                    return None
                content = body
                title = f"@{username}: {_head(body)}"

            return ContentItem(
                id=self._generate_id(SourceType.TWITTER.value, "tweet", tweet_id),
                source_type=SourceType.TWITTER,
                title=title,
                url=f"https://x.com/{username}/status/{tweet_id}",
                content=content,
                author=username,
                published_at=published_at,
                metadata=metadata,
            )
        except Exception as exc:
            logger.debug("Failed to parse tweet: %s", exc)
            return None

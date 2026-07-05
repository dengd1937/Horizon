"""Twitter scraper using Playwright + Cookie (replaces Apify)."""

import asyncio
import hashlib
import json
import logging
import os
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..models import ContentItem, SourceType, TwitterConfig
from .base import BaseScraper
from .twitter_parsing import (
    _RT_PREFIX_RE,
    _format_quote_block,
    _head,
    _visible_char_count,
    extract_timeline_tweets,
)

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
        merged = self._merge_threads(deduped)
        if len(merged) < len(deduped):
            logger.info(
                "Merged %d tweets into self-thread items", len(deduped) - len(merged)
            )
        logger.info("Fetched %d tweets via Playwright.", len(merged))
        return merged

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

    @staticmethod
    def _merge_threads(items: List[ContentItem]) -> List[ContentItem]:
        """Merge same-author self-reply chains (threads) into single items.

        Only tweets replying along a chain rooted at the conversation head
        are merged; same-conversation replies to other people's comments
        stay standalone. Merged segments are preserved structurally in
        metadata["thread_parts"] so renderers can keep per-segment media.
        """
        groups: dict[tuple[str, str], List[ContentItem]] = defaultdict(list)
        result: List[ContentItem] = []
        for item in items:
            conv = str(item.metadata.get("conversation_id") or "")
            if conv and not item.metadata.get("is_retweet"):
                groups[(conv, (item.author or "").lower())].append(item)
            else:
                result.append(item)

        for (conv, _author), group in groups.items():
            if len(group) == 1:
                result.extend(group)
                continue

            group.sort(key=lambda x: x.published_at)
            by_id = {str(it.metadata.get("tweet_id")): it for it in group}
            head = by_id.get(conv) or next(
                (
                    it
                    for it in group
                    if str(it.metadata.get("in_reply_to_status_id") or "") not in by_id
                ),
                group[0],
            )

            chain_ids = {str(head.metadata.get("tweet_id"))}
            chain = [head]
            grew = True
            while grew:
                grew = False
                for it in group:
                    tid = str(it.metadata.get("tweet_id"))
                    if tid in chain_ids:
                        continue
                    if str(it.metadata.get("in_reply_to_status_id") or "") in chain_ids:
                        chain.append(it)
                        chain_ids.add(tid)
                        grew = True

            result.extend(
                it for it in group if str(it.metadata.get("tweet_id")) not in chain_ids
            )
            if len(chain) == 1:
                result.append(head)
                continue

            chain.sort(key=lambda x: x.published_at)
            parts = [
                {
                    "tweet_id": str(it.metadata.get("tweet_id")),
                    "text": it.content or "",
                    "media": it.metadata.get("media") or [],
                    "links": it.metadata.get("links") or [],
                }
                for it in chain
            ]
            head.content = "\n\n".join(p["text"] for p in parts if p["text"])
            head.metadata["thread_parts"] = parts
            head.metadata["thread_length"] = len(chain)
            result.append(head)
            logger.debug("Merged thread %s: %d tweets", conv, len(chain))

        return result

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

        Attachment (media/links/card/article) attribution follows the
        rendered subject: RT and degraded QRT take the original tweet's
        attachments; a substantive QRT keeps its own and stores the quoted
        tweet's under quoted_media / quoted_links.
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
                "category": "ai-news",
            }
            if tweet.get("conversation_id"):
                metadata["conversation_id"] = tweet["conversation_id"]
            if tweet.get("in_reply_to_status_id"):
                metadata["in_reply_to_status_id"] = tweet["in_reply_to_status_id"]

            # Attachments of the rendered subject; reassigned per branch
            attachments = {
                "media": tweet.get("media") or [],
                "links": tweet.get("links") or [],
                "card": tweet.get("card"),
                "article": tweet.get("article"),
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
                attachments = {
                    "media": original.get("media") or [],
                    "links": original.get("links") or [],
                    "card": original.get("card"),
                    "article": original.get("article"),
                }
                nested = original.get("quoted")
                if nested:
                    content += "\n\n" + _format_quote_block(
                        nested.get("author", ""), nested.get("text", "")
                    )
                    metadata["quoted_tweet_id"] = nested.get("tweet_id", "")
                    metadata["quoted_author"] = nested.get("author", "")
                    metadata["quoted_text"] = nested.get("text", "")
                    if nested.get("media"):
                        metadata["quoted_media"] = nested["media"]
                    if nested.get("links"):
                        metadata["quoted_links"] = nested["links"]
                title = f"@{username} 转推 @{orig_author}: {_head(orig_text)}"
                metadata["rt_original_id"] = original.get("tweet_id", "")
                metadata["rt_original_author"] = orig_author
                metadata["rt_original_text"] = orig_text
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
                        metadata["qrt_comment"] = comment
                        metadata["quoted_text"] = quoted_text
                        if quoted.get("media"):
                            metadata["quoted_media"] = quoted["media"]
                        if quoted.get("links"):
                            metadata["quoted_links"] = quoted["links"]
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
                        attachments = {
                            "media": quoted.get("media") or [],
                            "links": quoted.get("links") or [],
                            "card": quoted.get("card"),
                            "article": quoted.get("article"),
                        }
                else:
                    # Quoted tweet unavailable (deleted/protected/empty)
                    if not substantive:
                        logger.debug(
                            "Dropping QRT %s: short comment, quoted tweet unavailable",
                            tweet_id,
                        )
                        return None
                    metadata["qrt_comment"] = comment
                    content = comment + "\n\n> 引用推文不可用"
                    title = f"@{username}: {_head(comment)}"
            else:
                body = text.strip()
                if not body:
                    return None
                content = body
                title = f"@{username}: {_head(body)}"

            if attachments["media"]:
                metadata["media"] = attachments["media"]
            if attachments["links"]:
                metadata["links"] = attachments["links"]
            if attachments["card"]:
                metadata["card"] = attachments["card"]
            if attachments["article"]:
                metadata["article"] = attachments["article"]

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

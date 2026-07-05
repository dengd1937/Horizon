"""Fetch full X Article content for selected items (post AI filtering).

Opens each article tweet's detail page with Playwright (same cookies and
proxy as the timeline scraper) and intercepts the GraphQL response that
carries the article's full content_state. Runs only when selected items
actually reference an article, so normal runs pay zero overhead.
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import List, Optional

from ..models import ContentItem, TwitterConfig
from ..render.article_html import (
    article_to_text,
    extract_cover_url,
    simplify_media_entities,
)
from .twitter_playwright import PROXY, PLAYWRIGHT_AVAILABLE, _load_browser_cookies

if PLAYWRIGHT_AVAILABLE:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

_ARTICLE_OPS = ("TweetDetail", "TweetResultByRestId")

# Separates the original tweet text from appended article full text in
# item.content; renderers split on it to recover the tweet body.
ARTICLE_MARKER = "【文章全文】"


def needs_article_fetch(item: ContentItem) -> bool:
    article = item.metadata.get("article")
    return bool(article and article.get("article_id") and not article.get("content_state"))


def find_article_node(data, article_id: str) -> Optional[dict]:
    """Recursively locate the article result carrying content_state.

    Prefers an exact article_id match; falls back to the first node with a
    content_state (a tweet detail page only embeds its own article).
    """
    fallback: Optional[dict] = None

    def walk(obj) -> Optional[dict]:
        nonlocal fallback
        if isinstance(obj, dict):
            if obj.get("content_state") and (obj.get("rest_id") or obj.get("id")):
                node_id = str(obj.get("rest_id") or obj.get("id") or "")
                if node_id == article_id:
                    return obj
                if fallback is None:
                    fallback = obj
            for value in obj.values():
                hit = walk(value)
                if hit is not None:
                    return hit
        elif isinstance(obj, list):
            for entry in obj:
                hit = walk(entry)
                if hit is not None:
                    return hit
        return None

    return walk(data) or fallback


def merge_article_node(item: ContentItem, node: dict) -> None:
    """Write the fetched full article into item metadata and content."""
    article = dict(item.metadata.get("article") or {})
    article["title"] = node.get("title") or article.get("title", "")
    article["preview_text"] = node.get("preview_text") or article.get("preview_text", "")
    article["content_state"] = node.get("content_state")
    article["media_entities"] = simplify_media_entities(node.get("media_entities") or [])
    cover_url = extract_cover_url(node.get("cover_media") or {})
    if cover_url:
        article["cover_url"] = cover_url
    item.metadata["article"] = article

    full_text = article_to_text(article)
    if full_text:
        item.content = (
            (item.content or "").rstrip() + "\n\n" + ARTICLE_MARKER + "\n" + full_text
        )


class ArticleFetcher:
    """Fetch full text for X Articles referenced by selected items."""

    def __init__(self, config: TwitterConfig):
        self.config = config

    async def fetch_full_articles(self, items: List[ContentItem]) -> int:
        """Fetch article content in-place. Returns number of articles fetched."""
        candidates = [item for item in items if needs_article_fetch(item)]
        if not candidates:
            return 0
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright unavailable; skipping %d article fetches", len(candidates))
            return 0

        cookie_files = sorted(
            Path(self.config.cookie_dir).glob(self.config.cookie_file_pattern)
        )
        if not cookie_files:
            logger.warning("No cookie files; skipping article fetches")
            return 0
        cookies = _load_browser_cookies(str(cookie_files[0]))

        fetched = 0
        async with Stealth().use_async(async_playwright()) as p:
            launch_kwargs: dict = {"headless": True}
            if PROXY:
                launch_kwargs["proxy"] = {"server": PROXY}
            browser = await p.chromium.launch(**launch_kwargs)
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="UTC",
            )
            if cookies:
                await ctx.add_cookies(cookies)

            try:
                for item in candidates:
                    try:
                        if await self._fetch_one(ctx, item):
                            fetched += 1
                    except Exception as exc:
                        logger.warning(
                            "Article fetch failed for %s: %s", item.metadata.get("tweet_id"), exc
                        )
                    await asyncio.sleep(random.uniform(3.0, 6.0))
            finally:
                await ctx.close()
                await browser.close()

        logger.info("Fetched full text for %d/%d articles", fetched, len(candidates))
        return fetched

    async def _fetch_one(self, ctx, item: ContentItem) -> bool:
        article_id = str(item.metadata["article"]["article_id"])
        node: Optional[dict] = None
        page = await ctx.new_page()

        async def on_response(response):
            nonlocal node
            if node is not None or "/graphql/" not in response.url:
                return
            if not any(op in response.url for op in _ARTICLE_OPS):
                return
            try:
                data = await response.json()
            except Exception:
                return
            hit = find_article_node(data, article_id)
            if hit is not None:
                node = hit

        page.on("response", on_response)

        async def route_handler(route):
            if route.request.resource_type in ("media", "image", "video", "font"):
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_handler)

        try:
            await page.goto(str(item.url), wait_until="domcontentloaded", timeout=45000)
            deadline = asyncio.get_event_loop().time() + 25
            while node is None and asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(1)
        finally:
            await page.close()

        if node is None:
            logger.warning("No article content intercepted for %s", item.url)
            return False
        merge_article_node(item, node)
        logger.info(
            "Fetched article %s (%d chars)", article_id, len(item.content or "")
        )
        return True

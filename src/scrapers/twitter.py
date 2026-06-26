"""Twitter scraper using Apify altimis/scweet actor."""

import asyncio
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from html import unescape
from typing import List, Optional

from dateutil.parser import isoparse
import httpx

from .base import BaseScraper
from ..models import ContentItem, SourceType, TwitterConfig

logger = logging.getLogger(__name__)

_APIFY_BASE = "https://api.apify.com/v2"
_POLL_INTERVAL = 3.0
_MAX_WAIT_PER_USER = 90
_RETRY_DELAY = 5.0
_RT_MIN_TEXT_LEN = 30
_RT_PREFIX_RE = re.compile(r"^RT @\w+:\s*")


class TwitterScraper(BaseScraper):
    """Fetch tweets via the Apify altimis/scweet actor."""

    def __init__(self, config: TwitterConfig, http_client: httpx.AsyncClient):
        super().__init__(config, http_client)
        self.config = config

    async def fetch(self, since: datetime) -> List[ContentItem]:
        if not self.config.enabled:
            return []

        users = [u.strip().lstrip("@") for u in self.config.users if u.strip()]
        if not users:
            logger.debug("No Twitter users configured, skipping.")
            return []

        token = os.environ.get(self.config.apify_token_env)
        if not token:
            logger.warning(
                f"Apify token not found in env var '{self.config.apify_token_env}'. Skipping Twitter."
            )
            return []

        logger.info(f"Fetching Twitter (Apify) for {len(users)} users, concurrency={self.config.actor_concurrency}")

        semaphore = asyncio.Semaphore(self.config.actor_concurrency)
        results = await asyncio.gather(
            *(self._fetch_user(token, user, since, semaphore) for user in users),
            return_exceptions=True,
        )

        all_items: List[ContentItem] = []
        succeeded_users: list[str] = []
        failed_users: list[str] = []

        for user, result in zip(users, results):
            if isinstance(result, Exception):
                logger.error(f"@{user}: unexpected error: {result}")
                failed_users.append(user)
            elif result:
                all_items.extend(result)
                succeeded_users.append(user)
                logger.info(f"  @{user}: {len(result)} tweets")
            else:
                succeeded_users.append(user)
                logger.info(f"  @{user}: 0 tweets")

        if failed_users:
            logger.warning(f"Failed users: {failed_users}")
        logger.info(
            f"Twitter raw: {len(all_items)} tweets from "
            f"{len(succeeded_users)}/{len(users)} users"
        )

        merged = self._merge_threads(all_items)
        logger.info(f"Twitter after thread merge: {len(merged)} items")
        return merged

    async def _fetch_user(
        self,
        token: str,
        username: str,
        since: datetime,
        semaphore: asyncio.Semaphore,
    ) -> List[ContentItem]:
        async with semaphore:
            items = await self._run_actor_for_user(token, username, since)
            if items is not None:
                return items
            logger.info(f"  @{username}: retrying after {_RETRY_DELAY}s...")
            await asyncio.sleep(_RETRY_DELAY)
            items = await self._run_actor_for_user(token, username, since)
            return items or []

    async def _run_actor_for_user(
        self, token: str, username: str, since: datetime
    ) -> Optional[List[ContentItem]]:
        run_id, dataset_id = await self._start_run(token, username)
        if not run_id:
            return None

        succeeded = await self._wait_for_run(token, run_id)
        if not succeeded:
            return None

        raw_items = await self._fetch_dataset(token, dataset_id)
        items = []
        for raw in raw_items:
            if isinstance(raw, dict) and raw.get("noResults"):
                continue
            parsed = self._parse_item(raw, since)
            if parsed:
                items.append(parsed)
        return items

    async def _start_run(
        self, token: str, username: str
    ) -> tuple[Optional[str], Optional[str]]:
        payload = {
            "source_mode": "profiles",
            "profile_urls": [username],
            "search_sort": "Latest",
            "max_items": max(100, self.config.fetch_limit),
        }
        url = f"{_APIFY_BASE}/acts/{self.config.actor_id}/runs?token={token}"
        try:
            resp = await self.client.post(url, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()["data"]
            run_id = data["id"]
            dataset_id = data["defaultDatasetId"]
            logger.debug(f"Started Apify run for @{username}: {run_id}")
            return run_id, dataset_id
        except Exception as exc:
            logger.error(f"Failed to start Apify run for @{username}: {exc}")
            return None, None

    async def _wait_for_run(self, token: str, run_id: str) -> bool:
        url = f"{_APIFY_BASE}/actor-runs/{run_id}?token={token}"
        elapsed = 0.0
        while elapsed < _MAX_WAIT_PER_USER:
            try:
                resp = await self.client.get(url, timeout=10.0)
                resp.raise_for_status()
                status = resp.json()["data"]["status"]
                if status == "SUCCEEDED":
                    return True
                if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.error(f"Apify run {run_id} ended with status: {status}")
                    return False
            except Exception as exc:
                logger.warning(f"Error polling Apify run {run_id}: {exc}")
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
        logger.warning(f"Apify run {run_id} timed out after {_MAX_WAIT_PER_USER}s.")
        return False

    async def _fetch_dataset(self, token: str, dataset_id: str) -> list:
        url = f"{_APIFY_BASE}/datasets/{dataset_id}/items?token={token}"
        try:
            resp = await self.client.get(url, timeout=30.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error(f"Failed to fetch Apify dataset {dataset_id}: {exc}")
            return []

    async def fetch_replies_for_item(self, item: ContentItem) -> List[str]:
        """Fetch reply texts for one tweet using scweet search mode."""
        if not self.config.fetch_reply_text:
            return []

        token = os.environ.get(self.config.apify_token_env)
        if not token:
            return []

        conversation_id = str(item.metadata.get("conversation_id") or "")
        if not conversation_id:
            return []

        max_replies = max(self.config.max_replies_per_tweet, 0)
        if max_replies == 0:
            return []

        max_items = max(100, max_replies * 5)
        payload = {
            "source_mode": "search",
            "search_query": f"conversation_id:{conversation_id}",
            "search_sort": "Latest",
            "max_items": max_items,
        }

        url = f"{_APIFY_BASE}/acts/{self.config.actor_id}/runs?token={token}"
        try:
            resp = await self.client.post(url, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()["data"]
            run_id = data["id"]
            dataset_id = data["defaultDatasetId"]
        except Exception as exc:
            logger.warning(f"Failed to start replies run for {item.id}: {exc}")
            return []

        if not await self._wait_for_run(token, run_id):
            return []

        rows = await self._fetch_dataset(token, dataset_id)
        return self._extract_reply_lines(item, rows, max_replies)

    def _extract_reply_lines(self, item: ContentItem, rows: list, max_replies: int) -> List[str]:
        """Convert scweet rows into compact reply lines."""
        min_likes = max(self.config.reply_min_likes, 0)
        tweet_id = str(item.metadata.get("tweet_id") or "")
        own_author = (item.author or "").lstrip("@")
        candidates = []

        for row in rows:
            if not isinstance(row, dict) or row.get("noResults"):
                continue

            row_id = str(row.get("id") or "")
            if row_id.startswith("tweet-"):
                row_id = row_id[6:]
            if tweet_id and row_id == tweet_id:
                continue

            user = row.get("user") or {}
            handle = (
                user.get("handle")
                or row.get("handle")
                or user.get("username")
                or "unknown"
            )
            if handle and own_author and handle.lower() == own_author.lower():
                continue

            text = unescape((row.get("text") or "").strip())
            if not text:
                continue

            likes = int(row.get("favorite_count") or 0)
            replies = int(row.get("reply_count") or 0)
            if likes < min_likes:
                continue

            score = likes * 2 + replies
            line = f"[@{handle} | ❤️ {likes} | 💬 {replies}] {text[:280]}"
            candidates.append((score, line))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [line for _, line in candidates[:max_replies]]

    @staticmethod
    def append_discussion_content(item: ContentItem, reply_lines: List[str]) -> bool:
        """Append reply lines under Top Comments marker."""
        if not reply_lines:
            return False

        existing = item.content or ""
        marker = "--- Top Comments ---"
        block = "\n".join(reply_lines)

        if marker in existing:
            if block in existing:
                return False
            item.content = existing + "\n" + block
            return True

        if existing:
            item.content = existing + f"\n\n{marker}\n" + block
        else:
            item.content = f"{marker}\n" + block
        return True

    def _parse_item(self, item: dict, since: datetime) -> Optional[ContentItem]:
        try:
            created_at_str = item.get("created_at")
            if not created_at_str:
                return None

            try:
                published_at = datetime.strptime(
                    created_at_str, "%a %b %d %H:%M:%S %z %Y"
                )
            except ValueError:
                published_at = isoparse(created_at_str)

            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)

            if published_at < since:
                return None

            tweet_id = str(item.get("id_str") or item.get("id") or "")
            if not tweet_id:
                return None

            raw_id = item.get("id") or ""
            numeric_id = (
                str(raw_id).replace("tweet-", "")
                if str(raw_id).startswith("tweet-")
                else tweet_id
            )
            conversation_id = str(
                item.get("conversation_id")
                or item.get("tweet", {}).get("conversation_id")
                or numeric_id
            )

            user = item.get("user") or {}
            screen_name = (
                user.get("screen_name")
                or user.get("username")
                or user.get("handle")
                or item.get("handle")
                or item.get("username")
                or "unknown"
            )
            author = user.get("name") or screen_name

            text = item.get("full_text") or item.get("text") or ""
            if not text:
                return None
            text = unescape(text)

            configured_users = {u.lower() for u in self.config.users}

            # --- RT handling ---
            is_rt = text.startswith("RT @")
            if is_rt:
                body = _RT_PREFIX_RE.sub("", text).strip()
                if len(body) < _RT_MIN_TEXT_LEN:
                    logger.debug(f"Dropping short RT from @{screen_name}: {text[:60]}")
                    return None
                rt_match = re.match(r"^RT @(\w+):", text)
                rt_original_author = rt_match.group(1) if rt_match else "unknown"
                text = body
                title_body = text[:50].replace("\n", " ").strip()
                if len(text) > 50:
                    title_body += "..."
                title = f"@{screen_name} 转推 @{rt_original_author}: {title_body}"
            else:
                # --- Cross-author reply filtering ---
                is_reply = item.get("is_reply", False)
                reply_to = item.get("in_reply_to_screen_name") or ""
                if is_reply and reply_to:
                    reply_to_lower = reply_to.lower()
                    if (reply_to_lower != screen_name.lower()
                            and reply_to_lower not in configured_users):
                        logger.debug(
                            f"Dropping cross-author reply from @{screen_name} "
                            f"to @{reply_to}: {text[:60]}"
                        )
                        return None

                title_body = text[:50].replace("\n", " ").strip()
                if len(text) > 50:
                    title_body += "..."
                title = f"@{screen_name}: {title_body}"

            url = item.get("url")
            if not url:
                permalink = item.get("permalink")
                if permalink and screen_name != "unknown":
                    url = f"https://twitter.com/{screen_name}{permalink}"
                else:
                    url = f"https://twitter.com/{screen_name}/status/{tweet_id}"

            return ContentItem(
                id=self._generate_id(SourceType.TWITTER.value, "tweet", numeric_id),
                source_type=SourceType.TWITTER,
                title=title,
                url=url,
                content=text,
                author=author,
                published_at=published_at,
                metadata={
                    "tweet_id": numeric_id,
                    "conversation_id": conversation_id,
                    "favorite_count": item.get("favorite_count", 0),
                    "retweet_count": item.get("retweet_count", 0),
                    "reply_count": item.get("reply_count", 0),
                    "view_count": item.get("view_count"),
                    "is_reply": item.get("is_reply", False),
                    "is_retweet": is_rt,
                    "in_reply_to_status_id": item.get("in_reply_to_status_id"),
                    "in_reply_to_screen_name": item.get("in_reply_to_screen_name"),
                    "category": "ai-news",
                },
            )
        except Exception as exc:
            logger.debug(f"Failed to parse tweet: {exc}")
            return None

    @staticmethod
    def _merge_threads(items: List[ContentItem]) -> List[ContentItem]:
        """Merge same-author reply chains (threads) into single items."""
        by_conv: dict[str, list[ContentItem]] = defaultdict(list)
        for item in items:
            conv_id = item.metadata.get("conversation_id", "")
            by_conv[conv_id].append(item)

        result: list[ContentItem] = []
        for conv_id, group in by_conv.items():
            author_items: dict[str, list[ContentItem]] = defaultdict(list)
            for it in group:
                author_items[(it.author or "").lower()].append(it)

            for author, author_group in author_items.items():
                if len(author_group) == 1:
                    result.append(author_group[0])
                    continue

                author_group.sort(key=lambda x: x.published_at)
                head = author_group[0]
                tail_texts = [it.content for it in author_group[1:] if it.content]
                if tail_texts:
                    head.content = (head.content or "") + "\n\n" + "\n\n".join(tail_texts)

                for it in author_group[1:]:
                    head.metadata["favorite_count"] = (
                        head.metadata.get("favorite_count", 0)
                        + it.metadata.get("favorite_count", 0)
                    )
                    head.metadata["retweet_count"] = (
                        head.metadata.get("retweet_count", 0)
                        + it.metadata.get("retweet_count", 0)
                    )

                head.metadata["thread_length"] = len(author_group)
                result.append(head)
                logger.debug(
                    f"Merged thread {conv_id}: {len(author_group)} tweets by @{author}"
                )

        return result

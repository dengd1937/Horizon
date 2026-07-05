"""Download remote media referenced by items into local site assets.

twimg.com domains are blocked without a proxy just like x.com, so the
reading site must serve every image/video from its own assets directory.
Successful downloads are recorded per item in metadata["asset_map"]
(remote url -> site-relative path); original URL fields stay untouched.
"""

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, urlsplit

import httpx

from ..models import ContentItem, SiteConfig
from ..scrapers.twitter_playwright import _get_proxy

logger = logging.getLogger(__name__)

_EXT_RE = re.compile(r"\.(jpg|jpeg|png|gif|webp|mp4|m4v|webm)$", re.IGNORECASE)
_IMAGE_FORMATS = {"jpg", "jpeg", "png", "gif", "webp"}
_CHUNK_SIZE = 65536


class _OversizeError(Exception):
    pass


def collect_media_urls(item: ContentItem) -> list[str]:
    """All remote media URLs one item references, in stable order."""
    urls: list[str] = []
    meta = item.metadata

    def add(url) -> None:
        if isinstance(url, str) and url.startswith("http") and url not in urls:
            urls.append(url)

    def add_media_list(media_list) -> None:
        for m in media_list or []:
            add(m.get("thumbnail_url"))
            add(m.get("mp4_url"))

    add_media_list(meta.get("media"))
    add_media_list(meta.get("quoted_media"))
    for part in meta.get("thread_parts") or []:
        add_media_list(part.get("media"))
    add((meta.get("card") or {}).get("thumbnail_url"))
    article = meta.get("article") or {}
    for entity in article.get("media_entities") or []:
        add(entity.get("url"))
    add(article.get("cover_url"))
    return urls


def _infer_ext(url: str) -> str:
    parts = urlsplit(url)
    fmt = (parse_qs(parts.query).get("format") or [""])[0].lower()
    if fmt in _IMAGE_FORMATS:
        return f".{fmt}"
    match = _EXT_RE.search(parts.path)
    if match:
        return f".{match.group(1).lower()}"
    if "video.twimg.com" in parts.netloc:
        return ".mp4"
    return ".jpg"


def asset_filename(url: str) -> str:
    """Stable content-addressed filename for a remote URL."""
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    return f"{digest}{_infer_ext(url)}"


class MediaDownloader:
    """Download referenced media for a run into output_dir/assets/{date}/."""

    def __init__(
        self,
        config: SiteConfig,
        transport: Optional[httpx.BaseTransport] = None,
        concurrency: int = 4,
    ):
        self.config = config
        self._transport = transport  # tests inject httpx.MockTransport
        self._concurrency = max(concurrency, 1)

    async def download_for_items(self, items: List[ContentItem], date: str) -> int:
        """Download all referenced media; write asset_map per item.

        Returns the number of files newly downloaded. Failures degrade to
        "no mapping" so renderers fall back to the remote URL.
        """
        wanted: dict[str, list[ContentItem]] = {}
        for item in items:
            for url in collect_media_urls(item):
                wanted.setdefault(url, []).append(item)
        if not wanted:
            return 0

        assets_dir = Path(self.config.output_dir) / "assets" / date
        assets_dir.mkdir(parents=True, exist_ok=True)
        size_cap = self.config.max_media_mb * 1024 * 1024
        resolved: dict[str, str] = {}
        downloaded = 0

        client_kwargs: dict = {"timeout": 60.0, "follow_redirects": True}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        else:
            proxy = _get_proxy()
            if proxy:
                client_kwargs["proxy"] = proxy

        semaphore = asyncio.Semaphore(self._concurrency)

        async with httpx.AsyncClient(**client_kwargs) as client:

            async def fetch(url: str) -> None:
                nonlocal downloaded
                filename = asset_filename(url)
                dest = assets_dir / filename
                rel_path = f"assets/{date}/{filename}"
                if dest.exists():
                    resolved[url] = rel_path
                    return
                async with semaphore:
                    try:
                        async with client.stream("GET", url) as response:
                            if response.status_code != 200:
                                logger.warning(
                                    "Media download HTTP %d: %s", response.status_code, url
                                )
                                return
                            declared = int(response.headers.get("content-length") or 0)
                            if declared > size_cap:
                                logger.warning(
                                    "Skipping oversized media (%d MB > %d MB): %s",
                                    declared // (1024 * 1024),
                                    self.config.max_media_mb,
                                    url,
                                )
                                return
                            written = 0
                            with open(dest, "wb") as f:
                                async for chunk in response.aiter_bytes(_CHUNK_SIZE):
                                    written += len(chunk)
                                    if written > size_cap:
                                        raise _OversizeError()
                                    f.write(chunk)
                        resolved[url] = rel_path
                        downloaded += 1
                    except _OversizeError:
                        dest.unlink(missing_ok=True)
                        logger.warning(
                            "Aborted oversized media (> %d MB): %s",
                            self.config.max_media_mb,
                            url,
                        )
                    except Exception as exc:
                        dest.unlink(missing_ok=True)
                        logger.warning("Media download failed %s: %s", url, exc)

            await asyncio.gather(*(fetch(url) for url in wanted))

        for item in items:
            mapping = {
                url: resolved[url]
                for url in collect_media_urls(item)
                if url in resolved
            }
            if mapping:
                item.metadata["asset_map"] = mapping

        logger.info(
            "Media download: %d new, %d resolved, %d referenced",
            downloaded,
            len(resolved),
            len(wanted),
        )
        return downloaded

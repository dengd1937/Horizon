"""Tests for the site media downloader (URL collection, naming, download)."""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from src.models import ContentItem, SiteConfig, SourceType
from src.render.assets import (
    MediaDownloader,
    asset_filename,
    collect_media_urls,
)


def _item(**meta) -> ContentItem:
    return ContentItem(
        id="twitter:tweet:1",
        source_type=SourceType.TWITTER,
        title="t",
        url="https://x.com/u/status/1",
        published_at=datetime.now(timezone.utc),
        metadata=meta,
    )


# ---------- URL collection ----------


def test_collect_media_urls_covers_all_shapes():
    item = _item(
        media=[{"type": "video", "thumbnail_url": "https://p/1.jpg", "mp4_url": "https://v/1.mp4"}],
        quoted_media=[{"type": "photo", "thumbnail_url": "https://p/2.jpg"}],
        thread_parts=[{"media": [{"type": "photo", "thumbnail_url": "https://p/3.jpg"}]}],
        card={"thumbnail_url": "https://p/card.jpg"},
        article={
            "media_entities": [{"media_id": "9", "url": "https://p/art.png"}],
            "cover_url": "https://p/cover.jpg",
        },
    )
    urls = collect_media_urls(item)
    assert urls == [
        "https://p/1.jpg",
        "https://v/1.mp4",
        "https://p/2.jpg",
        "https://p/3.jpg",
        "https://p/card.jpg",
        "https://p/art.png",
        "https://p/cover.jpg",
    ]


def test_collect_media_urls_dedupes_and_ignores_junk():
    item = _item(
        media=[
            {"type": "photo", "thumbnail_url": "https://p/same.jpg"},
            {"type": "photo", "thumbnail_url": "https://p/same.jpg"},
            {"type": "photo", "thumbnail_url": None},
            {"type": "photo", "thumbnail_url": ""},
        ]
    )
    assert collect_media_urls(item) == ["https://p/same.jpg"]
    assert collect_media_urls(_item()) == []


# ---------- filename inference ----------


def test_asset_filename_stable_and_ext_inference():
    fmt_url = "https://pbs.twimg.com/media/ABC?format=png&name=large"
    path_url = "https://pbs.twimg.com/media/ABC.webp"
    video_url = "https://video.twimg.com/amplify_video/1/vid/avc1/720x1280/x"
    plain = "https://pbs.twimg.com/media/noext"

    assert asset_filename(fmt_url).endswith(".png")
    assert asset_filename(path_url).endswith(".webp")
    assert asset_filename(video_url).endswith(".mp4")
    assert asset_filename(plain).endswith(".jpg")
    assert asset_filename(fmt_url) == asset_filename(fmt_url)
    assert asset_filename(fmt_url) != asset_filename(path_url)


# ---------- download behaviour (MockTransport) ----------


def _downloader(tmp_path, handler, max_mb: int = 50) -> MediaDownloader:
    cfg = SiteConfig(enabled=True, output_dir=str(tmp_path), max_media_mb=max_mb)
    return MediaDownloader(cfg, transport=httpx.MockTransport(handler))


def _media_response(content: bytes = b"DATA", *, media_type: str = "image/jpeg"):
    return httpx.Response(200, headers={"content-type": media_type}, content=content)


def test_download_writes_files_and_asset_map(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "missing" in str(request.url):
            return httpx.Response(404)
        return _media_response()

    item = _item(
        media=[
            {"type": "photo", "thumbnail_url": "https://p/ok.jpg"},
            {"type": "photo", "thumbnail_url": "https://p/missing.jpg"},
        ]
    )
    dl = _downloader(tmp_path, handler)
    n = asyncio.run(dl.download_for_items([item], "2026-07-05"))

    assert n == 1
    mapping = item.metadata["asset_map"]
    assert list(mapping) == ["https://p/ok.jpg"]
    rel = mapping["https://p/ok.jpg"]
    assert rel.startswith("assets/2026-07-05/")
    assert (tmp_path / rel).read_bytes() == b"DATA"
    # failed URL leaves no file behind
    assert len(list((tmp_path / "assets" / "2026-07-05").iterdir())) == 1


def test_download_idempotent_skips_existing(tmp_path):
    counter = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        return _media_response()

    item = _item(media=[{"type": "photo", "thumbnail_url": "https://p/ok.jpg"}])
    dl = _downloader(tmp_path, handler)
    assert asyncio.run(dl.download_for_items([item], "2026-07-05")) == 1
    item2 = _item(media=[{"type": "photo", "thumbnail_url": "https://p/ok.jpg"}])
    assert asyncio.run(dl.download_for_items([item2], "2026-07-05")) == 0
    assert counter["n"] == 1
    assert item2.metadata["asset_map"]["https://p/ok.jpg"].startswith("assets/")


def test_download_shared_url_downloaded_once_mapped_to_all(tmp_path):
    counter = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        return _media_response()

    a = _item(media=[{"type": "photo", "thumbnail_url": "https://p/shared.jpg"}])
    b = _item(card={"thumbnail_url": "https://p/shared.jpg"})
    dl = _downloader(tmp_path, handler)
    asyncio.run(dl.download_for_items([a, b], "2026-07-05"))
    assert counter["n"] == 1
    assert a.metadata["asset_map"] == b.metadata["asset_map"]


def test_download_oversized_declared_and_streamed(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "declared" in url:
            return httpx.Response(
                200,
                headers={
                    "content-length": str(99 * 1024 * 1024),
                    "content-type": "video/mp4",
                },
                content=b"x",
            )
        return _media_response(
            b"y" * (2 * 1024 * 1024), media_type="video/mp4"
        )

    item = _item(
        media=[
            {"type": "video", "mp4_url": "https://v/declared.mp4"},
            {"type": "video", "mp4_url": "https://v/streamed.mp4"},
        ]
    )
    dl = _downloader(tmp_path, handler, max_mb=1)
    n = asyncio.run(dl.download_for_items([item], "2026-07-05"))
    assert n == 0
    assert "asset_map" not in item.metadata
    assert list((tmp_path / "assets" / "2026-07-05").iterdir()) == []


def test_download_no_urls_no_dir(tmp_path):
    dl = _downloader(tmp_path, lambda r: httpx.Response(200))
    assert asyncio.run(dl.download_for_items([_item()], "2026-07-05")) == 0
    assert not (tmp_path / "assets").exists()


def test_download_urls_supports_article_asset_directory(tmp_path):
    url = "https://media.example/cover.jpg"
    dl = _downloader(tmp_path, lambda r: _media_response(b"IMAGE"))

    mapping, downloaded = asyncio.run(
        dl.download_urls([url, url], relative_dir="assets/articles/example-20260701-title")
    )

    assert downloaded == 1
    assert mapping[url].startswith("assets/articles/example-20260701-title/")
    assert (tmp_path / mapping[url]).read_bytes() == b"IMAGE"


def test_download_urls_rejects_unsafe_directory(tmp_path):
    dl = _downloader(tmp_path, lambda r: _media_response(b"IMAGE"))
    with pytest.raises(ValueError, match="unsafe media relative directory"):
        asyncio.run(dl.download_urls(["https://media.example/cover.jpg"], relative_dir="../x"))


def test_download_rejects_non_media_response(tmp_path):
    url = "https://media.example/not-an-image.jpg"
    dl = _downloader(
        tmp_path,
        lambda r: httpx.Response(
            200, headers={"content-type": "text/html"}, content=b"<script>x</script>"
        ),
    )

    mapping, downloaded = asyncio.run(
        dl.download_urls([url], relative_dir="assets/articles/test")
    )

    assert mapping == {}
    assert downloaded == 0
    assert not list((tmp_path / "assets" / "articles" / "test").iterdir())


def test_download_revalidates_redirects_and_rejects_private_destination(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if len(seen) == 1:
            return httpx.Response(
                302, headers={"location": "http://127.0.0.1:9999/internal"}
            )
        return _media_response(b"SECRET")

    dl = _downloader(tmp_path, handler)
    mapping, downloaded = asyncio.run(
        dl.download_urls(
            ["https://public.example/redirect.jpg"],
            relative_dir="assets/articles/test",
        )
    )

    assert seen == ["https://public.example/redirect.jpg"]
    assert mapping == {}
    assert downloaded == 0


def test_download_rejects_plain_http_before_transport(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _media_response()

    dl = _downloader(tmp_path, handler)
    mapping, downloaded = asyncio.run(
        dl.download_urls(
            ["http://media.example/image.jpg"],
            relative_dir="assets/articles/test",
        )
    )

    assert seen == []
    assert mapping == {}
    assert downloaded == 0

"""Render and publish the article and paper libraries without the daily pipeline."""

import asyncio
from pathlib import Path

from src.render.assets import MediaDownloader, asset_filename
from src.render.curated import (
    article_media_urls,
    load_articles,
    localize_article_media,
    render_curated,
)
from src.render.deploy import deploy_site
from src.render.papers import render_papers
from src.render.publication import (
    build_libraries_release_manifest,
    load_previous_manifest,
    pending_manifest_path,
)
from src.render.site_css import write_site_css
from src.papers.contract import load_papers
from src.storage.manager import StorageManager


def _bootstrap_existing_library_media(site_root: Path, articles):
    """Build a local-only baseline for the one-time incremental cutover."""
    media: dict[str, set[str]] = {}
    paths: list[Path] = []
    for article in articles:
        for url in article_media_urls(article):
            key = f"assets/articles/{article.slug}/{asset_filename(url)}"
            path = site_root / key
            if path.is_file():
                media.setdefault(url, set()).add(key)
                paths.append(path)
    if not media:
        return None
    return build_libraries_release_manifest(site_root, paths, media)


async def main() -> None:
    storage = StorageManager("data")
    config = storage.load_config()
    if not config.site.enabled:
        raise RuntimeError("site.enabled must be true to publish curated articles")

    site_root = Path(config.site.output_dir)
    previous = load_previous_manifest(site_root, "libraries", "current")
    articles = load_articles(Path(config.site.articles_source_dir))
    if previous is None:
        previous = _bootstrap_existing_library_media(site_root, articles)
        if previous is not None:
            previous.write(
                site_root / ".horizon-state" / "releases" / "libraries.json"
            )
    downloader = MediaDownloader(
        config.site,
        known_assets=previous.media if previous else None,
    )
    downloaded = await localize_article_media(articles, downloader)
    paths = render_curated(site_root, articles)
    print(
        f"Rendered {len(paths)} curated article page(s); "
        f"downloaded {downloaded} media file(s)."
    )

    papers = load_papers(Path(config.site.papers_source_dir))
    paper_paths = render_papers(site_root, papers)
    print(f"Rendered {len(paper_paths)} paper library page(s).")

    media: dict[str, set[str]] = {}
    for article in articles:
        for url, key in article.asset_map.items():
            media.setdefault(url, set()).add(key)
    release = build_libraries_release_manifest(
        site_root,
        [*paths, *paper_paths, write_site_css(site_root)],
        media,
        previous=previous,
    )
    release.write(pending_manifest_path(site_root, "libraries"))

    if config.site.deploy_command:
        deployed = await deploy_site(config.site)
        if deployed is False:
            raise RuntimeError("content library deployment failed")


if __name__ == "__main__":
    asyncio.run(main())

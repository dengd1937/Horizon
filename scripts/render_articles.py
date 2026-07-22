"""Render and publish the article and paper libraries without the daily pipeline."""

import asyncio
from pathlib import Path

from src.render.assets import MediaDownloader
from src.render.curated import load_articles, localize_article_media, render_curated
from src.render.deploy import deploy_site
from src.render.papers import render_papers
from src.render.site import backfill_paper_library_navigation
from src.papers.contract import load_papers
from src.storage.manager import StorageManager


async def main() -> None:
    storage = StorageManager("data")
    config = storage.load_config()
    if not config.site.enabled:
        raise RuntimeError("site.enabled must be true to publish curated articles")

    articles = load_articles(Path(config.site.articles_source_dir))
    downloader = MediaDownloader(config.site)
    downloaded = await localize_article_media(articles, downloader)
    paths = render_curated(Path(config.site.output_dir), articles)
    print(
        f"Rendered {len(paths)} curated article page(s); "
        f"downloaded {downloaded} media file(s)."
    )

    papers = load_papers(Path(config.site.papers_source_dir))
    paper_paths = render_papers(Path(config.site.output_dir), papers)
    print(f"Rendered {len(paper_paths)} paper library page(s).")

    migrated_pages = backfill_paper_library_navigation(Path(config.site.output_dir))
    print(f"Backfilled paper navigation on {len(migrated_pages)} daily page(s).")

    deployed = await deploy_site(config.site)
    if deployed is False:
        raise RuntimeError("content library deployment failed")


if __name__ == "__main__":
    asyncio.run(main())

"""Static contracts for production site deployment workflows."""

import json
from pathlib import Path

from scripts.render_articles import _bootstrap_existing_library_media
from src.render.assets import asset_filename
from src.render.curated import article_media_urls, load_articles


def test_article_publish_workflow_is_scoped_and_uses_cos():
    workflow = Path(".github/workflows/publish-articles.yml").read_text(encoding="utf-8")

    assert '"articles/**"' in workflow
    assert '"papers/**"' in workflow
    assert '"src/papers/**"' in workflow
    assert '"src/render/papers.py"' in workflow
    assert '"src/render/paper_index_js.py"' in workflow
    assert '"src/render/site.py"' in workflow
    assert "branches:" in workflow
    assert "- main" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "group: horizon-production-site" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "scripts/render_articles.py" in workflow
    assert "scripts/restore_site_state.py libraries" in workflow
    assert "scripts/publish_site.py libraries" in workflow
    assert '$COS_SITE_BUCKET/assets/articles/' in workflow
    assert "coscli sync" not in workflow
    assert "--delete" not in workflow
    assert "|| echo" not in workflow
    assert "actions-gh-pages" not in workflow
    assert "Twitter" not in workflow
    assert "DEEPSEEK_API_KEY" not in workflow
    assert "EMAIL_PASSWORD" not in workflow
    assert "email_delivery_state" not in workflow


def test_content_library_publish_script_builds_manifest_without_daily_backfill():
    script = Path("scripts/render_articles.py").read_text(encoding="utf-8")

    assert "load_papers" in script
    assert "render_papers" in script
    assert "backfill_paper_library_navigation" not in script
    assert "build_libraries_release_manifest" in script
    assert script.index("render_papers") < script.index(
        "build_libraries_release_manifest"
    )


def test_deploy_workflows_share_a_fail_closed_concurrency_boundary():
    daily = Path(".github/workflows/daily-summary.yml").read_text(encoding="utf-8")
    articles = Path(".github/workflows/publish-articles.yml").read_text(
        encoding="utf-8"
    )

    for workflow in (daily, articles):
        assert "group: horizon-production-site" in workflow
        assert "cancel-in-progress: false" in workflow
        assert "|| echo" not in workflow
        assert "curl -fsSL" in workflow
        assert "coscli sync" not in workflow
        assert "--delete" not in workflow
        assert "COS_SITE_BUCKET" in workflow
        assert "COS_STATE_BUCKET" in workflow
        assert "cos://signalfeed-state-1257788828" in workflow
        assert "COS_ENDPOINT" in workflow
        assert "--init-skip=true" in workflow
        assert "scripts/restore_site_state.py" in workflow
        assert "scripts/publish_site.py" in workflow

    assert "Restore incremental publication state" in daily
    assert "Persist email delivery state" in daily
    assert ".horizon-state/email_delivery_state.json" in daily
    assert (
        "$COS_STATE_BUCKET/.horizon-state/email_delivery_state.json" in daily
    )


def test_production_config_separates_canonical_url_from_legacy_prefix():
    config = json.loads(Path("data/config.github.json").read_text(encoding="utf-8"))
    site = config["site"]

    assert site["base_url"] == "https://www.signalfeed.site"
    assert site["deploy_command"] is None
    assert "COS_SITE_PREFIX" not in site["base_url"]


def test_content_media_cutover_baseline_owns_only_existing_expected_assets(tmp_path):
    articles = load_articles(Path("tests/fixtures/articles"))
    article = articles[0]
    url = article_media_urls(article)[0]
    key = f"assets/articles/{article.slug}/{asset_filename(url)}"
    path = tmp_path / key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"existing remote media")

    baseline = _bootstrap_existing_library_media(tmp_path, articles)

    assert baseline is not None
    assert set(baseline.objects) == {key}
    assert baseline.media[url] == (key,)

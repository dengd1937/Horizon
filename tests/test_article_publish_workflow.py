"""Static contracts for production site deployment workflows."""

import json
from pathlib import Path


def test_article_publish_workflow_is_scoped_and_uses_cos():
    workflow = Path(".github/workflows/publish-articles.yml").read_text(encoding="utf-8")

    assert '"articles/**"' in workflow
    assert "branches:" in workflow
    assert "- main" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "group: horizon-production-site" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "scripts/render_articles.py" in workflow
    assert "coscli sync" in workflow
    assert "|| echo" not in workflow
    assert "actions-gh-pages" not in workflow
    assert "Twitter" not in workflow
    assert "DEEPSEEK_API_KEY" not in workflow
    assert "EMAIL_PASSWORD" not in workflow
    assert "email_delivery_state" not in workflow


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
        assert 'coscli sync "cos://signalfeed-1257788828/" data/site/' in workflow
        assert '--exclude "^d/.*$"' in workflow
        assert "COS_SITE_PREFIX" not in workflow

    assert "Restore email delivery state" in daily
    assert "Persist email delivery state" in daily
    assert ".horizon-state/email_delivery_state.json" in daily
    assert (
        "cos://signalfeed-1257788828/.horizon-state/email_delivery_state.json"
        in daily
    )


def test_production_config_separates_canonical_url_from_legacy_prefix():
    config = json.loads(Path("data/config.github.json").read_text(encoding="utf-8"))
    site = config["site"]

    assert site["base_url"] == "https://www.signalfeed.site"
    assert "cos://signalfeed-1257788828/" in site["deploy_command"]
    assert '--exclude "^d/.*$"' in site["deploy_command"]
    assert "COS_SITE_PREFIX" not in site["base_url"]
    assert "COS_SITE_PREFIX" not in site["deploy_command"]

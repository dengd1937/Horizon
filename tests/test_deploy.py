"""Tests for the site deploy command runner."""

import asyncio

from src.models import SiteConfig
from src.render.deploy import deploy_site


def _run(cfg: SiteConfig, **kwargs):
    return asyncio.run(deploy_site(cfg, **kwargs))


def test_no_command_is_local_mode():
    assert _run(SiteConfig()) is None
    assert _run(SiteConfig(deploy_command="   ")) is None


def test_successful_command():
    assert _run(SiteConfig(deploy_command="echo uploaded")) is True


def test_nonzero_exit_reports_failure():
    assert _run(SiteConfig(deploy_command="exit 3")) is False


def test_missing_binary_reports_failure():
    assert _run(SiteConfig(deploy_command="definitely-not-a-command-xyz")) is False


def test_timeout_kills_and_reports_failure():
    assert _run(SiteConfig(deploy_command="sleep 5"), timeout=0.3) is False

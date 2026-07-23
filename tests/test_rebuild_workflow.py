"""Contracts for explicit historical rebuild and legacy CSS migration."""

import json
from pathlib import Path

from scripts.migrate_legacy_css import migrate_legacy_css
from scripts.rebuild_daily_site import _selected_dates


def test_selected_dates_uses_existing_manifest_dates_only(tmp_path):
    manifest = tmp_path / "site_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "2026-07-01": {},
                "2026-07-03": {},
                "2026-07-10": {},
            }
        ),
        encoding="utf-8",
    )

    assert _selected_dates(manifest, "2026-07-02", "2026-07-09") == [
        "2026-07-03"
    ]


def test_legacy_css_migration_is_dry_run_by_default_and_idempotent(tmp_path):
    page = tmp_path / "daily" / "2026-07-01.html"
    page.parent.mkdir(parents=True)
    original = (
        "<html><head><meta content=\"style-src 'unsafe-inline';\">"
        "<style>\n:root { --paper: white; }\n"
        ".item { color: black; }</style></head><body></body></html>"
    )
    page.write_text(original, encoding="utf-8")

    assert migrate_legacy_css(tmp_path) == [page]
    assert page.read_text(encoding="utf-8") == original

    assert migrate_legacy_css(tmp_path, write=True) == [page]
    migrated = page.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="../assets/site/horizon.css">' in migrated
    assert "<style>" not in migrated
    assert "style-src 'self' 'unsafe-inline';" in migrated
    assert (tmp_path / "assets" / "site" / "horizon.css").is_file()
    assert migrate_legacy_css(tmp_path, write=True) == []


def test_rebuild_workflow_is_manual_dry_by_default_and_has_no_pipeline_side_effects():
    workflow = Path(".github/workflows/rebuild-daily-site.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "date_from:" in workflow and "date_to:" in workflow
    assert "default: false" in workflow
    assert "group: horizon-production-site" in workflow
    assert "scripts/rebuild_daily_site.py" in workflow
    assert "--publish" in workflow
    assert "uv run horizon" not in workflow
    assert "DEEPSEEK_API_KEY" not in workflow
    assert "EMAIL_PASSWORD" not in workflow
    assert "coscli sync" not in workflow
    assert "--delete" not in workflow

# Incremental site publication

Horizon production publishing is manifest-driven. Daily jobs restore only the
small state required to render a new release; historical HTML and media remain
in COS and are never mirrored back to the runner.

## Object ownership

- A daily release owns `daily/YYYY-MM-DD.html` and `assets/YYYY-MM-DD/*`.
- X Article detail pages and the site entry points are shared, overwrite-only
  objects. Automated cleanup cannot delete them.
- The content-library release owns `articles/*`, `papers/*`, and
  `assets/articles/*`.
- `d/*` is outside every release and remains an untouched compatibility layer.

Every cleanup target must appear in the previous release manifest and remain
inside the current release's path allowlist. Publishing never uses a recursive
bucket-root delete.

## Required GitHub configuration

The workflows use the existing `COS_SECRET_ID` and `COS_SECRET_KEY` secrets.
They define the public site bucket and endpoint in workflow environment values.

The workflows default `COS_STATE_BUCKET` to the dedicated private bucket
`cos://signalfeed-state-1257788828`. The repository variable remains available
as an override. Release manifests, email delivery state, and structured daily
run sources are stored there; the public site bucket never receives this state.

## Normal workflows

`daily-summary.yml` restores `site_manifest.json`, email state, and at most one
daily release manifest. It renders and uploads the current date only.

`publish-articles.yml` restores one content-library release manifest. Existing
media mappings are reused, so only new media needs to be downloaded.
On the first cutover run only, if that manifest does not yet exist, the workflow
restores the scoped `assets/articles/` prefix and builds a baseline manifest.
It never restores the daily archive or performs a bucket-root sync.

Both workflows share the `horizon-production-site` concurrency group.

## Historical rebuild

`rebuild-daily-site.yml` is manual and dry-run by default. It accepts an
inclusive UTC date range. A real rebuild must explicitly enable `publish`.
The workflow does not fetch sources, invoke AI, or send notifications; it reads
persisted `data/runs/YYYY-MM-DD.json` equivalents from the state bucket and
reuses existing media objects.

Dates published before structured run persistence may not be rebuildable. They
can be skipped explicitly with `allow_missing_sources`.

## Legacy shared-CSS migration

New pages reference `assets/site/horizon.css`, so style-only changes apply
without HTML re-rendering. Legacy self-contained pages can be inspected and
migrated after downloading their HTML into a temporary site tree:

```bash
uv run python scripts/migrate_legacy_css.py --site-root /path/to/site
uv run python scripts/migrate_legacy_css.py --site-root /path/to/site --write
```

The command is dry-run by default and never uploads or deletes remote objects.

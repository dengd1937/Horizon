"""Re-render historical daily pages from persisted structured run sources."""

import argparse
import json
import os
from datetime import date as date_cls
from pathlib import Path

from src.render.publication import (
    CosCliPublisher,
    CosCliRestorer,
    PublicationError,
    build_daily_release_manifest,
    load_previous_manifest,
    local_release_manifest_path,
    pending_manifest_path,
    release_manifest_key,
    validate_site_manifest,
)
from src.render.site import SiteRenderer
from src.storage.manager import StorageManager


def _settings() -> tuple[str, str, str]:
    site_bucket = os.environ.get("COS_SITE_BUCKET", "")
    state_bucket = os.environ.get("COS_STATE_BUCKET") or site_bucket
    endpoint = os.environ.get("COS_ENDPOINT", "")
    if not site_bucket or not endpoint:
        raise PublicationError("COS_SITE_BUCKET and COS_ENDPOINT are required")
    return site_bucket, state_bucket, endpoint


def _selected_dates(manifest_path: Path, start: str, end: str) -> list[str]:
    start_date = date_cls.fromisoformat(start)
    end_date = date_cls.fromisoformat(end or start)
    if end_date < start_date:
        raise PublicationError("--to must not be earlier than --from")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"cannot read site manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise PublicationError("site manifest must be a JSON object")
    return [
        value
        for value in sorted(manifest)
        if start_date <= date_cls.fromisoformat(value) <= end_date
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", default="")
    parser.add_argument("--site-root", type=Path, default=Path("data/site"))
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--coscli", default="coscli")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Write the rebuilt pages to COS; the default is a dry-run",
    )
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="Skip legacy dates that do not have a persisted run JSON",
    )
    args = parser.parse_args()

    site_bucket, state_bucket, endpoint = _settings()
    restorer = CosCliRestorer(
        site_bucket=site_bucket,
        state_bucket=state_bucket,
        endpoint=endpoint,
        coscli=args.coscli,
    )
    restorer.restore(
        bucket=site_bucket,
        key="site_manifest.json",
        destination=args.site_root / "site_manifest.json",
        required=True,
    )
    validate_site_manifest(args.site_root / "site_manifest.json")
    dates = _selected_dates(
        args.site_root / "site_manifest.json", args.date_from, args.date_to
    )
    if not dates:
        raise PublicationError("no published daily dates matched the requested range")

    storage = StorageManager(str(args.data_root))
    config = storage.load_config()
    renderer = SiteRenderer(config.site)
    publisher = CosCliPublisher(
        site_bucket=site_bucket,
        state_bucket=state_bucket,
        endpoint=endpoint,
        coscli=args.coscli,
    )
    rebuilt = 0
    skipped = 0

    for release in dates:
        source_path = storage.runs_dir / f"{release}.json"
        source_found = restorer.restore(
            bucket=state_bucket,
            key=f".horizon-state/runs/{release}.json",
            destination=source_path,
            required=not args.allow_missing_sources,
        )
        if not source_found:
            print(f"Skip {release}: structured source is unavailable")
            skipped += 1
            continue

        restorer.restore(
            bucket=state_bucket,
            key=release_manifest_key("daily", release),
            destination=local_release_manifest_path(
                args.site_root, "daily", release
            ),
            required=True,
        )
        loaded = storage.load_run_items(release)
        if loaded is None:
            raise PublicationError(f"restored run source is unreadable: {release}")
        items, meta = loaded
        total_fetched = int(meta.get("total_fetched", len(items)))
        previous = load_previous_manifest(args.site_root, "daily", release)
        pages = renderer.render_daily(items, release, total_fetched)
        current = build_daily_release_manifest(
            args.site_root,
            release,
            pages,
            items,
            previous=previous,
        )
        current.write(pending_manifest_path(args.site_root, "daily"))
        plan = publisher.publish(
            site_root=args.site_root,
            current=current,
            previous=previous,
            source_path=source_path,
            dry_run=not args.publish,
        )
        mode = "Publish" if args.publish else "Dry-run"
        print(
            f"{mode} {release}: {len(plan.uploads)} upload(s), "
            f"{len(plan.unchanged)} unchanged, {len(plan.deletes)} delete(s)"
        )
        rebuilt += 1

    print(f"Historical rebuild complete: {rebuilt} rebuilt, {skipped} skipped")


if __name__ == "__main__":
    main()

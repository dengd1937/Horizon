"""Restore only the remote state required for an incremental site render."""

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from src.render.publication import (
    CosCliRestorer,
    PublicationError,
    local_release_manifest_path,
    release_manifest_key,
    validate_site_manifest,
)


def _settings() -> tuple[str, str, str]:
    site_bucket = os.environ.get("COS_SITE_BUCKET", "")
    state_bucket = os.environ.get("COS_STATE_BUCKET") or site_bucket
    endpoint = os.environ.get("COS_ENDPOINT", "")
    if not site_bucket or not endpoint:
        raise PublicationError("COS_SITE_BUCKET and COS_ENDPOINT are required")
    return site_bucket, state_bucket, endpoint


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("daily", "libraries"))
    parser.add_argument("--date", help="UTC daily release date (YYYY-MM-DD)")
    parser.add_argument("--site-root", type=Path, default=Path("data/site"))
    parser.add_argument("--coscli", default="coscli")
    parser.add_argument(
        "--allow-bootstrap",
        action="store_true",
        help="Allow an absent site_manifest.json for a brand-new site",
    )
    args = parser.parse_args()

    release = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if args.kind == "libraries":
        release = "current"

    site_bucket, state_bucket, endpoint = _settings()
    restorer = CosCliRestorer(
        site_bucket=site_bucket,
        state_bucket=state_bucket,
        endpoint=endpoint,
        coscli=args.coscli,
    )

    if args.kind == "daily":
        restored = restorer.restore(
            bucket=site_bucket,
            key="site_manifest.json",
            destination=args.site_root / "site_manifest.json",
            required=not args.allow_bootstrap,
        )
        if restored:
            validate_site_manifest(args.site_root / "site_manifest.json")
        print(f"site manifest: {'restored' if restored else 'bootstrap'}")
        email_state = restorer.restore(
            bucket=state_bucket,
            key=".horizon-state/email_delivery_state.json",
            destination=args.site_root.parent / "email_delivery_state.json",
            required=False,
        )
        print(f"email state: {'restored' if email_state else 'absent'}")

    previous = restorer.restore(
        bucket=state_bucket,
        key=release_manifest_key(args.kind, release),
        destination=local_release_manifest_path(
            args.site_root, args.kind, release
        ),
        required=False,
    )
    print(f"previous {args.kind} release: {'restored' if previous else 'absent'}")


if __name__ == "__main__":
    main()

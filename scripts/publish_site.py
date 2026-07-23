"""Publish a staged Horizon release with exact manifest-driven COS writes."""

import argparse
import os
from pathlib import Path

from src.render.publication import (
    CosCliPublisher,
    PublicationError,
    ReleaseManifest,
    load_previous_manifest,
    pending_manifest_path,
    read_noop_marker,
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
    parser.add_argument("--site-root", type=Path, default=Path("data/site"))
    parser.add_argument("--coscli", default="coscli")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pending = pending_manifest_path(args.site_root, args.kind)
    if not pending.exists():
        marker = read_noop_marker(args.site_root, args.kind)
        if marker is None:
            raise PublicationError(
                f"pending {args.kind} release is missing and no valid no-op marker exists"
            )
        print(
            f"No-op {marker['kind']}/{marker['release']}: {marker['reason']}"
        )
        return
    current = ReleaseManifest.read(pending)
    previous = load_previous_manifest(
        args.site_root, current.kind, current.release
    )
    site_bucket, state_bucket, endpoint = _settings()
    publisher = CosCliPublisher(
        site_bucket=site_bucket,
        state_bucket=state_bucket,
        endpoint=endpoint,
        coscli=args.coscli,
    )
    source = (
        args.site_root.parent / "runs" / f"{current.release}.json"
        if current.kind == "daily"
        else None
    )
    plan = publisher.publish(
        site_root=args.site_root,
        current=current,
        previous=previous,
        source_path=source,
        dry_run=args.dry_run,
    )
    mode = "Dry-run" if args.dry_run else "Published"
    print(
        f"{mode} {current.kind}/{current.release}: "
        f"{len(plan.uploads)} upload(s), "
        f"{len(plan.unchanged)} unchanged, {len(plan.deletes)} delete(s)."
    )
    for key in plan.deletes:
        print(f"  delete {key}")


if __name__ == "__main__":
    main()

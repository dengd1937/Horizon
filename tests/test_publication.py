"""Safety and incremental behavior for manifest-driven site publication."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models import ContentItem, SourceType
from src.render.publication import (
    CosCliRestorer,
    CosCliPublisher,
    PublicationError,
    ReleaseManifest,
    build_daily_release_manifest,
    build_libraries_release_manifest,
    build_publication_plan,
    pending_manifest_path,
    read_noop_marker,
    sha256_file,
    validate_site_manifest,
    write_noop_marker,
)


HASH_A = "a" * 64
HASH_B = "b" * 64


def _item(asset_map=None) -> ContentItem:
    return ContentItem(
        id="twitter:tweet:1",
        source_type=SourceType.TWITTER,
        title="title",
        url="https://x.com/user/status/1",
        published_at=datetime.now(timezone.utc),
        metadata={"asset_map": asset_map or {}},
    )


def _write(root: Path, key: str, content: str = "content") -> Path:
    path = root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_manifest_rejects_traversal_and_cross_release_ownership():
    with pytest.raises(PublicationError, match="unsafe object key"):
        ReleaseManifest(
            kind="daily",
            release="2026-07-22",
            objects={"../index.html": HASH_A},
            shared_objects={},
            media={},
        )

    with pytest.raises(PublicationError, match="cannot own"):
        ReleaseManifest(
            kind="daily",
            release="2026-07-22",
            objects={"assets/2026-07-21/old.jpg": HASH_A},
            shared_objects={},
            media={},
        )


def test_site_manifest_validation_fails_closed_on_corrupt_archive_state(tmp_path):
    manifest = tmp_path / "site_manifest.json"
    manifest.write_text(
        '{"2026-07-22":{"count":-1,"top":[]}}', encoding="utf-8"
    )
    with pytest.raises(PublicationError, match="count is invalid"):
        validate_site_manifest(manifest)

def test_plan_deletes_only_previous_owned_objects_and_never_shared_objects():
    previous = ReleaseManifest(
        kind="daily",
        release="2026-07-22",
        objects={
            "daily/2026-07-22.html": HASH_A,
            "assets/2026-07-22/old.jpg": HASH_A,
        },
        shared_objects={
            "index.html": HASH_A,
            "daily/article-123.html": HASH_A,
        },
        media={"https://media.example/old.jpg": "assets/2026-07-22/old.jpg"},
    )
    current = ReleaseManifest(
        kind="daily",
        release="2026-07-22",
        objects={"daily/2026-07-22.html": HASH_B},
        shared_objects={"index.html": HASH_B},
        media={},
    )

    plan = build_publication_plan(current, previous)

    assert plan.deletes == ("assets/2026-07-22/old.jpg",)
    assert "daily/article-123.html" not in plan.deletes
    assert plan.uploads == ("daily/2026-07-22.html", "index.html")


def test_daily_manifest_reuses_known_remote_media_without_local_download(tmp_path):
    release = "2026-07-22"
    media_key = f"assets/{release}/known.jpg"
    previous = ReleaseManifest(
        kind="daily",
        release=release,
        objects={media_key: HASH_A},
        shared_objects={},
        media={"https://media.example/known.jpg": media_key},
    )
    paths = [
        _write(tmp_path, f"daily/{release}.html"),
        _write(tmp_path, "site_manifest.json", "{}"),
        _write(tmp_path, "daily/index.html"),
        _write(tmp_path, "index.html"),
        _write(tmp_path, "assets/site/horizon.css"),
    ]

    manifest = build_daily_release_manifest(
        tmp_path,
        release,
        paths,
        [_item({"https://media.example/known.jpg": media_key})],
        previous=previous,
    )

    assert manifest.objects[media_key] == HASH_A
    assert not (tmp_path / media_key).exists()
    assert manifest.media == {"https://media.example/known.jpg": (media_key,)}


def test_library_manifest_preserves_duplicate_url_in_multiple_article_paths(tmp_path):
    url = "https://media.example/shared.jpg"
    first = "assets/articles/first/shared.jpg"
    second = "assets/articles/second/shared.jpg"
    paths = [
        _write(tmp_path, "articles/index.html"),
        _write(tmp_path, "papers/index.html"),
        _write(tmp_path, "assets/site/horizon.css"),
        _write(tmp_path, first),
        _write(tmp_path, second),
    ]

    manifest = build_libraries_release_manifest(
        tmp_path,
        paths,
        {url: {first, second}},
    )

    assert manifest.media[url] == (first, second)
    assert first in manifest.objects and second in manifest.objects
    restored = ReleaseManifest.from_dict(manifest.to_dict())
    assert restored.media[url] == (first, second)


def test_publisher_uploads_source_before_entry_points_and_deletes_exact_keys(
    tmp_path, monkeypatch
):
    release = "2026-07-22"
    current_paths = {
        f"daily/{release}.html": "digest",
        "site_manifest.json": "manifest",
        "daily/index.html": "archive",
        "index.html": "root",
        "assets/site/horizon.css": "css",
    }
    objects = {f"daily/{release}.html": ""}
    shared = {}
    for key, content in current_paths.items():
        path = _write(tmp_path, key, content)
        digest = sha256_file(path)
        if key == f"daily/{release}.html":
            objects[key] = digest
        else:
            shared[key] = digest
    current = ReleaseManifest(
        kind="daily",
        release=release,
        objects=objects,
        shared_objects=shared,
        media={},
    )
    previous = ReleaseManifest(
        kind="daily",
        release=release,
        objects={
            f"daily/{release}.html": HASH_A,
            f"assets/{release}/orphan.jpg": HASH_A,
        },
        shared_objects={},
        media={
            "https://media.example/orphan.jpg": f"assets/{release}/orphan.jpg"
        },
    )
    current.write(pending_manifest_path(tmp_path, "daily"))
    source = _write(tmp_path.parent / "runs", f"{release}.json", "{}")
    commands: list[list[str]] = []

    def runner(command):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setenv("COS_SECRET_ID", "secret-id")
    monkeypatch.setenv("COS_SECRET_KEY", "secret-key")
    publisher = CosCliPublisher(
        site_bucket="cos://site-bucket",
        state_bucket="cos://state-bucket",
        endpoint="cos.example.test",
        runner=runner,
    )

    plan = publisher.publish(
        site_root=tmp_path,
        current=current,
        previous=previous,
        source_path=source,
    )

    assert plan.deletes == (f"assets/{release}/orphan.jpg",)
    targets = [next((part for part in command if part.startswith("cos://")), "") for command in commands]
    source_index = targets.index(
        f"cos://state-bucket/.horizon-state/runs/{release}.json"
    )
    manifest_index = targets.index("cos://site-bucket/site_manifest.json")
    root_index = targets.index("cos://site-bucket/index.html")
    assert source_index < manifest_index < root_index

    delete = next(command for command in commands if command[1] == "rm")
    assert delete[2] == f"cos://site-bucket/assets/{release}/orphan.jpg"
    assert "--force" in delete
    assert "--recursive" not in delete and "-r" not in delete
    assert all("--init-skip=true" in command for command in commands)
    assert all("--log-path" in command for command in commands)
    assert all("--disable-log" not in command for command in commands)


def test_noop_marker_is_explicit_and_validated(tmp_path):
    write_noop_marker(tmp_path, "daily", "2026-07-22", "no-content")
    assert read_noop_marker(tmp_path, "daily") == {
        "kind": "daily",
        "release": "2026-07-22",
        "reason": "no-content",
    }


def test_optional_restore_ignores_only_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("COS_SECRET_ID", "secret-id")
    monkeypatch.setenv("COS_SECRET_KEY", "secret-key")

    def missing(command):
        return subprocess.CompletedProcess(command, 1, "", "NoSuchKey")

    restorer = CosCliRestorer(
        site_bucket="cos://site-bucket",
        state_bucket="cos://state-bucket",
        endpoint="cos.example.test",
        runner=missing,
    )
    assert not restorer.restore(
        bucket="cos://state-bucket",
        key=".horizon-state/releases/missing.json",
        destination=tmp_path / "missing.json",
        required=False,
    )

    def denied(command):
        return subprocess.CompletedProcess(command, 1, "", "AccessDenied")

    restorer.runner = denied
    with pytest.raises(PublicationError, match="AccessDenied"):
        restorer.restore(
            bucket="cos://state-bucket",
            key=".horizon-state/releases/missing.json",
            destination=tmp_path / "missing.json",
            required=False,
        )

"""Manifest-driven publication contracts for the static reading site.

The renderer writes into a clean staging tree.  Release manifests record the
objects owned by one logical release, allowing deployment to upload only
changed files and to delete only objects that a previous manifest explicitly
owned.  Shared entry points are never eligible for automatic deletion.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, Optional, Sequence, Union

from ..models import ContentItem


RELEASE_SCHEMA_VERSION = 1
RENDERER_VERSION = 2
DATA_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DAILY_ARTICLE_RE = re.compile(r"^daily/article-[A-Za-z0-9_-]+\.html$")


class PublicationError(ValueError):
    """Raised when a release manifest or publication plan is unsafe."""


def _safe_key(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise PublicationError("object keys must be non-empty strings")
    key = PurePosixPath(value)
    if key.is_absolute() or ".." in key.parts or value.startswith("./"):
        raise PublicationError(f"unsafe object key: {value!r}")
    normalized = key.as_posix()
    if normalized != value or normalized in {".", ""}:
        raise PublicationError(f"object key is not normalized: {value!r}")
    return normalized


def _validate_hash(value: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise PublicationError(f"invalid sha256 digest: {value!r}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_site_manifest(path: Path) -> dict[str, dict]:
    """Validate the compact canonical archive state before it is overwritten."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"cannot read site manifest {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PublicationError("site manifest must be a JSON object")
    for release, info in raw.items():
        try:
            date_cls.fromisoformat(release)
        except (TypeError, ValueError) as exc:
            raise PublicationError(
                f"site manifest contains an invalid date: {release!r}"
            ) from exc
        if not isinstance(info, dict):
            raise PublicationError(f"site manifest entry must be an object: {release}")
        count = info.get("count")
        top = info.get("top")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise PublicationError(f"site manifest count is invalid: {release}")
        if not isinstance(top, list) or any(not isinstance(value, str) for value in top):
            raise PublicationError(f"site manifest top titles are invalid: {release}")
    return raw


@dataclass(frozen=True)
class ReleaseManifest:
    kind: str
    release: str
    objects: dict[str, str]
    shared_objects: dict[str, str]
    media: dict[str, tuple[str, ...]]
    schema_version: int = RELEASE_SCHEMA_VERSION
    renderer_version: int = RENDERER_VERSION
    data_schema_version: int = DATA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RELEASE_SCHEMA_VERSION:
            raise PublicationError(
                f"unsupported release schema version: {self.schema_version}"
            )
        if self.data_schema_version != DATA_SCHEMA_VERSION:
            raise PublicationError(
                f"unsupported data schema version: {self.data_schema_version}"
            )
        if self.kind not in {"daily", "libraries"}:
            raise PublicationError(f"unsupported release kind: {self.kind!r}")
        if self.kind == "daily":
            try:
                date_cls.fromisoformat(self.release)
            except (TypeError, ValueError) as exc:
                raise PublicationError("daily release must be an ISO date") from exc
        elif self.release != "current":
            raise PublicationError("libraries release must be 'current'")

        for key, digest in self.objects.items():
            self._validate_owned_key(_safe_key(key))
            _validate_hash(digest)
        for key, digest in self.shared_objects.items():
            self._validate_shared_key(_safe_key(key))
            _validate_hash(digest)
        normalized_media: dict[str, tuple[str, ...]] = {}
        for url, raw_keys in self.media.items():
            if not isinstance(url, str) or not url.startswith("https://"):
                raise PublicationError(f"invalid media URL: {url!r}")
            keys = (raw_keys,) if isinstance(raw_keys, str) else tuple(raw_keys)
            if not keys:
                raise PublicationError(f"media URL has no object keys: {url}")
            normalized_keys = tuple(sorted({_safe_key(key) for key in keys}))
            for normalized in normalized_keys:
                if normalized not in self.objects:
                    raise PublicationError(
                        f"media object is not owned by this release: {normalized}"
                    )
            normalized_media[url] = normalized_keys
        object.__setattr__(self, "media", normalized_media)

    def _validate_owned_key(self, key: str) -> None:
        if self.kind == "daily":
            allowed = key == f"daily/{self.release}.html" or key.startswith(
                f"assets/{self.release}/"
            )
        else:
            allowed = key.startswith(("articles/", "papers/", "assets/articles/"))
        if not allowed:
            raise PublicationError(
                f"{self.kind} release cannot own object key: {key}"
            )

    def _validate_shared_key(self, key: str) -> None:
        if self.kind == "daily":
            allowed = key in {
                "assets/site/horizon.css",
                "daily/index.html",
                "index.html",
                "site_manifest.json",
            } or bool(_DAILY_ARTICLE_RE.fullmatch(key))
        else:
            allowed = key == "assets/site/horizon.css"
        if not allowed:
            raise PublicationError(
                f"{self.kind} release cannot update shared object key: {key}"
            )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "renderer_version": self.renderer_version,
            "data_schema_version": self.data_schema_version,
            "kind": self.kind,
            "release": self.release,
            "objects": dict(sorted(self.objects.items())),
            "shared_objects": dict(sorted(self.shared_objects.items())),
            "media": {
                url: list(keys) for url, keys in sorted(self.media.items())
            },
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def from_dict(cls, raw: Mapping) -> "ReleaseManifest":
        if not isinstance(raw, Mapping):
            raise PublicationError("release manifest must be a JSON object")
        try:
            return cls(
                schema_version=raw.get("schema_version"),
                renderer_version=int(raw.get("renderer_version", 0)),
                data_schema_version=int(
                    raw.get("data_schema_version", DATA_SCHEMA_VERSION)
                ),
                kind=raw.get("kind"),
                release=raw.get("release"),
                objects=dict(raw.get("objects") or {}),
                shared_objects=dict(raw.get("shared_objects") or {}),
                media=dict(raw.get("media") or {}),
            )
        except (TypeError, ValueError) as exc:
            raise PublicationError(f"invalid release manifest: {exc}") from exc

    @classmethod
    def read(cls, path: Path) -> "ReleaseManifest":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PublicationError(f"cannot read release manifest {path}: {exc}") from exc
        return cls.from_dict(raw)


def release_manifest_key(kind: str, release: str) -> str:
    if kind == "daily":
        date_cls.fromisoformat(release)
        return f".horizon-state/releases/daily/{release}.json"
    if kind == "libraries" and release == "current":
        return ".horizon-state/releases/libraries.json"
    raise PublicationError(f"invalid release identity: {kind}/{release}")


def local_release_manifest_path(site_root: Path, kind: str, release: str) -> Path:
    return site_root / release_manifest_key(kind, release)


def pending_manifest_path(site_root: Path, kind: str) -> Path:
    if kind not in {"daily", "libraries"}:
        raise PublicationError(f"invalid pending manifest kind: {kind}")
    return site_root / ".horizon-state" / "pending" / f"{kind}.json"


def noop_marker_path(site_root: Path, kind: str) -> Path:
    if kind not in {"daily", "libraries"}:
        raise PublicationError(f"invalid no-op marker kind: {kind}")
    return site_root / ".horizon-state" / "pending" / f"{kind}.noop.json"


def write_noop_marker(site_root: Path, kind: str, release: str, reason: str) -> Path:
    if kind != "daily":
        raise PublicationError("only daily releases support no-op markers")
    date_cls.fromisoformat(release)
    if reason != "no-content":
        raise PublicationError(f"unsupported no-op reason: {reason!r}")
    path = noop_marker_path(site_root, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"kind": kind, "release": release, "reason": reason},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def read_noop_marker(site_root: Path, kind: str) -> Optional[dict[str, str]]:
    path = noop_marker_path(site_root, kind)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"cannot read no-op marker: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("kind") != kind:
        raise PublicationError("invalid no-op marker identity")
    release = raw.get("release")
    reason = raw.get("reason")
    if kind == "daily":
        try:
            date_cls.fromisoformat(release)
        except (TypeError, ValueError) as exc:
            raise PublicationError("invalid no-op release date") from exc
    if reason != "no-content":
        raise PublicationError("invalid no-op reason")
    return {"kind": kind, "release": release, "reason": reason}


def load_previous_manifest(
    site_root: Path, kind: str, release: str
) -> Optional[ReleaseManifest]:
    path = local_release_manifest_path(site_root, kind, release)
    if not path.exists():
        return None
    manifest = ReleaseManifest.read(path)
    if manifest.kind != kind or manifest.release != release:
        raise PublicationError(
            f"release manifest identity mismatch: expected {kind}/{release}"
        )
    return manifest


def _relative_key(site_root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(site_root.resolve())
    except ValueError as exc:
        raise PublicationError(f"artifact is outside site root: {path}") from exc
    return _safe_key(relative.as_posix())


def _hash_keys(
    site_root: Path,
    keys: Iterable[str],
    previous: Optional[ReleaseManifest],
) -> dict[str, str]:
    result: dict[str, str] = {}
    previous_objects = previous.objects if previous is not None else {}
    previous_shared = previous.shared_objects if previous is not None else {}
    for raw_key in sorted(set(keys)):
        key = _safe_key(raw_key)
        path = site_root / key
        if path.is_file():
            result[key] = sha256_file(path)
        elif key in previous_objects:
            result[key] = previous_objects[key]
        elif key in previous_shared:
            result[key] = previous_shared[key]
        else:
            raise PublicationError(f"release artifact is missing locally: {key}")
    return result


def build_daily_release_manifest(
    site_root: Path,
    release: str,
    rendered_paths: Iterable[Path],
    items: Iterable[ContentItem],
    previous: Optional[ReleaseManifest] = None,
) -> ReleaseManifest:
    """Build the pending daily manifest from rendered pages and asset maps."""
    date_cls.fromisoformat(release)
    owned: set[str] = set()
    shared: set[str] = set()
    media_sets: dict[str, set[str]] = {}

    for path in rendered_paths:
        key = _relative_key(site_root, path)
        if key == f"daily/{release}.html" or key.startswith(f"assets/{release}/"):
            owned.add(key)
        elif key in {
            "assets/site/horizon.css",
            "daily/index.html",
            "index.html",
            "site_manifest.json",
        } or _DAILY_ARTICLE_RE.fullmatch(key):
            shared.add(key)

    for item in items:
        for url, raw_key in (item.metadata.get("asset_map") or {}).items():
            key = _safe_key(str(raw_key))
            if key.startswith(f"assets/{release}/"):
                owned.add(key)
                media_sets.setdefault(str(url), set()).add(key)

    manifest = ReleaseManifest(
        kind="daily",
        release=release,
        objects=_hash_keys(site_root, owned, previous),
        shared_objects=_hash_keys(site_root, shared, previous),
        media={url: tuple(sorted(keys)) for url, keys in media_sets.items()},
    )
    return manifest


def build_libraries_release_manifest(
    site_root: Path,
    rendered_paths: Iterable[Path],
    media_by_url: Mapping[str, Union[str, Iterable[str]]],
    previous: Optional[ReleaseManifest] = None,
) -> ReleaseManifest:
    """Build the pending content-library manifest."""
    owned: set[str] = set()
    shared: set[str] = set()
    media: dict[str, tuple[str, ...]] = {}
    for path in rendered_paths:
        key = _relative_key(site_root, path)
        if key == "assets/site/horizon.css":
            shared.add(key)
        elif key.startswith(("articles/", "papers/", "assets/articles/")):
            owned.add(key)
    for url, raw_keys in media_by_url.items():
        keys = (raw_keys,) if isinstance(raw_keys, str) else tuple(raw_keys)
        normalized_keys: list[str] = []
        for raw_key in keys:
            key = _safe_key(raw_key)
            if not key.startswith("assets/articles/"):
                raise PublicationError(f"invalid content-library media key: {key}")
            owned.add(key)
            normalized_keys.append(key)
        media[url] = tuple(sorted(set(normalized_keys)))
    return ReleaseManifest(
        kind="libraries",
        release="current",
        objects=_hash_keys(site_root, owned, previous),
        shared_objects=_hash_keys(site_root, shared, previous),
        media=media,
    )


@dataclass(frozen=True)
class PublicationPlan:
    uploads: tuple[str, ...]
    unchanged: tuple[str, ...]
    deletes: tuple[str, ...]


def build_publication_plan(
    current: ReleaseManifest,
    previous: Optional[ReleaseManifest],
) -> PublicationPlan:
    """Compare release manifests without granting deletion beyond old ownership."""
    if previous is not None and (
        previous.kind != current.kind or previous.release != current.release
    ):
        raise PublicationError("cannot compare manifests from different releases")

    previous_objects = previous.objects if previous is not None else {}
    previous_shared = previous.shared_objects if previous is not None else {}
    uploads: list[str] = []
    unchanged: list[str] = []

    for key, digest in [*current.objects.items(), *current.shared_objects.items()]:
        old_digest = previous_objects.get(key) or previous_shared.get(key)
        if old_digest == digest:
            unchanged.append(key)
        else:
            uploads.append(key)

    deletes = sorted(set(previous_objects) - set(current.objects))
    # Re-validate every destructive target through the current release scope.
    for key in deletes:
        current._validate_owned_key(_safe_key(key))

    return PublicationPlan(
        uploads=tuple(sorted(uploads)),
        unchanged=tuple(sorted(unchanged)),
        deletes=tuple(deletes),
    )


def _bucket_uri(value: str) -> str:
    bucket = value.rstrip("/")
    if not bucket.startswith("cos://") or bucket == "cos://":
        raise PublicationError(f"invalid COS bucket URI: {value!r}")
    return bucket


def _remote_uri(bucket: str, key: str) -> str:
    return f"{_bucket_uri(bucket)}/{_safe_key(key)}"


def _upload_priority(key: str) -> tuple[int, str]:
    if key == "assets/site/horizon.css":
        return (0, key)
    if key.startswith("assets/"):
        return (10, key)
    if key.endswith("index.html"):
        return (80 if key != "index.html" else 100, key)
    if key == "site_manifest.json":
        return (70, key)
    return (40, key)


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_command_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


class CosCliPublisher:
    """Execute a validated publication plan with exact COS object operations."""

    def __init__(
        self,
        *,
        site_bucket: str,
        state_bucket: str,
        endpoint: str,
        coscli: str = "coscli",
        runner: CommandRunner = _default_command_runner,
    ) -> None:
        self.site_bucket = _bucket_uri(site_bucket)
        self.state_bucket = _bucket_uri(state_bucket)
        if not endpoint or any(char.isspace() for char in endpoint):
            raise PublicationError("invalid COS endpoint")
        self.endpoint = endpoint
        self.coscli = coscli
        self.runner = runner
        self.secret_id = os.environ.get("COS_SECRET_ID", "")
        self.secret_key = os.environ.get("COS_SECRET_KEY", "")
        if not self.secret_id or not self.secret_key:
            raise PublicationError("COS_SECRET_ID and COS_SECRET_KEY are required")

    def _common(self) -> list[str]:
        return [
            "-i",
            self.secret_id,
            "-k",
            self.secret_key,
            "-e",
            self.endpoint,
            "--init-skip=true",
            "--log-path",
            str(Path(tempfile.gettempdir()) / "horizon-coscli.log"),
            "--process-log=false",
            "--fail-output=false",
        ]

    def _run(self, command: Sequence[str], *, action: str) -> None:
        result = self.runner(command)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise PublicationError(f"COS {action} failed: {detail[-500:]}")

    def _upload(
        self, local: Path, bucket: str, key: str, *, private: bool = False
    ) -> None:
        if not local.is_file():
            raise PublicationError(f"upload source does not exist: {local}")
        command = [
            self.coscli,
            "cp",
            str(local),
            _remote_uri(bucket, key),
            *self._common(),
        ]
        if private:
            command.extend(["--acl", "private"])
        if key == "assets/site/horizon.css":
            command.extend(["--meta", "Cache-Control:no-cache"])
        self._run(command, action=f"upload {key}")

    def _delete(self, key: str) -> None:
        self._run(
            [
                self.coscli,
                "rm",
                _remote_uri(self.site_bucket, key),
                "--force",
                *self._common(),
            ],
            action=f"delete {key}",
        )

    def publish(
        self,
        *,
        site_root: Path,
        current: ReleaseManifest,
        previous: Optional[ReleaseManifest],
        source_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> PublicationPlan:
        plan = build_publication_plan(current, previous)
        if dry_run:
            return plan

        ordered_uploads = sorted(plan.uploads, key=_upload_priority)
        precommit = [key for key in ordered_uploads if _upload_priority(key)[0] < 70]
        commit = [key for key in ordered_uploads if _upload_priority(key)[0] >= 70]
        for key in precommit:
            self._upload(site_root / key, self.site_bucket, key)

        if current.kind == "daily":
            if source_path is None or not source_path.is_file():
                raise PublicationError(
                    "daily publication requires its structured run source"
                )
            source_key = f".horizon-state/runs/{current.release}.json"
            self._upload(source_path, self.state_bucket, source_key, private=True)

        for key in commit:
            self._upload(site_root / key, self.site_bucket, key)

        # Deletes happen only after all replacement objects and shared entry
        # points have uploaded successfully.  They are exact, non-recursive keys.
        for key in plan.deletes:
            self._delete(key)

        pending = pending_manifest_path(site_root, current.kind)
        if not pending.is_file():
            current.write(pending)
        self._upload(
            pending,
            self.state_bucket,
            release_manifest_key(current.kind, current.release),
            private=True,
        )
        return plan


_NOT_FOUND_MARKERS = (
    "nosuchkey",
    "status code: 404",
    "statuscode=404",
    "specified key does not exist",
    "object not exist",
)


class CosCliRestorer:
    """Restore only the small state objects required before rendering."""

    def __init__(
        self,
        *,
        site_bucket: str,
        state_bucket: str,
        endpoint: str,
        coscli: str = "coscli",
        runner: CommandRunner = _default_command_runner,
    ) -> None:
        self.site_bucket = _bucket_uri(site_bucket)
        self.state_bucket = _bucket_uri(state_bucket)
        self.endpoint = endpoint
        self.coscli = coscli
        self.runner = runner
        self.secret_id = os.environ.get("COS_SECRET_ID", "")
        self.secret_key = os.environ.get("COS_SECRET_KEY", "")
        if not self.secret_id or not self.secret_key:
            raise PublicationError("COS_SECRET_ID and COS_SECRET_KEY are required")

    def _common(self) -> list[str]:
        return [
            "-i",
            self.secret_id,
            "-k",
            self.secret_key,
            "-e",
            self.endpoint,
            "--init-skip=true",
            "--log-path",
            str(Path(tempfile.gettempdir()) / "horizon-coscli.log"),
            "--process-log=false",
            "--fail-output=false",
        ]

    def restore(
        self,
        *,
        bucket: str,
        key: str,
        destination: Path,
        required: bool,
    ) -> bool:
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = self.runner(
            [
                self.coscli,
                "cp",
                _remote_uri(bucket, key),
                str(destination),
                *self._common(),
            ]
        )
        if result.returncode == 0:
            return True
        detail = (result.stderr or result.stdout or "").strip()
        missing = any(marker in detail.lower() for marker in _NOT_FOUND_MARKERS)
        if not required and missing:
            destination.unlink(missing_ok=True)
            return False
        raise PublicationError(f"COS restore {key} failed: {detail[-500:]}")

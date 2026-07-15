"""Bounded execution and quality checks for the external baoyu reader."""

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

import frontmatter


class FetchError(RuntimeError):
    """Raised when external URL capture fails or yields unusable output."""


@dataclass(frozen=True)
class FetchResult:
    path: Path
    body_md: str
    metadata: dict[str, Any]
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "body_chars": len(self.body_md),
            "metadata": self.metadata,
            "sha256": self.sha256,
        }


_ERROR_PAGE_RE = re.compile(
    r"\b(captcha|access denied|verify (?:that )?you are human|sign in to continue|"
    r"login required|page not found|service unavailable)\b",
    re.IGNORECASE,
)


def load_reader_command(path: Path) -> list[str]:
    """Load the already-resolved baoyu reader command as a JSON string array."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FetchError(f"cannot read reader command {path}: {exc}") from exc
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise FetchError("reader command must be a non-empty JSON array of strings")
    return value


def validate_fetch_output(path: Path, *, allow_short: bool = False) -> FetchResult:
    """Parse baoyu Markdown output and reject empty or obvious error captures."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise FetchError(f"reader did not create output: {path}") from exc
    if not payload.strip():
        raise FetchError("reader output is empty")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FetchError("reader output is not UTF-8 Markdown") from exc
    try:
        post = frontmatter.loads(text)
    except Exception as exc:
        raise FetchError(f"reader output has malformed frontmatter: {exc}") from exc
    body = (post.content or "").strip()
    if not body:
        raise FetchError("reader output has no article body")
    metadata = dict(post.metadata or {})
    raw_title = metadata.get("title")
    if not isinstance(raw_title, str) or not raw_title.strip():
        raise FetchError("reader output has no usable title metadata")
    compact = re.sub(r"\s+", " ", body)
    title = raw_title.strip()
    if _ERROR_PAGE_RE.search(f"{title}\n{compact[:2000]}"):
        raise FetchError("reader captured an error, login, or verification page")
    if not allow_short and len(compact) < 200:
        raise FetchError(
            "reader output is suspiciously short; inspect it and retry with --allow-short only after user confirmation"
        )
    return FetchResult(path, body, metadata, hashlib.sha256(payload).hexdigest())


def run_baoyu_fetch(
    reader_command: Sequence[str],
    source_url: str,
    output: Path,
    *,
    process_timeout_seconds: float = 90,
    page_timeout_ms: int = 30_000,
    allow_short: bool = False,
) -> FetchResult:
    """Run the resolved reader without a shell and validate its Markdown output."""
    parsed = urlsplit(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FetchError("source URL must be an absolute http/https URL")
    if not reader_command or any(
        not isinstance(item, str) or not item for item in reader_command
    ):
        raise FetchError("reader command must be a non-empty sequence of strings")
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    command = [
        *reader_command,
        source_url,
        "--output",
        str(output),
        "--timeout",
        str(page_timeout_ms),
    ]
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=process_timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise FetchError(f"reader executable not found: {reader_command[0]}") from exc
    except PermissionError as exc:
        raise FetchError(f"reader is not executable: {reader_command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise FetchError(
            f"reader timed out after {process_timeout_seconds:g} seconds"
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\x00", "")[:800]
        raise FetchError(
            f"reader failed with exit code {result.returncode}"
            + (f": {detail}" if detail else "")
        )
    return validate_fetch_output(output, allow_short=allow_short)

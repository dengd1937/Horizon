"""Safe Git publication primitives for curated articles."""

import difflib
import hashlib
import json
import subprocess
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Collection, Optional, Sequence

PUBLICATION_REMOTE = "origin"
PUBLICATION_BRANCH = "main"
PUBLICATION_WORKFLOW = "publish-articles.yml"


class PublicationError(RuntimeError):
    """Raised when publication safety preconditions are not met."""


@dataclass(frozen=True)
class PublicationSnapshot:
    repo_root: str
    head: str
    remote_sha: str
    remote: str = PUBLICATION_REMOTE
    branch: str = PUBLICATION_BRANCH


@dataclass(frozen=True)
class ReviewState:
    version: int
    repo_root: str
    article_path: str
    article_sha256: str
    diff_sha256: str
    base_head: str
    remote_sha: str
    remote: str
    branch: str
    commit_message: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReviewState":
        try:
            state = cls(**value)
        except TypeError as exc:
            raise PublicationError(f"invalid review state: {exc}") from exc
        if state.version != 1:
            raise PublicationError(f"unsupported review state version: {state.version}")
        return state


@dataclass(frozen=True)
class BatchReviewArticle:
    article_path: str
    article_sha256: str

    @classmethod
    def from_dict(cls, value: object) -> "BatchReviewArticle":
        if not isinstance(value, dict):
            raise PublicationError("invalid batch review article entry")
        try:
            entry = cls(**value)
        except TypeError as exc:
            raise PublicationError(f"invalid batch review article entry: {exc}") from exc
        if not entry.article_path or not entry.article_sha256:
            raise PublicationError("invalid batch review article entry")
        return entry


@dataclass(frozen=True)
class BatchReviewState:
    version: int
    repo_root: str
    articles: tuple[BatchReviewArticle, ...]
    diff_sha256: str
    base_head: str
    remote_sha: str
    remote: str
    branch: str
    commit_message: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BatchReviewState":
        raw_articles = value.get("articles")
        if not isinstance(raw_articles, list):
            raise PublicationError("batch review state must contain an article list")
        fields = {key: item for key, item in value.items() if key != "articles"}
        try:
            state = cls(
                articles=tuple(
                    BatchReviewArticle.from_dict(item) for item in raw_articles
                ),
                **fields,
            )
        except TypeError as exc:
            raise PublicationError(f"invalid batch review state: {exc}") from exc
        if state.version != 1:
            raise PublicationError(
                f"unsupported batch review state version: {state.version}"
            )
        if len(state.articles) < 2:
            raise PublicationError("batch review state must contain at least two articles")
        return state


@dataclass(frozen=True)
class CommitResult:
    commit_sha: str
    article_path: str
    commit_message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class BatchCommitResult:
    commit_sha: str
    article_paths: tuple[str, ...]
    commit_message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(
    repo: Path,
    command: Sequence[str],
    *,
    allowed_returncodes: Collection[int] = (0,),
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(command),
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise PublicationError(f"cannot run {command[0]}: {exc}") from exc
    if result.returncode not in allowed_returncodes:
        detail = (result.stderr or result.stdout).strip().replace("\x00", "")[:800]
        raise PublicationError(
            f"command failed ({result.returncode}): {' '.join(command)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def validate_horizon_workspace(repo: Path) -> Path:
    """Resolve and verify the exact Horizon Git workspace root."""
    repo = repo.expanduser().resolve()
    root = Path(
        _run(repo, ["git", "rev-parse", "--show-toplevel"]).stdout.strip()
    ).resolve()
    if root != repo:
        raise PublicationError(f"workspace must be the Git root: {root}")

    pyproject = root / "pyproject.toml"
    contract = root / "docs" / "article-frontmatter-spec.md"
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise PublicationError("workspace has no readable Horizon pyproject.toml") from exc
    if project.get("name") != "horizon" or not contract.is_file():
        raise PublicationError("workspace is not a Horizon repository")
    return root


def _fetch_publication_ref(repo: Path) -> None:
    _run(
        repo,
        [
            "git",
            "fetch",
            "--quiet",
            PUBLICATION_REMOTE,
            f"+refs/heads/{PUBLICATION_BRANCH}:refs/remotes/{PUBLICATION_REMOTE}/{PUBLICATION_BRANCH}",
        ],
    )


def _staged_paths(repo: Path) -> list[str]:
    output = _run(
        repo, ["git", "diff", "--cached", "--name-only", "-z"]
    ).stdout
    return [path for path in output.split("\x00") if path]


def _github_repo_for_publication(repo: Path) -> str:
    """Return ``owner/name`` from the fixed origin GitHub remote."""
    remote_url = _run(
        repo, ["git", "remote", "get-url", PUBLICATION_REMOTE]
    ).stdout.strip()
    prefixes = (
        "https://github.com/",
        "http://github.com/",
        "git@github.com:",
        "ssh://git@github.com/",
    )
    relative = next(
        (
            remote_url.removeprefix(prefix)
            for prefix in prefixes
            if remote_url.startswith(prefix)
        ),
        "",
    ).rstrip("/")
    relative = relative.removesuffix(".git")
    parts = relative.split("/")
    if len(parts) != 2 or any(not part for part in parts):
        raise PublicationError(
            f"{PUBLICATION_REMOTE} must be a GitHub repository URL for workflow lookup"
        )
    return "/".join(parts)


def preflight(repo: Path, *, fetch: bool = True) -> PublicationSnapshot:
    """Verify that publication can start without disturbing Git state."""
    root = validate_horizon_workspace(repo)
    branch = _run(root, ["git", "symbolic-ref", "--short", "HEAD"]).stdout.strip()
    if branch != PUBLICATION_BRANCH:
        raise PublicationError(
            f"publication requires branch {PUBLICATION_BRANCH!r}, got {branch!r}"
        )
    staged = _staged_paths(root)
    if staged:
        raise PublicationError(
            "index already contains staged changes: " + ", ".join(staged)
        )
    if fetch:
        _fetch_publication_ref(root)
    head = _run(root, ["git", "rev-parse", "HEAD"]).stdout.strip()
    remote_ref = f"refs/remotes/{PUBLICATION_REMOTE}/{PUBLICATION_BRANCH}"
    remote_sha = _run(root, ["git", "rev-parse", remote_ref]).stdout.strip()
    if head != remote_sha:
        raise PublicationError(
            f"local HEAD {head} must equal {PUBLICATION_REMOTE}/{PUBLICATION_BRANCH} {remote_sha}"
        )
    return PublicationSnapshot(str(root), head, remote_sha)


def _relative_article_path(repo: Path, article_path: Path) -> tuple[Path, str]:
    root = validate_horizon_workspace(repo)
    path = article_path.expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise PublicationError("article path must be inside the Horizon workspace") from exc
    if Path(relative).parent != Path("articles") or path.suffix != ".md":
        raise PublicationError("article path must be articles/{slug}.md")
    if not path.is_file():
        raise PublicationError(f"article file does not exist: {relative}")
    tracked = _run(
        root,
        ["git", "ls-files", "--error-unmatch", "--", relative],
        allowed_returncodes={0, 1},
    )
    if tracked.returncode == 0:
        raise PublicationError("publication only accepts a newly created article file")
    return path, relative


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_new_file_diff(relative: str, content: str) -> str:
    """Return the stable diff representation shown for a new article."""
    lines = content.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            [],
            lines,
            fromfile="/dev/null",
            tofile=f"b/{relative}",
            lineterm="\n",
        )
    )


def canonical_new_file_diffs(entries: Sequence[tuple[str, str]]) -> str:
    """Return deterministic diffs for a batch of newly created articles."""
    return "".join(
        canonical_new_file_diff(relative, content) for relative, content in entries
    )


def build_review(repo: Path, article_path: Path) -> tuple[ReviewState, str]:
    """Bind the exact article, diff, HEAD, and target that the user reviews."""
    snapshot = preflight(repo)
    root = Path(snapshot.repo_root)
    path, relative = _relative_article_path(root, article_path)
    content = path.read_text(encoding="utf-8")
    diff = canonical_new_file_diff(relative, content)
    state = ReviewState(
        version=1,
        repo_root=str(root),
        article_path=relative,
        article_sha256=_file_sha256(path),
        diff_sha256=hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        base_head=snapshot.head,
        remote_sha=snapshot.remote_sha,
        remote=PUBLICATION_REMOTE,
        branch=PUBLICATION_BRANCH,
        commit_message=f"clip(article): {path.stem}",
    )
    return state, diff


def build_batch_review(
    repo: Path, article_paths: Sequence[Path]
) -> tuple[BatchReviewState, str]:
    """Bind a deterministic multi-article diff to one publication approval."""
    if len(article_paths) < 2:
        raise PublicationError("batch review requires at least two article paths")
    snapshot = preflight(repo)
    root = Path(snapshot.repo_root)
    entries: list[tuple[Path, str]] = []
    for article_path in article_paths:
        path, relative = _relative_article_path(root, article_path)
        entries.append((path, relative))
    entries.sort(key=lambda item: item[1])
    relative_paths = [relative for _, relative in entries]
    if len(set(relative_paths)) != len(relative_paths):
        raise PublicationError("batch review contains duplicate article paths")
    state_entries = tuple(
        BatchReviewArticle(relative, _file_sha256(path)) for path, relative in entries
    )
    diff = canonical_new_file_diffs(
        [(relative, path.read_text(encoding="utf-8")) for path, relative in entries]
    )
    state = BatchReviewState(
        version=1,
        repo_root=str(root),
        articles=state_entries,
        diff_sha256=hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        base_head=snapshot.head,
        remote_sha=snapshot.remote_sha,
        remote=PUBLICATION_REMOTE,
        branch=PUBLICATION_BRANCH,
        commit_message=f"clip(articles): import {len(state_entries)} articles",
    )
    return state, diff


def save_review_state(state: ReviewState | BatchReviewState, output: Path) -> None:
    """Persist review state outside the repository for the approval boundary."""
    root = Path(state.repo_root)
    output = output.expanduser().resolve()
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise PublicationError("review state must be stored outside the Horizon workspace")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")


def load_review_state(path: Path) -> ReviewState:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"cannot read review state {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationError("review state must contain a JSON object")
    return ReviewState.from_dict(value)


def load_batch_review_state(path: Path) -> BatchReviewState:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"cannot read batch review state {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationError("batch review state must contain a JSON object")
    return BatchReviewState.from_dict(value)


def _assert_review_unchanged(
    state: ReviewState, *, fetch: bool = True
) -> tuple[Path, Path, str]:
    root = validate_horizon_workspace(Path(state.repo_root))
    snapshot = preflight(root, fetch=fetch)
    if snapshot.head != state.base_head or snapshot.remote_sha != state.remote_sha:
        raise PublicationError("HEAD or remote changed after review; generate a new review")
    if state.remote != PUBLICATION_REMOTE or state.branch != PUBLICATION_BRANCH:
        raise PublicationError("review targets a non-publication remote or branch")
    path, relative = _relative_article_path(root, root / state.article_path)
    if relative != state.article_path or _file_sha256(path) != state.article_sha256:
        raise PublicationError("article changed after review; generate a new review")
    diff = canonical_new_file_diff(relative, path.read_text(encoding="utf-8"))
    if hashlib.sha256(diff.encode("utf-8")).hexdigest() != state.diff_sha256:
        raise PublicationError("article diff changed after review; generate a new review")
    if state.commit_message != f"clip(article): {path.stem}":
        raise PublicationError("review contains an invalid commit message")
    return root, path, relative


def _assert_batch_review_unchanged(
    state: BatchReviewState, *, fetch: bool = True
) -> tuple[Path, list[tuple[Path, str]]]:
    root = validate_horizon_workspace(Path(state.repo_root))
    snapshot = preflight(root, fetch=fetch)
    if snapshot.head != state.base_head or snapshot.remote_sha != state.remote_sha:
        raise PublicationError("HEAD or remote changed after review; generate a new review")
    if state.remote != PUBLICATION_REMOTE or state.branch != PUBLICATION_BRANCH:
        raise PublicationError("review targets a non-publication remote or branch")
    entries: list[tuple[Path, str]] = []
    for entry in state.articles:
        path, relative = _relative_article_path(root, root / entry.article_path)
        if relative != entry.article_path or _file_sha256(path) != entry.article_sha256:
            raise PublicationError("article changed after review; generate a new review")
        entries.append((path, relative))
    if [relative for _, relative in entries] != sorted(
        relative for _, relative in entries
    ) or len({relative for _, relative in entries}) != len(entries):
        raise PublicationError("batch review contains invalid article paths")
    diff = canonical_new_file_diffs(
        [(relative, path.read_text(encoding="utf-8")) for path, relative in entries]
    )
    if hashlib.sha256(diff.encode("utf-8")).hexdigest() != state.diff_sha256:
        raise PublicationError("article diff changed after review; generate a new review")
    if state.commit_message != f"clip(articles): import {len(entries)} articles":
        raise PublicationError("review contains an invalid commit message")
    return root, entries


def discard_review(state: ReviewState) -> str:
    """Delete an uncommitted reviewed file only when its approved hash is unchanged."""
    root, path, relative = _assert_review_unchanged(state, fetch=False)
    if relative in _staged_paths(root):
        raise PublicationError("cannot discard a staged article")
    path.unlink()
    return relative


def discard_batch_review(state: BatchReviewState) -> list[str]:
    """Delete an unchanged batch only after checking every reviewed article."""
    root, entries = _assert_batch_review_unchanged(state, fetch=False)
    staged = _staged_paths(root)
    relative_paths = [relative for _, relative in entries]
    if any(relative in staged for relative in relative_paths):
        raise PublicationError("cannot discard a staged article")
    for path, _ in entries:
        path.unlink()
    return relative_paths


def commit_review(state: ReviewState) -> CommitResult:
    """Commit exactly the approved article while preserving unrelated worktree state."""
    root, path, relative = _assert_review_unchanged(state)
    try:
        _run(root, ["git", "add", "--", relative])
        staged = _staged_paths(root)
        if staged != [relative]:
            raise PublicationError(
                "staged paths changed during publication: " + ", ".join(staged)
            )
        _run(root, ["git", "diff", "--cached", "--check"])
        _run(root, ["git", "commit", "-m", state.commit_message])
    except Exception:
        if relative in _staged_paths(root):
            _run(root, ["git", "restore", "--staged", "--", relative])
        raise

    commit_sha = _run(root, ["git", "rev-parse", "HEAD"]).stdout.strip()
    parent = _run(root, ["git", "rev-parse", f"{commit_sha}^1"]).stdout.strip()
    if parent != state.base_head:
        raise PublicationError("created commit has an unexpected parent")
    paths = [
        line
        for line in _run(
            root,
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
        ).stdout.splitlines()
        if line
    ]
    if paths != [relative]:
        raise PublicationError("created commit contains unexpected paths")
    message = _run(root, ["git", "show", "-s", "--format=%s", commit_sha]).stdout.strip()
    if message != state.commit_message:
        raise PublicationError("created commit message differs from the review")
    committed = _run(root, ["git", "show", f"{commit_sha}:{relative}"]).stdout
    diff = canonical_new_file_diff(relative, committed)
    if hashlib.sha256(diff.encode("utf-8")).hexdigest() != state.diff_sha256:
        raise PublicationError("created commit differs from the reviewed diff")
    return CommitResult(commit_sha, relative, message)


def commit_batch_review(state: BatchReviewState) -> BatchCommitResult:
    """Commit exactly the reviewed batch while preserving unrelated worktree state."""
    root, entries = _assert_batch_review_unchanged(state)
    relative_paths = [relative for _, relative in entries]
    try:
        _run(root, ["git", "add", "--", *relative_paths])
        staged = _staged_paths(root)
        if set(staged) != set(relative_paths) or len(staged) != len(relative_paths):
            raise PublicationError(
                "staged paths changed during publication: " + ", ".join(staged)
            )
        _run(root, ["git", "diff", "--cached", "--check"])
        _run(root, ["git", "commit", "-m", state.commit_message])
    except Exception:
        staged = _staged_paths(root)
        restore = [relative for relative in relative_paths if relative in staged]
        if restore:
            _run(root, ["git", "restore", "--staged", "--", *restore])
        raise

    commit_sha = _run(root, ["git", "rev-parse", "HEAD"]).stdout.strip()
    parent = _run(root, ["git", "rev-parse", f"{commit_sha}^1"]).stdout.strip()
    if parent != state.base_head:
        raise PublicationError("created commit has an unexpected parent")
    paths = sorted(
        line
        for line in _run(
            root,
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
        ).stdout.splitlines()
        if line
    )
    if paths != relative_paths:
        raise PublicationError("created commit contains unexpected paths")
    message = _run(root, ["git", "show", "-s", "--format=%s", commit_sha]).stdout.strip()
    if message != state.commit_message:
        raise PublicationError("created commit message differs from the review")
    diff = canonical_new_file_diffs(
        [
            (relative, _run(root, ["git", "show", f"{commit_sha}:{relative}"]).stdout)
            for relative in relative_paths
        ]
    )
    if hashlib.sha256(diff.encode("utf-8")).hexdigest() != state.diff_sha256:
        raise PublicationError("created commit differs from the reviewed diff")
    return BatchCommitResult(commit_sha, tuple(relative_paths), message)


def _assert_commit_matches_review(
    root: Path, state: ReviewState, commit_sha: str
) -> None:
    parent = _run(root, ["git", "rev-parse", f"{commit_sha}^1"]).stdout.strip()
    if parent != state.base_head or parent != state.remote_sha:
        raise PublicationError("reviewed commit has an unexpected parent")
    paths = [
        line
        for line in _run(
            root,
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
        ).stdout.splitlines()
        if line
    ]
    if paths != [state.article_path]:
        raise PublicationError("reviewed commit contains unexpected paths")
    message = _run(root, ["git", "show", "-s", "--format=%s", commit_sha]).stdout.strip()
    if message != state.commit_message:
        raise PublicationError("reviewed commit message differs from approval")
    committed = _run(root, ["git", "show", f"{commit_sha}:{state.article_path}"]).stdout
    diff = canonical_new_file_diff(state.article_path, committed)
    if hashlib.sha256(diff.encode("utf-8")).hexdigest() != state.diff_sha256:
        raise PublicationError("reviewed commit content differs from approval")


def _assert_commit_matches_batch_review(
    root: Path, state: BatchReviewState, commit_sha: str
) -> None:
    parent = _run(root, ["git", "rev-parse", f"{commit_sha}^1"]).stdout.strip()
    if parent != state.base_head or parent != state.remote_sha:
        raise PublicationError("reviewed commit has an unexpected parent")
    expected_paths = [entry.article_path for entry in state.articles]
    paths = sorted(
        line
        for line in _run(
            root,
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
        ).stdout.splitlines()
        if line
    )
    if paths != expected_paths:
        raise PublicationError("reviewed commit contains unexpected paths")
    message = _run(root, ["git", "show", "-s", "--format=%s", commit_sha]).stdout.strip()
    if message != state.commit_message:
        raise PublicationError("reviewed commit message differs from approval")
    diff = canonical_new_file_diffs(
        [
            (
                entry.article_path,
                _run(root, ["git", "show", f"{commit_sha}:{entry.article_path}"]).stdout,
            )
            for entry in state.articles
        ]
    )
    if hashlib.sha256(diff.encode("utf-8")).hexdigest() != state.diff_sha256:
        raise PublicationError("reviewed commit content differs from approval")


def push_review(state: ReviewState, commit_sha: str) -> dict[str, Any]:
    """Push the reviewed commit to the one fixed publication ref, without force."""
    root = validate_horizon_workspace(Path(state.repo_root))
    head = _run(root, ["git", "rev-parse", "HEAD"]).stdout.strip()
    if head != commit_sha:
        raise PublicationError("current HEAD is not the reviewed commit")
    _assert_commit_matches_review(root, state, commit_sha)
    _fetch_publication_ref(root)
    remote_ref = f"refs/remotes/{PUBLICATION_REMOTE}/{PUBLICATION_BRANCH}"
    current_remote = _run(root, ["git", "rev-parse", remote_ref]).stdout.strip()
    if current_remote == commit_sha:
        return {"commit_sha": commit_sha, "already_pushed": True}
    if current_remote != state.remote_sha:
        raise PublicationError("publication branch moved after review; do not retry blindly")

    _run(
        root,
        [
            "git",
            "push",
            PUBLICATION_REMOTE,
            f"{commit_sha}:refs/heads/{PUBLICATION_BRANCH}",
        ],
    )
    remote_line = _run(
        root,
        ["git", "ls-remote", PUBLICATION_REMOTE, f"refs/heads/{PUBLICATION_BRANCH}"],
    ).stdout.strip()
    remote_sha = remote_line.split()[0] if remote_line else ""
    if remote_sha != commit_sha:
        raise PublicationError("remote publication ref does not match the pushed commit")
    return {"commit_sha": commit_sha, "already_pushed": False}


def push_batch_review(state: BatchReviewState, commit_sha: str) -> dict[str, Any]:
    """Push one reviewed batch to the fixed publication branch without force."""
    root = validate_horizon_workspace(Path(state.repo_root))
    head = _run(root, ["git", "rev-parse", "HEAD"]).stdout.strip()
    if head != commit_sha:
        raise PublicationError("current HEAD is not the reviewed commit")
    _assert_commit_matches_batch_review(root, state, commit_sha)
    _fetch_publication_ref(root)
    remote_ref = f"refs/remotes/{PUBLICATION_REMOTE}/{PUBLICATION_BRANCH}"
    current_remote = _run(root, ["git", "rev-parse", remote_ref]).stdout.strip()
    if current_remote == commit_sha:
        return {"commit_sha": commit_sha, "already_pushed": True}
    if current_remote != state.remote_sha:
        raise PublicationError("publication branch moved after review; do not retry blindly")
    _run(
        root,
        [
            "git",
            "push",
            PUBLICATION_REMOTE,
            f"{commit_sha}:refs/heads/{PUBLICATION_BRANCH}",
        ],
    )
    remote_line = _run(
        root,
        ["git", "ls-remote", PUBLICATION_REMOTE, f"refs/heads/{PUBLICATION_BRANCH}"],
    ).stdout.strip()
    remote_sha = remote_line.split()[0] if remote_line else ""
    if remote_sha != commit_sha:
        raise PublicationError("remote publication ref does not match the pushed commit")
    return {"commit_sha": commit_sha, "already_pushed": False}


def query_workflow_run(
    repo: Path,
    commit_sha: str,
    *,
    wait_seconds: float = 0,
    poll_seconds: float = 3,
) -> dict[str, Any]:
    """Find the publication workflow run tied to one exact commit SHA."""
    root = validate_horizon_workspace(repo)
    github_repo = _github_repo_for_publication(root)
    deadline = time.monotonic() + max(wait_seconds, 0)
    last_match: Optional[dict[str, Any]] = None
    while True:
        result = _run(
            root,
            [
                "gh",
                "run",
                "list",
                "--repo",
                github_repo,
                "--workflow",
                PUBLICATION_WORKFLOW,
                "--commit",
                commit_sha,
                "--limit",
                "20",
                "--json",
                "databaseId,url,status,conclusion,event,headBranch,headSha",
            ],
        )
        try:
            runs = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise PublicationError("gh returned invalid workflow JSON") from exc
        if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
            raise PublicationError("gh returned an unexpected workflow JSON shape")
        for run in runs:
            if (
                run.get("headSha") == commit_sha
                and run.get("event") == "push"
                and run.get("headBranch") == PUBLICATION_BRANCH
            ):
                last_match = run
                break
        if last_match and (
            last_match.get("status") == "completed" or time.monotonic() >= deadline
        ):
            return last_match
        if time.monotonic() >= deadline:
            if last_match:
                return last_match
            raise PublicationError(
                f"no {PUBLICATION_WORKFLOW} run found for commit {commit_sha}"
            )
        time.sleep(min(poll_seconds, max(deadline - time.monotonic(), 0)))

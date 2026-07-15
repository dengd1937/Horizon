"""Tests for review-bound Git publication safety."""

import json
import subprocess
from pathlib import Path

import pytest

from src.articles.ingest import write_article
from src.articles.publication import (
    PublicationError,
    build_review,
    commit_review,
    discard_review,
    preflight,
    push_review,
    query_workflow_run,
    save_review_state,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _manifest(**overrides):
    value = {
        "title": "Publication Safety",
        "source_url": "https://example.com/publication-safety",
        "published_date": "2026-07-01",
        "summary": "A publication safety fixture.",
        "tags": ["testing"],
    }
    value.update(overrides)
    return value


@pytest.fixture
def git_workspace(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(remote)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repo)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _git(repo, "config", "user.name", "Horizon Test")
    _git(repo, "config", "user.email", "horizon@example.com")
    (repo / "docs").mkdir()
    (repo / "docs" / "article-frontmatter-spec.md").write_text("contract\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "horizon"\n')
    (repo / "baseline.txt").write_text("baseline\n")
    _git(repo, "add", "docs/article-frontmatter-spec.md", "pyproject.toml", "baseline.txt")
    _git(repo, "commit", "-m", "baseline")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-u", "origin", "main")
    return repo, remote


def _new_article(repo: Path):
    return write_article(
        repo / "articles",
        _manifest(),
        "Full publication body.",
        added_date="2026-07-14",
    )


def test_preflight_allows_unstaged_but_rejects_staged(git_workspace):
    repo, _ = git_workspace
    (repo / "notes.txt").write_text("untracked\n")
    assert preflight(repo).branch == "main"

    (repo / "baseline.txt").write_text("staged\n")
    _git(repo, "add", "baseline.txt")
    staged_before = _git(repo, "diff", "--cached", "--name-only")
    with pytest.raises(PublicationError, match="index already contains"):
        preflight(repo)
    assert _git(repo, "diff", "--cached", "--name-only") == staged_before


def test_review_change_requires_new_approval(git_workspace, tmp_path):
    repo, _ = git_workspace
    result = _new_article(repo)
    state, diff = build_review(repo, result.path)
    state_path = tmp_path / "review.json"
    save_review_state(state, state_path)
    assert result.path.name in diff
    assert json.loads(state_path.read_text())["article_sha256"] == state.article_sha256

    result.path.write_text(result.path.read_text() + "changed\n")
    with pytest.raises(PublicationError, match="changed after review"):
        commit_review(state)
    assert _git(repo, "diff", "--cached", "--name-only") == ""


def test_head_change_requires_a_new_review(git_workspace):
    repo, _ = git_workspace
    result = _new_article(repo)
    state, _ = build_review(repo, result.path)
    (repo / "unrelated.txt").write_text("new commit\n")
    _git(repo, "add", "unrelated.txt")
    _git(repo, "commit", "-m", "unrelated change")

    with pytest.raises(PublicationError, match="must equal origin/main"):
        commit_review(state)

    assert result.path.is_file()
    assert _git(repo, "diff", "--cached", "--name-only") == ""


def test_discard_cancellation_preserves_git_state(git_workspace):
    repo, remote = git_workspace
    result = _new_article(repo)
    state, _ = build_review(repo, result.path)
    head = _git(repo, "rev-parse", "HEAD")
    remote_head = _git(remote, "rev-parse", "refs/heads/main")

    assert discard_review(state) == f"articles/{result.path.name}"
    assert not result.path.exists()
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    assert _git(remote, "rev-parse", "refs/heads/main") == remote_head


def test_keep_cancellation_leaves_reviewed_file_untracked(git_workspace):
    repo, remote = git_workspace
    result = _new_article(repo)
    build_review(repo, result.path)
    head = _git(repo, "rev-parse", "HEAD")
    remote_head = _git(remote, "rev-parse", "refs/heads/main")

    assert result.path.is_file()
    assert _git(repo, "status", "--short", "--", f"articles/{result.path.name}") == (
        f"?? articles/{result.path.name}"
    )
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    assert _git(remote, "rev-parse", "refs/heads/main") == remote_head


def test_commit_contains_only_approved_article_and_preserves_dirty_files(git_workspace):
    repo, _ = git_workspace
    result = _new_article(repo)
    (repo / "baseline.txt").write_text("unrelated dirty edit\n")
    (repo / "notes.txt").write_text("untracked\n")
    state, _ = build_review(repo, result.path)

    committed = commit_review(state)

    assert committed.commit_message == result.commit_message
    assert _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") == (
        f"articles/{result.path.name}"
    )
    assert _git(repo, "diff", "--", "baseline.txt")
    assert (repo / "notes.txt").read_text() == "untracked\n"
    assert _git(repo, "diff", "--cached", "--name-only") == ""


def test_push_moves_only_publication_ref_and_retry_is_idempotent(git_workspace):
    repo, remote = git_workspace
    result = _new_article(repo)
    state, _ = build_review(repo, result.path)
    commit = commit_review(state)

    pushed = push_review(state, commit.commit_sha)
    retried = push_review(state, commit.commit_sha)

    assert pushed == {"commit_sha": commit.commit_sha, "already_pushed": False}
    assert retried == {"commit_sha": commit.commit_sha, "already_pushed": True}
    assert _git(remote, "rev-parse", "refs/heads/main") == commit.commit_sha
    assert _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads") == (
        "refs/heads/main"
    )


def test_push_rejects_remote_movement(git_workspace, tmp_path):
    repo, remote = git_workspace
    result = _new_article(repo)
    state, _ = build_review(repo, result.path)
    commit = commit_review(state)

    other = tmp_path / "other"
    _git(tmp_path, "clone", str(remote), str(other))
    _git(other, "config", "user.name", "Other")
    _git(other, "config", "user.email", "other@example.com")
    (other / "remote-change.txt").write_text("remote\n")
    _git(other, "add", "remote-change.txt")
    _git(other, "commit", "-m", "remote change")
    _git(other, "push", "origin", "main")

    with pytest.raises(PublicationError, match="moved after review"):
        push_review(state, commit.commit_sha)
    assert _git(remote, "rev-parse", "refs/heads/main") != commit.commit_sha


def test_push_server_rejection_keeps_one_commit_for_authorized_retry(git_workspace):
    repo, remote = git_workspace
    result = _new_article(repo)
    state, _ = build_review(repo, result.path)
    commit = commit_review(state)
    remote_before = _git(remote, "rev-parse", "refs/heads/main")

    hook = remote / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\necho 'authorization denied by test remote' >&2\nexit 1\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    with pytest.raises(PublicationError, match="authorization denied"):
        push_review(state, commit.commit_sha)

    assert _git(repo, "rev-parse", "HEAD") == commit.commit_sha
    assert _git(remote, "rev-parse", "refs/heads/main") == remote_before
    assert _git(repo, "rev-list", "--count", f"{remote_before}..HEAD") == "1"

    hook.unlink()
    assert push_review(state, commit.commit_sha) == {
        "commit_sha": commit.commit_sha,
        "already_pushed": False,
    }
    assert _git(remote, "rev-parse", "refs/heads/main") == commit.commit_sha


def test_push_transport_failure_keeps_remote_unchanged_and_retry_is_exact(
    git_workspace, tmp_path
):
    repo, remote = git_workspace
    result = _new_article(repo)
    state, _ = build_review(repo, result.path)
    commit = commit_review(state)
    remote_before = _git(remote, "rev-parse", "refs/heads/main")
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "offline.git"))

    with pytest.raises(PublicationError, match="git fetch"):
        push_review(state, commit.commit_sha)

    assert _git(remote, "rev-parse", "refs/heads/main") == remote_before
    assert _git(repo, "rev-parse", "HEAD") == commit.commit_sha

    _git(repo, "remote", "set-url", "origin", str(remote))
    assert push_review(state, commit.commit_sha) == {
        "commit_sha": commit.commit_sha,
        "already_pushed": False,
    }
    assert _git(remote, "rev-parse", "refs/heads/main") == commit.commit_sha


def test_workflow_query_filters_exact_sha_branch_and_event(git_workspace, monkeypatch):
    repo, _ = git_workspace
    sha = _git(repo, "rev-parse", "HEAD")
    from src.articles import publication

    original_run = publication._run
    gh_commands = []

    def fake_run(root, command, **kwargs):
        if command == ["git", "remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(
                command, 0, "https://github.com/acme/horizon.git\n", ""
            )
        if command[0] == "gh":
            gh_commands.append(command)
            payload = [
                {
                    "databaseId": 7,
                    "url": "https://github.example/runs/7",
                    "status": "completed",
                    "conclusion": "success",
                    "event": "push",
                    "headBranch": "main",
                    "headSha": sha,
                }
            ]
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        return original_run(root, command, **kwargs)

    monkeypatch.setattr(publication, "_run", fake_run)
    run = query_workflow_run(repo, sha)
    assert run["headSha"] == sha
    assert run["headBranch"] == "main"
    assert run["event"] == "push"
    assert run["conclusion"] == "success"
    assert gh_commands[0][0:5] == [
        "gh",
        "run",
        "list",
        "--repo",
        "acme/horizon",
    ]

"""Tests for isolated local article preview generation."""

import json
import subprocess
import uuid
from pathlib import Path

import pytest

from src.articles.cli import main
from src.articles.contract import load_article
from src.articles.preview import PreviewError, render_article_preview


REPO_ROOT = Path(__file__).resolve().parents[1]


def _git_status() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _fetched(path: Path) -> Path:
    body = "A complete captured paragraph for local Horizon preview. " * 12
    path.write_text(
        "---\n"
        "title: Local Preview Article\n"
        "summary: Captured safely\n"
        "---\n\n"
        f"# Local Preview Article\n\n{body}\n\n"
        "![diagram](https://images.example.com/diagram.png)\n",
        encoding="utf-8",
    )
    return path


def _translated(path: Path) -> Path:
    body = "这是用于 Horizon 本地预览的完整中文译文段落。" * 24
    path.write_text(
        "# 本地预览文章\n\n"
        f"{body}\n\n"
        "![示意图](https://images.example.com/diagram.png)\n",
        encoding="utf-8",
    )
    return path


def _manifest() -> dict[str, object]:
    return {
        "title": "本地预览文章",
        "source_url": "https://example.com/local-preview",
        "published_date": "2026-07-15",
        "summary": "一篇无需发布即可生成的本地预览文章。",
        "tags": ["preview", "test"],
        "cover": "https://images.example.com/cover.png",
        "slug_title": "Local Preview Article",
    }


def test_preview_reuses_contract_and_renderer_without_touching_git(tmp_path):
    status_before = _git_status()
    result = render_article_preview(
        REPO_ROOT,
        _manifest(),
        _fetched(tmp_path / "fetched.md"),
        _translated(tmp_path / "translated.md"),
        tmp_path / "preview",
        added_date="2026-07-15",
    )

    article = load_article(Path(result.article_source))
    detail = Path(result.detail_path).read_text(encoding="utf-8")
    index = Path(result.index_path).read_text(encoding="utf-8")
    root_index = Path(result.site_root, "index.html").read_text(encoding="utf-8")

    assert article.slug == "example-com-20260715-local-preview-article"
    assert article.title in detail
    assert article.slug in index
    assert f"articles/{article.slug}.html" in root_index
    assert Path(result.preview_root).is_relative_to(tmp_path)
    assert _git_status() == status_before


def test_preview_root_must_be_outside_workspace(tmp_path):
    forbidden = REPO_ROOT / f".preview-test-{uuid.uuid4().hex}"
    with pytest.raises(PreviewError, match="outside the Horizon workspace"):
        render_article_preview(
            REPO_ROOT,
            _manifest(),
            _fetched(tmp_path / "fetched.md"),
            _translated(tmp_path / "translated.md"),
            forbidden,
        )
    assert not forbidden.exists()


def test_preview_refuses_nonempty_destination(tmp_path):
    preview_root = tmp_path / "preview"
    preview_root.mkdir()
    (preview_root / "keep.txt").write_text("user data\n", encoding="utf-8")

    with pytest.raises(PreviewError, match="must be empty"):
        render_article_preview(
            REPO_ROOT,
            _manifest(),
            _fetched(tmp_path / "fetched.md"),
            _translated(tmp_path / "translated.md"),
            preview_root,
        )
    assert (preview_root / "keep.txt").read_text(encoding="utf-8") == "user data\n"


def test_preview_cli_returns_paths_and_workspace_command_is_read_only(tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    preview_root = tmp_path / "preview"

    assert main(["workspace", "--repo", str(REPO_ROOT)]) == 0
    workspace_output = json.loads(capsys.readouterr().out)
    assert workspace_output["repo_root"] == str(REPO_ROOT)

    assert (
        main(
            [
                "preview",
                "--repo",
                str(REPO_ROOT),
                "--manifest",
                str(manifest),
                "--fetched",
                str(_fetched(tmp_path / "fetched.md")),
                "--body",
                str(_translated(tmp_path / "translated.md")),
                "--preview-root",
                str(preview_root),
                "--added-date",
                "2026-07-15",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["slug"] == "example-com-20260715-local-preview-article"
    assert Path(output["detail_path"]).is_file()

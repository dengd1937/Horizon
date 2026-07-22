"""Local workflow tests for the horizon-add-paper skill helper."""

from pathlib import Path

import pytest

from src.papers.cli import main
from src.papers.workflow import (
    PaperWorkflowError,
    create_paper,
    render_paper_preview,
)

PROJECT_ROOT = Path(__file__).parents[1]
REACT = PROJECT_ROOT / "papers" / "yao-2022-react-synergizing-reasoning-acting.md"


def test_validate_cli_reports_contract_sections(capsys):
    assert main(["validate", "--source", str(REACT)]) == 0
    output = capsys.readouterr().out

    assert '"slug": "yao-2022-react-synergizing-reasoning-acting"' in output
    assert '"论文结论与证据边界"' in output
    assert '"AI 解读"' in output


def test_preview_is_isolated_and_renders_index_and_detail(tmp_path):
    preview_root = tmp_path / "paper-preview"
    result = render_paper_preview(PROJECT_ROOT, REACT, preview_root)

    assert Path(result.paper_source).is_file()
    assert Path(result.index_path).is_file()
    assert Path(result.detail_path).is_file()
    assert (Path(result.site_root) / "index.html").is_file()
    assert "AI 解读" in Path(result.detail_path).read_text(encoding="utf-8")


def test_preview_refuses_workspace_and_nonempty_destinations(tmp_path):
    with pytest.raises(PaperWorkflowError, match="outside"):
        render_paper_preview(PROJECT_ROOT, REACT, PROJECT_ROOT / ".paper-preview")

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(PaperWorkflowError, match="empty"):
        render_paper_preview(PROJECT_ROOT, REACT, occupied)


def test_create_adds_only_validated_source_and_rejects_duplicates(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(
        "src.papers.workflow.validate_horizon_workspace", lambda value: repo
    )

    result = create_paper(repo, REACT)
    destination = repo / result.paper_path

    assert destination.is_file()
    assert destination.read_text(encoding="utf-8") == REACT.read_text(encoding="utf-8")
    assert list((repo / "papers").glob("*.md")) == [destination]

    with pytest.raises(PaperWorkflowError, match="already exists"):
        create_paper(repo, REACT)

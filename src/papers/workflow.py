"""Deterministic local workflow primitives for Horizon paper close reads."""

import html
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from ..articles.publication import validate_horizon_workspace
from ..render.papers import render_papers
from .contract import ResearchPaper, load_paper, load_papers


class PaperWorkflowError(RuntimeError):
    """Raised when a paper draft cannot be previewed or added safely."""


@dataclass(frozen=True)
class PaperPreviewResult:
    preview_root: str
    paper_source: str
    site_root: str
    index_path: str
    detail_path: str
    slug: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PaperCreateResult:
    paper_path: str
    slug: str
    title: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _load_source(source: Path) -> tuple[Path, ResearchPaper, str]:
    path = source.expanduser().resolve()
    if not path.is_file():
        raise PaperWorkflowError(f"paper source does not exist: {path}")
    if path.suffix != ".md":
        raise PaperWorkflowError("paper source must be a Markdown file")
    content = path.read_text(encoding="utf-8")
    return path, load_paper(path), content


def _isolated_preview_root(repo: Path, preview_root: Path) -> Path:
    root = preview_root.expanduser().resolve()
    try:
        root.relative_to(repo)
    except ValueError:
        pass
    else:
        raise PaperWorkflowError("preview root must be outside the Horizon workspace")

    if root.exists():
        if not root.is_dir():
            raise PaperWorkflowError(f"preview root is not a directory: {root}")
        if any(root.iterdir()):
            raise PaperWorkflowError(f"preview root must be empty: {root}")
    return root


def _write_preview_redirect(site_root: Path, paper: ResearchPaper) -> None:
    relative_detail = f"papers/{paper.slug}.html"
    (site_root / "index.html").write_text(
        "<!doctype html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={relative_detail}">'
        f'<title>{html.escape(paper.title)} · Horizon Preview</title></head>'
        f'<body><a href="{relative_detail}">打开论文预览</a></body></html>\n',
        encoding="utf-8",
    )


def render_paper_preview(
    repo: Path,
    source: Path,
    preview_root: Path,
) -> PaperPreviewResult:
    """Validate and render one paper without touching ``papers/`` or Git."""
    root = validate_horizon_workspace(repo)
    preview_root = _isolated_preview_root(root, preview_root)
    _, paper, content = _load_source(source)

    source_dir = preview_root / "paper-source"
    source_dir.mkdir(parents=True)
    preview_source = source_dir / f"{paper.slug}.md"
    preview_source.write_text(content, encoding="utf-8")

    site_root = preview_root / "site"
    render_papers(site_root, load_papers(source_dir))
    _write_preview_redirect(site_root, paper)

    return PaperPreviewResult(
        preview_root=str(preview_root),
        paper_source=str(preview_source),
        site_root=str(site_root),
        index_path=str(site_root / "papers" / "index.html"),
        detail_path=str(site_root / "papers" / f"{paper.slug}.html"),
        slug=paper.slug,
    )


def _reject_collision(existing: list[ResearchPaper], paper: ResearchPaper) -> None:
    checks = (
        ("paper_url", paper.paper_url),
        ("arxiv_id", paper.arxiv_id),
        ("doi", paper.doi),
    )
    for field, value in checks:
        if value and any(getattr(item, field) == value for item in existing):
            raise PaperWorkflowError(f"duplicate {field}: {value}")


def create_paper(repo: Path, source: Path) -> PaperCreateResult:
    """Add one validated draft to ``papers/`` without staging or publishing it."""
    root = validate_horizon_workspace(repo)
    _, paper, content = _load_source(source)
    paper_dir = root / "papers"
    paper_dir.mkdir(parents=True, exist_ok=True)
    destination = paper_dir / f"{paper.slug}.md"
    if destination.exists():
        raise PaperWorkflowError(f"paper already exists: {destination.relative_to(root)}")
    _reject_collision(load_papers(paper_dir), paper)

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=paper_dir,
            prefix=f".{paper.slug}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, destination)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise

    validated = load_paper(destination)
    return PaperCreateResult(
        paper_path=str(destination.relative_to(root)),
        slug=validated.slug,
        title=validated.title,
    )


def result_json(result: PaperPreviewResult | PaperCreateResult) -> str:
    return json.dumps(result.as_dict(), ensure_ascii=False, indent=2)

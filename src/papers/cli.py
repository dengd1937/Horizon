"""Command-line interface used by the horizon-add-paper skill."""

import argparse
import json
import sys
from pathlib import Path

from ..articles.publication import PublicationError, validate_horizon_workspace
from .contract import PaperValidationError, load_paper
from .workflow import (
    PaperWorkflowError,
    create_paper,
    render_paper_preview,
    result_json,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horizon-paper",
        description="Validate, preview, and locally add a Horizon paper close read.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    workspace = subparsers.add_parser("workspace")
    workspace.add_argument("--repo", type=Path, default=Path.cwd())

    validate = subparsers.add_parser("validate")
    validate.add_argument("--source", type=Path, required=True)

    preview = subparsers.add_parser("preview")
    preview.add_argument("--repo", type=Path, default=Path.cwd())
    preview.add_argument("--source", type=Path, required=True)
    preview.add_argument("--preview-root", type=Path, required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--repo", type=Path, default=Path.cwd())
    create.add_argument("--source", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "workspace":
            root = validate_horizon_workspace(args.repo)
            print(json.dumps({"repo_root": str(root)}, indent=2))
        elif args.command == "validate":
            paper = load_paper(args.source.expanduser().resolve())
            print(
                json.dumps(
                    {
                        "path": str(args.source),
                        "slug": paper.slug,
                        "title": paper.title,
                        "sections": ["论文结论与证据边界", "AI 解读"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "preview":
            print(
                result_json(
                    render_paper_preview(args.repo, args.source, args.preview_root)
                )
            )
        elif args.command == "create":
            print(result_json(create_paper(args.repo, args.source)))
        return 0
    except (
        PaperValidationError,
        PaperWorkflowError,
        PublicationError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

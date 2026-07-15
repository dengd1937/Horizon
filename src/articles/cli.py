"""Command-line interface used by the horizon-add-article skill."""

import argparse
import json
import sys
from pathlib import Path

from .contract import ArticleValidationError, load_article
from .fetch import FetchError, load_reader_command, run_baoyu_fetch
from .ingest import load_manifest, write_article
from .preview import PreviewError, preview_result_json, render_article_preview
from .publication import (
    PublicationError,
    build_review,
    commit_review,
    discard_review,
    load_review_state,
    preflight,
    push_review,
    query_workflow_run,
    save_review_state,
    validate_horizon_workspace,
)
from .translation import load_translated_body, validate_article_translation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horizon-article",
        description="Create and safely publish one Horizon curated article.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    workspace_parser = subparsers.add_parser("workspace")
    workspace_parser.add_argument("--repo", type=Path, default=Path.cwd())

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--repo", type=Path, default=Path.cwd())

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--reader-command", type=Path, required=True)
    fetch.add_argument("--url", required=True)
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--process-timeout-seconds", type=float, default=90)
    fetch.add_argument("--page-timeout-ms", type=int, default=30_000)
    fetch.add_argument("--allow-short", action="store_true")

    create = subparsers.add_parser("create")
    create.add_argument("--repo", type=Path, default=Path.cwd())
    create.add_argument("--manifest", type=Path, required=True)
    create.add_argument("--fetched", type=Path, required=True)
    create.add_argument("--body", type=Path, required=True)
    create.add_argument("--added-date")

    validate = subparsers.add_parser("validate")
    validate.add_argument("article", type=Path)

    preview = subparsers.add_parser("preview")
    preview.add_argument("--repo", type=Path, default=Path.cwd())
    preview.add_argument("--manifest", type=Path, required=True)
    preview.add_argument("--fetched", type=Path, required=True)
    preview.add_argument("--body", type=Path, required=True)
    preview.add_argument("--preview-root", type=Path, required=True)
    preview.add_argument("--added-date")

    review = subparsers.add_parser("review")
    review.add_argument("--repo", type=Path, default=Path.cwd())
    review.add_argument("--article", type=Path, required=True)
    review.add_argument("--state", type=Path, required=True)

    commit = subparsers.add_parser("commit")
    commit.add_argument("--state", type=Path, required=True)

    discard = subparsers.add_parser("discard")
    discard.add_argument("--state", type=Path, required=True)

    push = subparsers.add_parser("push")
    push.add_argument("--state", type=Path, required=True)
    push.add_argument("--commit", required=True)

    workflow = subparsers.add_parser("workflow")
    workflow.add_argument("--repo", type=Path, default=Path.cwd())
    workflow.add_argument("--commit", required=True)
    workflow.add_argument("--wait-seconds", type=float, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "workspace":
            print(
                json.dumps(
                    {"repo_root": str(validate_horizon_workspace(args.repo))},
                    indent=2,
                )
            )
        elif args.command == "preflight":
            print(json.dumps(preflight(args.repo).__dict__, indent=2))
        elif args.command == "fetch":
            result = run_baoyu_fetch(
                load_reader_command(args.reader_command),
                args.url,
                args.output,
                process_timeout_seconds=args.process_timeout_seconds,
                page_timeout_ms=args.page_timeout_ms,
                allow_short=args.allow_short,
            )
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        elif args.command == "create":
            repo = Path(preflight(args.repo).repo_root)
            manifest = load_manifest(args.manifest)
            fetched = validate_fetch_output(args.fetched)
            body = validate_article_translation(
                manifest, fetched.body_md, load_translated_body(args.body)
            )
            result = write_article(
                repo / "articles", manifest, body, added_date=args.added_date
            )
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        elif args.command == "validate":
            article = load_article(args.article)
            print(json.dumps({"path": str(args.article), "slug": article.slug}, indent=2))
        elif args.command == "preview":
            result = render_article_preview(
                args.repo,
                load_manifest(args.manifest),
                args.fetched,
                args.body,
                args.preview_root,
                added_date=args.added_date,
            )
            print(preview_result_json(result))
        elif args.command == "review":
            state, diff = build_review(args.repo, args.article)
            save_review_state(state, args.state)
            print(diff, end="" if diff.endswith("\n") else "\n")
            print(f"Review state: {args.state}")
        elif args.command == "commit":
            result = commit_review(load_review_state(args.state))
            print(json.dumps(result.as_dict(), indent=2))
        elif args.command == "discard":
            relative = discard_review(load_review_state(args.state))
            print(json.dumps({"discarded": relative}, indent=2))
        elif args.command == "push":
            result = push_review(load_review_state(args.state), args.commit)
            print(json.dumps(result, indent=2))
        elif args.command == "workflow":
            result = query_workflow_run(
                args.repo, args.commit, wait_seconds=args.wait_seconds
            )
            print(json.dumps(result, indent=2))
        return 0
    except (
        ArticleValidationError,
        FetchError,
        PreviewError,
        PublicationError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

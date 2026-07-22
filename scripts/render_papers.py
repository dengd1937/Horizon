"""Render the local paper-library index and detail pages without deploying."""

import argparse
from pathlib import Path

from src.papers.contract import load_papers
from src.render.papers import render_papers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("papers"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    papers = load_papers(args.source)
    paths = render_papers(args.output, papers)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()

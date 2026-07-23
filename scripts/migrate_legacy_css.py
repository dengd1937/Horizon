"""One-time migration of legacy inline-style pages to the shared stylesheet."""

import argparse
import re
from pathlib import Path

from src.render.site_css import SITE_CSS_HREF, write_site_css


_INLINE_SITE_STYLE_RE = re.compile(
    r"<style>\s*:root\s*\{.*?</style>", re.DOTALL
)


def migrate_legacy_css(site_root: Path, *, write: bool = False) -> list[Path]:
    """Return legacy HTML pages that can be safely migrated; write on request."""
    changed: list[Path] = []
    replacement = f'<link rel="stylesheet" href="{SITE_CSS_HREF}">'
    for section in ("daily", "articles", "papers"):
        directory = site_root / section
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.html")):
            content = path.read_text(encoding="utf-8")
            if 'href="../assets/site/horizon.css"' in content:
                continue
            migrated, count = _INLINE_SITE_STYLE_RE.subn(
                replacement, content, count=1
            )
            if count:
                migrated = migrated.replace(
                    "style-src 'unsafe-inline';",
                    "style-src 'self' 'unsafe-inline';",
                )
                changed.append(path)
                if write:
                    path.write_text(migrated, encoding="utf-8")
    if write and changed:
        write_site_css(site_root)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path("data/site"))
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the migration; default behavior is a dry-run",
    )
    args = parser.parse_args()
    changed = migrate_legacy_css(args.site_root, write=args.write)
    mode = "Migrated" if args.write else "Would migrate"
    print(f"{mode} {len(changed)} legacy page(s).")
    for path in changed:
        print(path)


if __name__ == "__main__":
    main()

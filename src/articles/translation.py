"""Validation for Chinese article translations derived from captured Markdown."""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from .contract import ArticleValidationError

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_URL_RE = re.compile(r"https?://\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MARKDOWN_REFERENCE_RE = re.compile(
    r"(?P<image>!)?\[[^\]]*\]\((?P<url><[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)"
)
_RAW_MEDIA_TAG_RE = re.compile(
    r"<(?:img|video|audio|source|iframe)\b[^>]*>", re.IGNORECASE
)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", re.DOTALL)


class TranslationError(ArticleValidationError):
    """Raised when a translated article is not a faithful Chinese rendition."""


class _HtmlReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, str, str]] = []

    def _record(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src", "poster"} and value:
                self.references.append((tag.lower(), name, value))

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._record(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._record(tag, attrs)


def load_translated_body(path: Path) -> str:
    """Read a body-only UTF-8 translation and reject nested frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TranslationError(f"cannot read translated body {path}: {exc}") from exc
    body = text.strip()
    if not body:
        raise TranslationError("translated article body must not be empty")
    if _FRONTMATTER_RE.match(body):
        raise TranslationError("translated article body must not contain frontmatter")
    return body


def _markdown_references(markdown_text: str) -> list[tuple[str, str]]:
    return [
        (
            "image" if match.group("image") else "link",
            match.group("url").strip("<>"),
        )
        for match in _MARKDOWN_REFERENCE_RE.finditer(markdown_text)
    ]


def _html_references(markdown_text: str) -> list[tuple[str, str, str]]:
    parser = _HtmlReferenceParser()
    parser.feed(markdown_text)
    return parser.references


def _fenced_code_blocks(markdown_text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] | None = None
    fence_char = ""
    fence_length = 0
    for line in markdown_text.splitlines():
        stripped = line.lstrip()
        opening = re.match(r"(`{3,}|~{3,})", stripped)
        if current is None:
            if opening:
                fence = opening.group(1)
                fence_char = fence[0]
                fence_length = len(fence)
                current = [line]
            continue
        current.append(line)
        if re.fullmatch(
            rf"\s*{re.escape(fence_char)}{{{fence_length},}}\s*", line
        ):
            blocks.append("\n".join(current))
            current = None
    if current is not None:
        blocks.append("\n".join(current))
    return blocks


def _structure(markdown_text: str) -> list[str]:
    tokens: list[str] = []
    in_fence = False
    fence_char = ""
    fence_length = 0
    for line in markdown_text.splitlines():
        stripped = line.lstrip()
        fence = re.match(r"(`{3,}|~{3,})", stripped)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_length = len(marker)
                tokens.append("fence")
            elif marker[0] == fence_char and len(marker) >= fence_length:
                in_fence = False
            continue
        if in_fence:
            continue
        heading = re.match(r"^(#{1,6})\s+", stripped)
        if heading:
            tokens.append(f"h{len(heading.group(1))}")
        elif re.match(r"^[-+*]\s+", stripped):
            tokens.append("ul")
        elif re.match(r"^\d+[.)]\s+", stripped):
            tokens.append("ol")
        elif stripped.startswith(">"):
            tokens.append("blockquote")
    return tokens


def _markdown_blocks(markdown_text: str) -> list[str]:
    """Return blank-line-delimited block types, including ordinary prose.

    The line-oriented structure check above protects heading/list cardinality.
    This complementary check makes every prose, link, image, media, and code
    block occupy a stable position so a translation cannot silently omit an
    otherwise unstructured paragraph.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    in_fence = False
    fence_char = ""
    fence_length = 0

    def flush() -> None:
        if current:
            blocks.append(current.copy())
            current.clear()

    for line in markdown_text.splitlines():
        stripped = line.lstrip()
        marker_match = re.match(r"(`{3,}|~{3,})", stripped)
        if in_fence:
            current.append(line)
            if marker_match:
                marker = marker_match.group(1)
                if marker[0] == fence_char and len(marker) >= fence_length:
                    in_fence = False
                    flush()
            continue

        if not stripped:
            flush()
            continue
        if marker_match:
            flush()
            marker = marker_match.group(1)
            in_fence = True
            fence_char = marker[0]
            fence_length = len(marker)
        current.append(line)
    flush()

    tokens: list[str] = []
    for block in blocks:
        first = block[0].lstrip()
        heading = re.match(r"^(#{1,6})\s+", first)
        if first.startswith(("```", "~~~")):
            tokens.append("fenced-code")
        elif heading:
            tokens.append(f"h{len(heading.group(1))}")
        elif re.match(r"^[-+*]\s+", first):
            tokens.append("unordered-list")
        elif re.match(r"^\d+[.)]\s+", first):
            tokens.append("ordered-list")
        elif first.startswith(">"):
            tokens.append("blockquote")
        elif re.fullmatch(r"(?:---+|___+|\*\*\*+)\s*", first):
            tokens.append("thematic-break")
        elif _MARKDOWN_REFERENCE_RE.fullmatch("\n".join(block)):
            tokens.append("markdown-media" if first.startswith("!") else "paragraph")
        elif _RAW_MEDIA_TAG_RE.fullmatch("\n".join(block)):
            tokens.append("raw-media")
        else:
            tokens.append("paragraph")
    return tokens


def _require_chinese_metadata(manifest: Mapping[str, Any], field: str) -> None:
    value = manifest.get(field)
    if not isinstance(value, str) or not _CJK_RE.search(value):
        raise TranslationError(f"{field} must be written in Chinese")


def _require_chinese_body(body: str) -> None:
    prose = "\n".join(
        line for block in re.split(r"(?:```|~~~).*?(?:```|~~~)", body, flags=re.DOTALL)
        for line in block.splitlines()
    )
    prose = _URL_RE.sub("", prose)
    prose = _HTML_TAG_RE.sub("", prose)
    cjk_count = len(_CJK_RE.findall(prose))
    ascii_count = len(_ASCII_LETTER_RE.findall(prose))
    ratio = cjk_count / max(cjk_count + ascii_count, 1)
    if cjk_count < 20 or ratio < 0.2:
        raise TranslationError(
            "translated article body must be predominantly Chinese prose"
        )


def validate_article_translation(
    manifest: Mapping[str, Any], source_body: str, translated_body: str
) -> str:
    """Return a validated Chinese body that preserves source structure and assets."""
    translated_body = translated_body.strip()
    if not translated_body:
        raise TranslationError("translated article body must not be empty")
    _require_chinese_metadata(manifest, "title")
    _require_chinese_metadata(manifest, "summary")
    _require_chinese_body(translated_body)

    checks = (
        ("Markdown links and images", _markdown_references),
        ("raw HTML references", _html_references),
        ("raw media elements", lambda value: _RAW_MEDIA_TAG_RE.findall(value)),
        ("Markdown blocks", _markdown_blocks),
        ("Markdown structure", _structure),
        ("fenced code blocks", _fenced_code_blocks),
    )
    for label, extractor in checks:
        if extractor(source_body) != extractor(translated_body):
            raise TranslationError(
                f"translated article must preserve source {label} in order"
            )
    return translated_body

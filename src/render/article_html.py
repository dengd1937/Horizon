"""Convert X Article draft.js content_state into HTML / plain text.

Pure functions, no I/O. Input quirks handled here (verified on captured
fixtures):
- entityMap arrives as a list of {key, value} rather than a dict;
- inline style names are capitalized ("Bold") instead of draft.js "BOLD";
- range offsets/lengths count UTF-16 code units, so emoji-containing text
  must be sliced via UTF-16 index mapping, not Python code points.
"""

import html as html_lib
import json
from bisect import bisect_right
from typing import Callable, Optional

_STYLE_TAGS = {"BOLD": "strong", "ITALIC": "em", "CODE": "code", "STRIKETHROUGH": "s"}
_HEADER_TAGS = {"header-one": "h2", "header-two": "h3", "header-three": "h4"}
_SAFE_LINK_SCHEMES = ("http://", "https://")

AssetResolver = Callable[[str], str]


def normalize_entity_map(entity_map) -> dict[str, dict]:
    """Accept both dict and list-of-{key,value} entityMap shapes."""
    if isinstance(entity_map, dict):
        return {str(k): v for k, v in entity_map.items() if isinstance(v, dict)}
    out: dict[str, dict] = {}
    for entry in entity_map or []:
        if isinstance(entry, dict) and isinstance(entry.get("value"), dict):
            out[str(entry.get("key"))] = entry["value"]
    return out


def simplify_media_entities(raw_entities: list) -> list[dict]:
    """Reduce raw article media_entities to {media_id, url, width, height}."""
    out: list[dict] = []
    for ent in raw_entities or []:
        info = (ent or {}).get("media_info") or {}
        url = info.get("original_img_url", "")
        if not url:
            continue
        out.append(
            {
                "media_id": str(ent.get("media_id", "")),
                "url": url,
                "width": info.get("original_img_width", 0),
                "height": info.get("original_img_height", 0),
            }
        )
    return out


def extract_cover_url(cover_media: dict) -> str:
    return ((cover_media or {}).get("media_info") or {}).get("original_img_url", "")


def _parse_content_state(article: dict) -> dict:
    cs = article.get("content_state") or {}
    if isinstance(cs, str):
        try:
            cs = json.loads(cs)
        except (ValueError, TypeError):
            return {}
    return cs if isinstance(cs, dict) else {}


def _utf16_offsets(text: str) -> list[int]:
    """Prefix sums: offsets[i] is the UTF-16 offset of code point i."""
    offsets = [0]
    for ch in text:
        offsets.append(offsets[-1] + (1 if ord(ch) <= 0xFFFF else 2))
    return offsets


def _render_inline(
    text: str,
    inline_ranges: list,
    entity_ranges: list,
    entities: dict[str, dict],
) -> str:
    """Escape text and apply style/link ranges (UTF-16 offsets)."""
    if not text:
        return ""

    offsets = _utf16_offsets(text)
    total16 = offsets[-1]
    bounds = {0, total16}
    spans: list[tuple[str, str, int, int]] = []

    for r in inline_ranges or []:
        start, length = r.get("offset", 0), r.get("length", 0)
        tag = _STYLE_TAGS.get(str(r.get("style", "")).upper())
        if tag and length > 0:
            end = min(start + length, total16)
            spans.append(("style", tag, start, end))
            bounds |= {start, end}

    for r in entity_ranges or []:
        start, length = r.get("offset", 0), r.get("length", 0)
        entity = entities.get(str(r.get("key", ""))) or {}
        url = ((entity.get("data") or {}).get("url") or "").strip()
        if (
            length > 0
            and str(entity.get("type", "")).upper() == "LINK"
            and url.startswith(_SAFE_LINK_SCHEMES)
        ):
            end = min(start + length, total16)
            spans.append(("link", url, start, end))
            bounds |= {start, end}

    def to_py(idx16: int) -> int:
        return bisect_right(offsets, min(max(idx16, 0), total16)) - 1

    cuts = sorted(bounds)
    parts: list[str] = []
    for seg_start, seg_end in zip(cuts, cuts[1:]):
        segment = text[to_py(seg_start):to_py(seg_end)]
        if not segment:
            continue
        piece = html_lib.escape(segment)
        for kind, value, start, end in spans:
            if kind == "style" and start <= seg_start and seg_end <= end:
                piece = f"<{value}>{piece}</{value}>"
        for kind, value, start, end in spans:
            if kind == "link" and start <= seg_start and seg_end <= end:
                href = html_lib.escape(value, quote=True)
                piece = f'<a href="{href}">{piece}</a>'
                break
        parts.append(piece)
    return "".join(parts)


def _render_atomic(
    block: dict,
    entities: dict[str, dict],
    media_by_id: dict[str, dict],
    resolver: AssetResolver,
) -> str:
    for entity_range in block.get("entityRanges") or []:
        entity = entities.get(str(entity_range.get("key", ""))) or {}
        for item in ((entity.get("data") or {}).get("mediaItems") or []):
            media = media_by_id.get(str(item.get("mediaId", "")))
            if not media or not media.get("url"):
                continue
            src = html_lib.escape(resolver(media["url"]), quote=True)
            size = ""
            if media.get("width") and media.get("height"):
                size = f' width="{media["width"]}" height="{media["height"]}"'
            return f'<figure><img src="{src}" alt=""{size} loading="lazy"></figure>'
    return ""


def article_to_html(
    article: dict, asset_resolver: Optional[AssetResolver] = None
) -> str:
    """Render an article's content_state to an HTML fragment.

    asset_resolver maps remote media URLs to their final src (e.g. a local
    assets path once the media downloader has run); defaults to identity.
    """
    content_state = _parse_content_state(article)
    blocks = content_state.get("blocks") or []
    entities = normalize_entity_map(content_state.get("entityMap"))
    media_by_id = {
        str(m.get("media_id", "")): m for m in article.get("media_entities") or []
    }
    resolver = asset_resolver or (lambda url: url)

    out: list[str] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        btype = block.get("type", "unstyled")

        if btype in ("unordered-list-item", "ordered-list-item"):
            tag = "ul" if btype == "unordered-list-item" else "ol"
            items = []
            while i < len(blocks) and blocks[i].get("type") == btype:
                b = blocks[i]
                items.append(
                    "<li>"
                    + _render_inline(
                        b.get("text", ""),
                        b.get("inlineStyleRanges"),
                        b.get("entityRanges"),
                        entities,
                    )
                    + "</li>"
                )
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue

        if btype == "code-block":
            lines = []
            while i < len(blocks) and blocks[i].get("type") == "code-block":
                lines.append(html_lib.escape(blocks[i].get("text", "")))
                i += 1
            out.append("<pre><code>" + "\n".join(lines) + "</code></pre>")
            continue

        if btype == "atomic":
            figure = _render_atomic(block, entities, media_by_id, resolver)
            if figure:
                out.append(figure)
            i += 1
            continue

        text = block.get("text", "")
        inner = _render_inline(
            text, block.get("inlineStyleRanges"), block.get("entityRanges"), entities
        )
        if btype in _HEADER_TAGS:
            tag = _HEADER_TAGS[btype]
            out.append(f"<{tag}>{inner}</{tag}>")
        elif btype == "blockquote":
            out.append(f"<blockquote>{inner}</blockquote>")
        elif text.strip():
            out.append(f"<p>{inner}</p>")
        i += 1

    return "\n".join(out)


def article_to_text(article: dict) -> str:
    """Plain-text body (headings and paragraphs) for AI consumption."""
    content_state = _parse_content_state(article)
    parts = []
    for block in content_state.get("blocks") or []:
        if block.get("type") == "atomic":
            continue
        text = (block.get("text") or "").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)

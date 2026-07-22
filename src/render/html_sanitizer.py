"""Allowlist sanitizer for HTML generated from untrusted Markdown."""

import ipaddress
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

_ALLOWED_TAGS = {
    "a",
    "annotation",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "img",
    "li",
    "math",
    "mfrac",
    "mi",
    "mn",
    "mo",
    "mover",
    "mpadded",
    "mroot",
    "mrow",
    "mspace",
    "msqrt",
    "mstyle",
    "msub",
    "msubsup",
    "msup",
    "mtable",
    "mtd",
    "mtext",
    "mtr",
    "munder",
    "munderover",
    "ol",
    "p",
    "pre",
    "semantics",
    "source",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
    "video",
}
_DROP_WITH_CONTENT = {
    "applet",
    "embed",
    "form",
    "iframe",
    "input",
    "noscript",
    "object",
    "script",
    "style",
    "svg",
    "template",
}
_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "annotation": {"encoding"},
    "img": {"alt", "loading", "src", "title"},
    "math": {"display", "xmlns"},
    "mo": {"accent", "fence", "form", "lspace", "rspace", "separator", "stretchy"},
    "mover": {"accent"},
    "mpadded": {"depth", "height", "lspace", "voffset", "width"},
    "mspace": {"depth", "height", "linebreak", "width"},
    "mstyle": {"displaystyle", "scriptlevel"},
    "mtd": {"columnalign", "columnspan", "rowalign", "rowspan"},
    "mtable": {"columnalign", "columnspacing", "rowalign", "rowspacing"},
    "munder": {"accentunder"},
    "source": {"src", "type"},
    "video": {
        "autoplay",
        "controls",
        "loop",
        "muted",
        "playsinline",
        "poster",
        "preload",
        "src",
    },
}
_URI_ATTRIBUTES = {"href", "poster", "src"}


def _safe_uri(value: str, *, media: bool) -> bool:
    value = value.strip()
    if not value:
        return False
    if value.startswith("#") and not media:
        return True
    if value.startswith(("../assets/", "assets/")):
        return media
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return False
    return parsed.scheme == "https" if media else True


def sanitize_html_fragment(fragment: str) -> str:
    """Remove executable markup while retaining article prose and HTTPS media."""
    soup = BeautifulSoup(fragment, "html.parser")
    for node in list(soup.find_all(True)):
        if node.name in _DROP_WITH_CONTENT:
            node.decompose()
            continue
        if node.name not in _ALLOWED_TAGS:
            node.unwrap()
            continue

        allowed = _ALLOWED_ATTRIBUTES.get(node.name, set())
        for attribute in list(node.attrs):
            if attribute not in allowed:
                del node.attrs[attribute]
                continue
            if attribute in _URI_ATTRIBUTES:
                raw_value = node.attrs.get(attribute)
                value = raw_value[0] if isinstance(raw_value, list) else raw_value
                is_media = node.name in {"img", "source", "video"}
                if not isinstance(value, str) or not _safe_uri(
                    value, media=is_media
                ):
                    del node.attrs[attribute]

        if node.name == "a" and node.get("href"):
            node["rel"] = "noopener noreferrer"
        if node.name == "img":
            node["loading"] = "lazy"

    return "".join(str(child) for child in soup.contents)

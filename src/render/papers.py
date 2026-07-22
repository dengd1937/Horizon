"""Render high-density research-paper close reads as static HTML pages."""

import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

import markdown
from bs4 import BeautifulSoup, Tag
from latex2mathml import converter as latex_converter

from ..papers.contract import ResearchPaper
from .html_sanitizer import sanitize_html_fragment
from .paper_index_js import PAPER_INDEX_JS
from .site_css import SITE_CSS

_e = html.escape
_BLOCK_MATH_RE = re.compile(r"(?<!\\)\$\$\s*(.+?)\s*\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?!\$)([^$\n]+?)(?<!\\)\$")
_NUMBERED_HEADING_RE = re.compile(r"^\d+\.\s*")
_PAPER_INDEX_JS_VERSION = hashlib.sha256(PAPER_INDEX_JS.encode("utf-8")).hexdigest()[:8]


def _plain_heading(text: str) -> str:
    return _NUMBERED_HEADING_RE.sub("", text.strip())


def _protect_math(md: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}

    def replace(expression: str, *, display: str) -> str:
        token = f"HORIZONPAPERMATH{len(replacements)}TOKEN"
        replacements[token] = latex_converter.convert(expression.strip(), display=display)
        return token

    protected = _BLOCK_MATH_RE.sub(
        lambda match: replace(match.group(1), display="block"), md
    )
    protected = _INLINE_MATH_RE.sub(
        lambda match: replace(match.group(1), display="inline"), protected
    )
    return protected, replacements


def _assign_heading_ids(soup: BeautifulSoup) -> list[tuple[str, str]]:
    toc: list[tuple[str, str]] = []
    for index, heading in enumerate(soup.find_all("h2"), start=1):
        heading_id = f"paper-section-{index}"
        heading["id"] = heading_id
        toc.append((heading_id, heading.get_text(" ", strip=True)))
    return toc


def _wrap_section(soup: BeautifulSoup, heading: Tag, class_name: str) -> None:
    section = soup.new_tag("section")
    section["class"] = class_name
    heading.insert_before(section)
    node: Tag | None = heading
    while node is not None:
        following = node.next_sibling
        if node is not heading and isinstance(node, Tag) and node.name == "h2":
            break
        section.append(node.extract())
        node = following if isinstance(following, Tag) else following  # type: ignore[assignment]


def render_paper_markdown(md: str) -> tuple[str, list[tuple[str, str]]]:
    """Render paper Markdown with tables and static MathML, then add page semantics."""
    protected, math_fragments = _protect_math(md)
    rendered = markdown.markdown(
        protected,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    for token, mathml in math_fragments.items():
        rendered = rendered.replace(token, mathml)
    soup = BeautifulSoup(sanitize_html_fragment(rendered), "html.parser")

    for math_node in soup.find_all("math"):
        display = math_node.get("display") == "block"
        math_node["class"] = "math-block" if display else "math-inline"
        parent = math_node.parent
        if display and isinstance(parent, Tag) and parent.name == "p":
            siblings = [child for child in parent.children if str(child).strip()]
            if len(siblings) == 1:
                parent.unwrap()
        if display:
            wrapper = soup.new_tag("div")
            wrapper["class"] = "paper-math-wrap"
            math_node.wrap(wrapper)

    for table in soup.find_all("table"):
        for header in table.find_all("th"):
            header["scope"] = "col"
        wrapper = soup.new_tag("div")
        wrapper["class"] = "paper-table-wrap"
        table.wrap(wrapper)

    toc = _assign_heading_ids(soup)
    for heading in list(soup.find_all("h2")):
        title = _plain_heading(heading.get_text(" ", strip=True))
        if title.startswith("论文结论与证据边界"):
            _wrap_section(soup, heading, "paper-evidence")
        elif title.startswith("AI 解读"):
            _wrap_section(soup, heading, "paper-ai")

    return "".join(str(child) for child in soup.contents), toc


def _resource_link(label: str, url: str) -> str:
    return f'<a class="paper-resource" href="{_e(url)}">{_e(label)} ↗</a>'


def _toc_html(toc: Iterable[tuple[str, str]]) -> str:
    items = "".join(
        f'<li><a href="#{_e(anchor)}">{_e(title)}</a></li>' for anchor, title in toc
    )
    return (
        '<aside class="paper-toc" aria-label="论文目录">'
        '<details class="paper-toc-details" open>'
        '<summary class="paper-toc-title">本页目录</summary>'
        f"<ol>{items}</ol>"
        '<a class="paper-toc-top" href="#paper-top">回到顶部 ↑</a>'
        "</details>"
        "</aside>"
    )


def paper_index_page_html(papers: list[ResearchPaper]) -> str:
    """Render the searchable, filterable paper-library index."""
    tag_counts: Counter[str] = Counter()
    for paper in papers:
        tag_counts.update(paper.tags)
    filter_tags = sorted(
        tag_counts.items(),
        key=lambda item: (-item[1], item[0].casefold(), item[0]),
    )

    entries = []
    for paper in papers:
        tags_json = json.dumps(
            paper.tags, ensure_ascii=False, separators=(",", ":")
        )
        authors = " · ".join(paper.authors)
        search_text = " ".join(
            [paper.title, paper.original_title, *paper.authors, *paper.tags]
        )
        facts = []
        if paper.models:
            facts.append("模型 " + " · ".join(paper.models))
        if paper.benchmarks:
            facts.append("基准 " + " · ".join(paper.benchmarks))
        entries.append(
            f'<a class="paper-index-entry" data-paper-entry '
            f'data-tags="{_e(tags_json)}" data-search="{_e(search_text)}" '
            f'href="{_e(paper.slug)}.html">'
            '<span class="paper-index-kicker">'
            f'<span>{_e(paper.venue)} · {paper.publication_year}</span>'
            f'<span>入库 {_e(paper.added_date)}</span>'
            "</span>"
            f'<span class="paper-index-title">{_e(paper.title)}</span>'
            f'<span class="paper-index-original" lang="en">{_e(paper.original_title)}</span>'
            f'<span class="paper-index-authors">{_e(authors)}</span>'
            f'<span class="paper-index-summary">{_e(paper.summary)}</span>'
            + (
                '<span class="paper-index-facts">'
                + "".join(f"<span>{_e(fact)}</span>" for fact in facts)
                + "</span>"
                if facts
                else ""
            )
            + '<span class="paper-index-tags">'
            + "".join(f"<span>#{_e(tag)}</span>" for tag in paper.tags)
            + "</span>"
            + '<span class="paper-index-cta">阅读全文 →</span>'
            + "</a>"
        )

    controls = ""
    filtered_empty = ""
    script = ""
    script_policy = "'none'"
    if papers:
        tag_buttons = [
            '<button class="idx-tag" type="button" data-paper-tag data-tag="" '
            f'aria-pressed="true">全部 <span>{len(papers)}</span></button>'
        ]
        tag_buttons.extend(
            '<button class="idx-tag" type="button" data-paper-tag '
            f'data-tag="{_e(tag)}" aria-pressed="false">'
            f'{_e(tag)} <span>{count}</span></button>'
            for tag, count in filter_tags
        )
        controls = (
            '<section class="idx-tools paper-index-tools" data-paper-filter hidden '
            'aria-label="论文搜索与筛选">'
            '<div class="paper-index-control-row">'
            '<label class="visually-hidden" for="paper-search">搜索论文</label>'
            '<input class="idx-search" id="paper-search" type="search" '
            'data-paper-search autocomplete="off" spellcheck="false" '
            'aria-controls="paper-list" '
            'placeholder="搜索标题、作者或标签……">'
            '<button class="idx-reset" type="button" data-paper-reset hidden>重置</button>'
            "</div>"
            '<div class="idx-tags" role="group" aria-label="按论文标签筛选">'
            + "".join(tag_buttons)
            + "</div>"
            f'<p class="idx-results" data-paper-results aria-live="polite" '
            f'aria-atomic="true">共 {len(papers)} 篇论文</p>'
            "</section>"
        )
        filtered_empty = (
            '<p class="idx-empty" data-paper-empty hidden>'
            "没有找到符合条件的论文。</p>"
        )
        script = (
            f'<script defer src="paper-index.js?v={_PAPER_INDEX_JS_VERSION}"></script>'
        )
        script_policy = "'self'"

    body = (
        '<main class="paper-index" data-paper-library>'
        '<div class="art-top"><span class="brand">HORIZON · 论文精读</span>'
        '<span class="paper-top-links">'
        '<a href="../daily/index.html">日报</a>'
        '<a href="../articles/index.html">文章库</a>'
        "</span></div>"
        '<header class="paper-index-head">'
        '<p class="paper-index-eyebrow">RESEARCH LIBRARY · EVIDENCE FIRST</p>'
        '<h1 class="idx-title">论文库</h1>'
        "</header>"
        + controls
        + (
            '<div class="paper-index-list" id="paper-list" data-paper-list>'
            + "".join(entries)
            + "</div>"
            if entries
            else '<p class="empty">暂无论文。</p>'
        )
        + filtered_empty
        + "</main>"
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; img-src \'self\' https: data:; '
        'style-src \'unsafe-inline\'; '
        f'script-src {script_policy}; base-uri \'none\'; form-action \'none\'">\n'
        '<link rel="icon" href="data:,">\n'
        '<meta name="description" content="Horizon 论文精读库：论文结论、证据边界与 AI 解读。">\n'
        f"<title>Horizon · 论文库</title>\n<style>{SITE_CSS}</style>{script}\n</head>\n"
        f'<body>\n<div class="wrap paper-index-page">\n{body}\n</div>\n</body>\n</html>\n'
    )
def paper_detail_page_html(paper: ResearchPaper) -> str:
    body_html, toc = render_paper_markdown(paper.body_md)
    resources = [
        _resource_link("论文页面", paper.paper_url),
        _resource_link("PDF", paper.pdf_url),
    ]
    if paper.project_url:
        resources.append(_resource_link("项目主页", paper.project_url))
    if paper.code_url:
        resources.append(_resource_link("代码", paper.code_url))
    if paper.data_url:
        resources.append(_resource_link("数据", paper.data_url))

    identifiers = []
    if paper.arxiv_id:
        identifiers.append(f"arXiv:{_e(paper.arxiv_id)}")
    if paper.doi:
        identifiers.append(
            f'<a href="https://doi.org/{_e(paper.doi)}">DOI {_e(paper.doi)}</a>'
        )

    dates = []
    if paper.submitted_date:
        dates.append(f"首次提交 {_e(paper.submitted_date)}")
    if paper.revised_date:
        dates.append(f"精读版本 {_e(paper.revised_date)}")
    dates.append(f"入库 {_e(paper.added_date)}")

    license_label = _e(paper.paper_license)
    if paper.paper_license_url:
        license_label = (
            f'<a href="{_e(paper.paper_license_url)}">{license_label}</a>'
        )
    code_license = (
        f" · 代码许可 {_e(paper.code_license)}" if paper.code_license else ""
    )

    facts = []
    if paper.models:
        facts.append(
            '<div><dt>实验模型</dt><dd>'
            + " · ".join(_e(model) for model in paper.models)
            + "</dd></div>"
        )
    if paper.benchmarks:
        facts.append(
            '<div><dt>任务基准</dt><dd>'
            + " · ".join(_e(benchmark) for benchmark in paper.benchmarks)
            + "</dd></div>"
        )

    page_body = (
        '<header class="paper-head" id="paper-top">'
        '<div class="art-top"><span class="brand">HORIZON · 论文精读</span>'
        '<span class="paper-top-links">'
        '<a href="../daily/index.html">日报</a>'
        '<a href="../articles/index.html">文章库</a>'
        '<a href="index.html">论文库</a>'
        "</span></div>"
        f'<p class="paper-kicker">{_e(paper.venue)} · {paper.publication_year}</p>'
        f'<h1 class="paper-title">{_e(paper.title)}</h1>'
        f'<p class="paper-original" lang="en">{_e(paper.original_title)}</p>'
        f'<p class="paper-authors">{" · ".join(_e(author) for author in paper.authors)}</p>'
        + (
            f'<p class="paper-affiliations">{" · ".join(_e(item) for item in paper.affiliations)}</p>'
            if paper.affiliations
            else ""
        )
        + '<div class="paper-meta">'
        + "".join(f"<span>{item}</span>" for item in identifiers)
        + "".join(f"<span>{item}</span>" for item in dates)
        + "</div>"
        + '<div class="paper-resources">'
        + "".join(resources)
        + "</div>"
        + f'<p class="paper-license">论文许可 {license_label}{code_license}。'
        "本文为中文重述与 AI 分析，不代表原作者背书。</p>"
        + '<div class="paper-tags">'
        + "".join(f"<span>#{_e(tag)}</span>" for tag in paper.tags)
        + "</div>"
        + (f'<dl class="paper-facts">{"".join(facts)}</dl>' if facts else "")
        + "</header>"
        + '<div class="paper-layout">'
        + _toc_html(toc)
        + f'<main class="prose paper-prose">{body_html}</main>'
        + "</div>"
        + '<footer class="paper-footer">'
        '<a href="index.html">← 论文库</a>'
        '<a href="#paper-top">回到顶部 ↑</a>'
        '<span>Horizon Paper Close Read · v0</span>'
        "</footer>"
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; img-src \'self\' https: data:; '
        'media-src \'self\' https:; style-src \'unsafe-inline\'; '
        'script-src \'none\'; base-uri \'none\'; form-action \'none\'">\n'
        '<link rel="icon" href="data:,">\n'
        f'<meta name="description" content="{_e(paper.summary)}">\n'
        f"<title>{_e(paper.title)} · Horizon 论文精读</title>\n"
        f"<style>{SITE_CSS}</style>\n</head>\n"
        f'<body>\n<div class="wrap paper-page">\n{page_body}\n</div>\n</body>\n</html>\n'
    )


def render_papers(out_dir: Path, papers: list[ResearchPaper]) -> list[Path]:
    """Render the paper-library index and detail pages under ``out_dir/papers/``."""
    paper_dir = out_dir / "papers"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper-index.js").write_text(PAPER_INDEX_JS, encoding="utf-8")
    index_path = paper_dir / "index.html"
    index_path.write_text(paper_index_page_html(papers), encoding="utf-8")
    paths = [index_path]
    for paper in papers:
        path = paper_dir / f"{paper.slug}.html"
        path.write_text(paper_detail_page_html(paper), encoding="utf-8")
        paths.append(path)
    return paths

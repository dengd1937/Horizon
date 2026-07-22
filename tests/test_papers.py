"""Tests for the paper close-read contract, library index, and detail renderer."""

from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.papers.contract import (
    PaperValidationError,
    load_paper,
    load_papers,
    parse_paper_text,
)
from src.render.papers import (
    paper_detail_page_html,
    paper_index_page_html,
    render_paper_markdown,
    render_papers,
)

PROJECT_ROOT = Path(__file__).parents[1]
PAPERS = PROJECT_ROOT / "papers"
REACT = PAPERS / "yao-2022-react-synergizing-reasoning-acting.md"
SELF_INSTRUCT = PAPERS / "wang-2023-self-instruct-self-generated-instructions.md"


def test_react_source_parses_all_v0_fields():
    paper = load_paper(REACT)

    assert paper.title == "ReAct：在语言模型中协同推理与行动"
    assert paper.original_title == "ReAct: Synergizing Reasoning and Acting in Language Models"
    assert paper.publication_year == 2023
    assert paper.venue == "ICLR 2023"
    assert paper.arxiv_id == "2210.03629"
    assert paper.submitted_date == "2022-10-06"
    assert paper.revised_date == "2023-03-10"
    assert paper.paper_license == "CC BY 4.0"
    assert paper.code_license == "MIT"
    assert len(paper.authors) == 7
    assert paper.tags == ["智能体", "推理与行动", "工具使用", "提示学习"]
    assert paper.benchmarks == ["HotpotQA", "FEVER", "ALFWorld", "WebShop"]
    assert "## 8. AI 解读" in paper.body_md
    assert "复现清单" not in paper.body_md
    assert "Horizon 解读" not in paper.body_md


def test_load_papers_returns_formal_sources():
    papers = load_papers(PAPERS)
    assert [paper.slug for paper in papers] == [
        "hsieh-2024-ruler-real-context-size-long-context-models",
        "wang-2023-self-instruct-self-generated-instructions",
        "yao-2022-react-synergizing-reasoning-acting",
    ]


def test_self_instruct_source_preserves_quality_and_evidence_boundaries():
    paper = load_paper(SELF_INSTRUCT)

    assert paper.title == "Self-Instruct：用模型自生成指令完成指令微调"
    assert paper.venue == "ACL 2023"
    assert paper.arxiv_id == "2212.10560"
    assert paper.doi == "10.18653/v1/2023.acl-long.754"
    assert paper.paper_license == "CC BY 4.0"
    assert paper.code_license == "Apache-2.0"
    assert paper.data_url == "https://github.com/yizhongw/self-instruct/tree/main/data"
    assert paper.benchmarks == [
        "Super-NaturalInstructions",
        "Self-Instruct User-Oriented Instructions",
    ]
    assert "52,445" in paper.body_md
    assert "54%" in paper.body_md
    assert "10 个百分点" in paper.body_md
    assert "## 7. 论文结论与证据边界" in paper.body_md
    assert "## 8. AI 解读" in paper.body_md
    assert "复现清单" not in paper.body_md
    assert "Horizon 解读" not in paper.body_md

    html_ = paper_detail_page_html(paper)
    soup = BeautifulSoup(html_, "html.parser")
    assert soup.select_one(
        '.paper-resource[href="https://github.com/yizhongw/self-instruct/tree/main/data"]'
    ).get_text(strip=True) == "数据 ↗"


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ('pdf_url: "https://arxiv.org/pdf/2210.03629"', 'pdf_url: "http://example.com/p.pdf"', "pdf_url"),
        ('arxiv_id: "2210.03629"', 'arxiv_id: "not-an-arxiv-id"', "arxiv_id"),
        ('doi: "10.48550/arXiv.2210.03629"', 'doi: "not-a-doi"', "DOI"),
        ('revised_date: "2023-03-10"', 'revised_date: "2021-03-10"', "revised_date"),
    ],
)
def test_paper_contract_rejects_invalid_metadata(old, new, expected):
    source = REACT.read_text(encoding="utf-8").replace(old, new)
    with pytest.raises(PaperValidationError, match=expected):
        parse_paper_text(source, REACT)


def test_paper_contract_requires_analysis_layers():
    source = REACT.read_text(encoding="utf-8").replace(
        "## 8. AI 解读：这篇论文真正留下了什么",
        "## 8. 延伸阅读",
    )
    with pytest.raises(PaperValidationError, match="AI 解读"):
        parse_paper_text(source, REACT)


def test_paper_contract_rejects_body_h1():
    source = REACT.read_text(encoding="utf-8").replace(
        "## 一句话结论", "# 重复页面标题\n\n## 一句话结论", 1
    )
    with pytest.raises(PaperValidationError, match="must not contain an H1"):
        parse_paper_text(source, REACT)


def test_paper_markdown_renders_static_mathml_tables_and_layers():
    paper = load_paper(REACT)
    html_, toc = render_paper_markdown(paper.body_md)
    soup = BeautifulSoup(html_, "html.parser")

    assert len(toc) == 12
    assert toc[0][1] == "一句话结论"
    assert len(soup.select(".paper-table-wrap > table")) == 8
    assert soup.select(".paper-table-wrap th[scope=col]")
    assert len(soup.select(".paper-math-wrap > math.math-block")) == 3
    assert soup.select_one("math.math-inline") is not None
    assert soup.select_one("section.paper-evidence") is not None
    assert soup.select_one("section.paper-ai") is not None
    assert "HORIZONPAPERMATH" not in html_
    assert "<script" not in html_


def test_self_instruct_markdown_renders_dense_data_sections():
    paper = load_paper(SELF_INSTRUCT)
    html_, toc = render_paper_markdown(paper.body_md)
    soup = BeautifulSoup(html_, "html.parser")

    assert len(toc) == 12
    assert len(soup.select(".paper-table-wrap > table")) == 10
    assert len(soup.select("math")) == 10
    assert soup.select_one("section.paper-evidence") is not None
    assert soup.select_one("section.paper-ai") is not None
    assert "HORIZONPAPERMATH" not in html_
    assert "<script" not in html_


def test_paper_detail_page_exposes_resources_attribution_and_toc():
    paper = load_paper(REACT)
    html_ = paper_detail_page_html(paper)
    soup = BeautifulSoup(html_, "html.parser")

    assert soup.select_one("h1.paper-title").get_text(strip=True) == paper.title
    assert soup.select_one(".paper-original").get_text(strip=True) == paper.original_title
    assert len(soup.select(".paper-authors")) == 1
    assert len(soup.select(".paper-resource")) == 4
    assert soup.select_one('.paper-resource[href="https://arxiv.org/pdf/2210.03629"]')
    assert "论文许可 CC BY 4.0" in soup.select_one(".paper-license").get_text(" ", strip=True)
    assert "代码许可 MIT" in soup.select_one(".paper-license").get_text(" ", strip=True)
    assert "不代表原作者背书" in soup.select_one(".paper-license").get_text(strip=True)
    assert len(soup.select(".paper-toc li")) == 12
    toc_details = soup.select_one(".paper-toc > details.paper-toc-details")
    assert toc_details is not None
    assert toc_details.has_attr("open")
    assert toc_details.select_one("summary.paper-toc-title").get_text(strip=True) == "本页目录"
    assert soup.select_one('.paper-top-links a[href="index.html"]').get_text(
        strip=True
    ) == "论文库"
    assert soup.select_one('.paper-footer a[href="index.html"]') is not None
    assert "script-src 'none'" in soup.select_one(
        'meta[http-equiv="Content-Security-Policy"]'
    )["content"]


def test_paper_markdown_still_sanitizes_untrusted_html():
    paper = load_paper(REACT)
    unsafe = replace(
        paper,
        body_md=paper.body_md
        + '\n\n<script>alert(1)</script>\n\n[坏链接](javascript:alert(1))',
    )
    html_ = paper_detail_page_html(unsafe)

    assert "<script" not in html_
    assert "javascript:" not in html_


def test_paper_index_renders_title_author_tag_search_and_filters():
    papers = load_papers(PAPERS)
    html_ = paper_index_page_html(papers)
    soup = BeautifulSoup(html_, "html.parser")

    assert soup.select_one("[data-paper-library]") is not None
    assert soup.select_one(".paper-index-overview") is None
    assert "已收录" not in soup.get_text()
    assert "主题标签" not in soup.get_text()
    assert "逐篇精读" not in soup.get_text()
    controls = soup.select_one("[data-paper-filter]")
    assert controls is not None and controls.has_attr("hidden")
    search = soup.select_one('input[type="search"][data-paper-search]')
    assert search is not None
    assert search["placeholder"] == "搜索标题、作者或标签……"
    assert soup.select_one("[data-paper-sort]") is None
    assert soup.select_one("[data-paper-reset]").has_attr("hidden")
    assert soup.select_one("[data-paper-results]").get_text(
        strip=True
    ) == f"共 {len(papers)} 篇论文"

    entries = soup.select("[data-paper-entry]")
    assert len(entries) == len(papers)
    for entry, paper in zip(entries, papers):
        assert entry["href"] == f"{paper.slug}.html"
        search_text = entry["data-search"]
        assert paper.title in search_text
        assert paper.original_title in search_text
        assert all(author in search_text for author in paper.authors)
        assert all(tag in search_text for tag in paper.tags)
        assert paper.summary not in search_text
        assert all(model not in search_text for model in paper.models)
        assert entry.select_one(".paper-index-summary").get_text(strip=True) == paper.summary

    buttons = soup.select("[data-paper-tag]")
    assert buttons[0].get_text(" ", strip=True) == f"全部 {len(papers)}"
    assert {button["data-tag"] for button in buttons[1:]} == {
        tag for paper in papers for tag in paper.tags
    }
    script = soup.select_one('script[src^="paper-index.js?v="][defer]')
    assert script is not None
    csp = soup.select_one('meta[http-equiv="Content-Security-Policy"]')["content"]
    assert "script-src 'self'" in csp


def test_paper_index_empty_state_has_no_active_script():
    html_ = paper_index_page_html([])
    soup = BeautifulSoup(html_, "html.parser")

    assert "暂无论文" in soup.get_text()
    assert soup.select_one("[data-paper-filter]") is None
    assert soup.select_one('script[src="paper-index.js"]') is None
    assert "script-src 'none'" in soup.select_one(
        'meta[http-equiv="Content-Security-Policy"]'
    )["content"]


def test_render_papers_writes_index_script_and_detail_pages(tmp_path):
    papers = load_papers(PAPERS)
    paths = render_papers(tmp_path, papers)
    paper_dir = tmp_path / "papers"
    expected = [paper_dir / "index.html"] + [
        paper_dir / f"{paper.slug}.html" for paper in papers
    ]

    assert paths == expected
    assert all(path.is_file() for path in expected)
    assert all(
        "AI 解读" in path.read_text(encoding="utf-8") for path in expected[1:]
    )
    script = paper_dir / "paper-index.js"
    assert script.is_file()
    assert "data-paper-entry" in script.read_text(encoding="utf-8")

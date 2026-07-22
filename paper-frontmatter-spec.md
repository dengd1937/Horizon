# 论文精读源文件契约 v0

Horizon 的论文模块扫描 `papers/*.md`，生成 `/papers/index.html` 论文库与 `/papers/{slug}.html` 单篇精读页。v0 已用于 ReAct 与 Self-Instruct 两种不同论文结构；列表页支持标题、作者和标签搜索以及标签筛选。

## 文件结构

每篇论文使用一个 YAML frontmatter + Markdown 文件：

```yaml
---
title: 中文标题
original_title: Original Paper Title
slug: author-2026-short-paper-title
authors: [First Author, Second Author]
affiliations: [Example University]
venue: ICLR 2026
publication_year: 2026
paper_url: https://arxiv.org/abs/2601.00001
pdf_url: https://arxiv.org/pdf/2601.00001
project_url: https://example.org/project
code_url: https://github.com/example/project
data_url: https://github.com/example/project/tree/main/data
arxiv_id: '2601.00001'
doi: 10.48550/arXiv.2601.00001
submitted_date: '2026-01-01'
revised_date: '2026-02-01'
added_date: '2026-07-20'
paper_license: CC BY 4.0
paper_license_url: https://creativecommons.org/licenses/by/4.0/
code_license: MIT
summary: 用于未来索引页的一行摘要。
tags: [智能体, 工具使用]
models: [Example Model]
benchmarks: [ExampleBench]
---

## 一句话结论

正文……

## 论文结论与证据边界

正文……

## AI 解读：这篇论文真正留下了什么

> 以下是 AI 基于论文证据作出的延伸分析，不是作者原文结论。
```

## 字段

| 字段 | 必填 | 说明 |
|---|---:|---|
| `title` | 是 | 简体中文标题，详情页主标题 |
| `original_title` | 是 | 论文原始标题 |
| `slug` | 是 | 小写 ASCII 连字符格式，必须与文件名一致 |
| `authors` | 是 | 非空作者列表，保持论文署名顺序 |
| `affiliations` | 否 | 论文列出的机构，去重后按首次出现顺序记录 |
| `venue` | 是 | 会议、期刊或预印本状态，例如 `ICLR 2023` |
| `publication_year` | 是 | 四位发表年份 |
| `paper_url` | 是 | 论文落地页的绝对 HTTPS URL |
| `pdf_url` | 是 | PDF 的绝对 HTTPS URL |
| `project_url` | 否 | 项目主页 |
| `code_url` | 否 | 官方代码仓库 |
| `data_url` | 否 | 官方数据集或数据目录；与代码仓库相同时可省略 |
| `arxiv_id` | 否 | arXiv 标识，可包含版本号 |
| `doi` | 否 | DOI 原始标识，不添加 `https://doi.org/` |
| `submitted_date` | 否 | 首次提交日期，严格 `YYYY-MM-DD` |
| `revised_date` | 否 | 精读依据版本的修订日期，不得早于首次提交 |
| `added_date` | 是 | 入库 UTC 日期，严格 `YYYY-MM-DD` |
| `paper_license` | 是 | 论文文本与图表的许可 |
| `paper_license_url` | 否 | 论文许可说明页 |
| `code_license` | 否 | 代码许可；不得与论文许可合并为一个字段 |
| `summary` | 是 | 非空单行索引摘要 |
| `tags` | 是 | 2–5 个去重标签；受控词表在种子论文稳定后确定 |
| `models` | 否 | 论文实际实验涉及的模型 |
| `benchmarks` | 否 | 论文实际实验涉及的基准或数据集 |

## 正文规则

- frontmatter 提供页面标题，正文不得再包含 H1。
- 正文必须包含“论文结论与证据边界”和“AI 解读”两个 H2。前者描述作者主张及实验支持范围，后者只提供跨章节综合、工程含义、适用条件或潜在误读。
- AI 解读不得伪装成论文结论；页面会对该 section 使用独立视觉样式。
- 数学公式使用 `$...$` 或独占一段的 `$$...$$`，构建时转换为静态 MathML，不依赖浏览器脚本或外部 CDN。
- Markdown 表格用于实验设置和结果；指标、样本量、模型、解码方式、平均值或最佳值等限定条件必须保留。
- 关键判断应注明原论文的 section、table、figure 或 appendix，避免只给二次概括。
- 正文图片只允许绝对 HTTPS URL；媒体本地化将在后续阶段接入。
- 论文版本必须明确。数字来自主文、附录或代码仓库时，应说明各自设置，不得混用。

## 本地精读与入库

项目内的 `horizon-add-paper` Skill 负责从官方论文链接建立证据笔记并生成精读稿。确定稿使用 `horizon-paper` 命令完成校验、隔离预览和本地入库：

```bash
uv run horizon-paper validate --source /tmp/{slug}.md
uv run horizon-paper preview --repo "$PWD" --source /tmp/{slug}.md --preview-root /tmp/{preview}
uv run horizon-paper create --repo "$PWD" --source /tmp/{slug}.md
```

`preview` 不写入正式 `papers/`，`create` 只新增通过契约校验的论文源文件，也不会自动暂存、提交或发布。

## 许可与署名

详情页必须展示作者、原论文链接、论文许可及“中文重述与 AI 分析不代表作者背书”的说明。代码拥有独立许可时单独显示。若论文许可不允许改编或图表再发布，入库前必须调整内容范围，不能由通用模板静默处理。

## v0 明确不包含

- 论文邮件推送
- PDF 或图表下载、本地化
- 批量导入论文
- 论文关系图和引用网络

这些能力在更多种子论文验证内容契约后再设计。

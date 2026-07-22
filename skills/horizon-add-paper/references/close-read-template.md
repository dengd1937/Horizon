# Horizon 论文精读模板

Use this as a structural baseline, not a demand that every paper have identical numbered sections. Preserve the paper's real contribution and evidence layout.

## Frontmatter

```yaml
---
title: 中文标题
original_title: Original Paper Title
slug: author-2026-short-title
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
added_date: 'YYYY-MM-DD'
paper_license: CC BY 4.0
paper_license_url: https://creativecommons.org/licenses/by/4.0/
code_license: MIT
summary: 一行中文索引摘要，只陈述论文最重要的机制与结果。
tags: [智能体, 工具使用]
models: [Example Model]
benchmarks: [ExampleBench]
---
```

Omit optional fields instead of guessing. `added_date` is the current UTC admission date. Confirm code and paper licenses separately.

## Recommended body

```markdown
## 一句话结论

用一到两句话说明论文做了什么、为何有效，以及证据覆盖到哪里。

## 摘要译文

忠实翻译原摘要，不加入 AI 判断。

## 论文地图

用短表格说明问题、方法、实验与结论分别位于哪里。

## 1. 研究问题

交代任务、已有方法的缺口、论文假设与贡献声明。

## 2. 方法

解释核心机制、算法、公式、训练或推理流程及必要实现条件。

## 3. 数据与实验设计

列出模型、数据、基准、指标、基线、样本量、解码或评估设置。

## 4. 主要结果

用带限定条件的表格或段落呈现主要比较，并标注 Table/Figure/Section。

## 5. 消融、补充实验与失败案例

保留负面结果、敏感性、附录限定和复现所需条件，但不要写成“复现清单”。

## 6. 论文结论与证据边界

只总结作者结论、直接证据、未被实验覆盖的外推，以及论文自己承认的限制。

## 7. AI 解读：这篇论文真正留下了什么

> 以下是 AI 基于论文证据作出的延伸分析，不是作者原文结论。

给出机制层综合、工程含义、适用条件与常见误读。明确使用“可能”“意味着”或“可以推断”，不要把推断写成论文事实。

## 8. 相关工作坐标

只选择理解这篇论文所必需的相邻方法，并准确说明差异。
```

## Evidence ledger

Keep this in the temporary work directory, not the published paper:

| Claim | Paper location | Setting | Value/comparison | Boundary |
|---|---|---|---|---|
| Method improves task X | §4.2, Table 3 | Model, split, metric | 71.2 vs 65.8 | One dataset; no significance test reported |

Every important number in the draft must map to one ledger row. Record when a value is read from a plot, reported only in an appendix, or taken from the official repository rather than the paper.

# 精华文章源文件契约

Horizon 渲染器扫描 `articles/*.md` 渲染精华文章库（索引页 `/articles/` + 详情页 `/articles/{slug}.html`）。本文档定义源文件格式，作为独立 skill repo（`web-article-clipper`）的产出依据。

## 源文件格式

每篇文章一个文件 `articles/{slug}.md`，由 YAML frontmatter + markdown 正文组成：

~~~
---
title: 文章标题
source_url: https://example.com/post
source_domain: example.com
published_date: 2026-07-01
added_date: 2026-07-08
slug: example-com-20260701-short-title
summary: 一行摘要，用于索引页与邮件本期新增。
tags: [AI, 编译器]
cover: assets/articles/example-com-20260701-short-title/cover.jpg
intro: |
  可选导读，可多行；渲染在原文链与正文之间。
---

正文 markdown 在此……
~~~

## 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 是 | 文章标题 |
| `source_url` | string | 是 | 原文 URL |
| `source_domain` | string | 是 | 来源域名（如 `example.com`） |
| `published_date` | string | 是 | 原文发布日期（ISO `YYYY-MM-DD`） |
| `added_date` | string | 是 | 入库日期（ISO `YYYY-MM-DD`），用于按月分组与邮件「本期新增」 |
| `slug` | string | 是 | 文件名与 URL slug，全库唯一 |
| `summary` | string | 是 | 一行摘要 |
| `tags` | string[] | 否 | 标签列表 |
| `cover` | string | 否 | 封面图相对仓库根路径（`assets/articles/{slug}/...`） |
| `intro` | string | 否 | 导读，可多行 |

## slug 规则

`{source_domain}-{yyyymmdd}-{短标题}`：全小写、连字符分隔、ASCII 安全、文件系统与 URL 友好。例：`overreacted-io-20260708-the-grug-developer`。

## 媒体路径约定

- 媒体文件落地目录：`assets/articles/{slug}/`（相对仓库根）。
- `cover` 与正文图片一律写**相对仓库根**的路径（`assets/articles/{slug}/x.jpg`）；Horizon 渲染时按详情页位置自动加 `../` 前缀。
- 媒体下载由 skill repo 负责产出，Horizon 只消费已本地化的相对路径，不自行下载。

## 必填校验

Horizon 解析时校验所有「必填」字段；缺失则抛出明确错误（不产出半成品页面）。

## 变更同步

本契约字段变更时，在 Horizon 仓库提交信息注明，并同步告知 skill repo（当前仅 Horizon 一个消费者，靠 CHANGELOG / git diff 同步，不引入 schema 版本号）。

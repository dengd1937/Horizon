# 精华文章源文件契约

Horizon 渲染器扫描 `articles/*.md` 渲染精华文章库（索引页 `/articles/` + 详情页 `/articles/{slug}.html`）。本文档定义源文件格式，作为仓库内项目级 skill（`horizon-add-article`）及 Horizon 入库 helper 的产出依据。

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
cover: https://images.example.com/example-cover.jpg
intro: |
  可选导读，可多行；渲染在原文链与正文之间。
---

正文必须是忠实的简体中文译文；若原文已经是中文，则保留原文措辞，不做改写。正文保持原文章节、段落、列表、引用和媒体顺序，链接与媒体 URL 不变，代码块及原始 HTML 媒体标签不得翻译或修改。正文图片也保留原始 HTTPS URL：

![示意图](https://images.example.com/example-diagram.jpg)
~~~

## 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 是 | 文章标题 |
| `source_url` | string | 是 | 原文 URL，仅允许绝对 `http` 或 `https` URL |
| `source_domain` | string | 是 | 从 `source_url` 主机名确定性生成的小写域名（移除开头 `www.`，如 `example.com`） |
| `published_date` | string | 是 | 原文发布日期，必须精确匹配零补齐的 `YYYY-MM-DD`；无法可靠获取时必须暂停询问，不以抓取日期代替 |
| `added_date` | string | 是 | 入库时的 UTC 日期，必须精确匹配零补齐的 `YYYY-MM-DD`，用于按月分组与邮件「本期新增」 |
| `slug` | string | 是 | 文件名与 URL slug，全库唯一 |
| `summary` | string | 是 | 一行摘要 |
| `tags` | string[] | 否 | 标签列表 |
| `cover` | string | 否 | 原始封面图绝对 `https` URL |
| `intro` | string | 否 | 导读，可多行 |

## slug 规则

`{source_domain}-{yyyymmdd}-{短标题}`：全小写、连字符分隔、ASCII 安全、文件系统与 URL 友好；日期段固定使用 `published_date`。

- 短标题从标题中的 ASCII 字母/数字确定性归一化，最多保留前 6 个词和 64 个字符。
- 原标题不含 ASCII 词时，入库结构化输入必须额外提供 2–6 个英文词的 `slug_title`；它只参与 slug 生成，不写入 frontmatter。
- 已发布的 slug 不因后续标题编辑改变，也不允许 helper 静默覆盖同名文件。

例：`overreacted-io-20260708-the-grug-developer`。

## 入库确定性规则

- `horizon-add-article` 不直接拼接 YAML；它将结构化 JSON 元数据与正文交给 `horizon-article create`。
- `title`、`summary` 和正文必须为简体中文。`create` 与本地 `preview` 同时接收原始 `fetched.md` 和中文 `body.md`，校验中文占比，并确认 Markdown 的章节、逐段 block 顺序、链接、图片、视频及代码块相对原文未丢失或改写；每个原文段落都必须有对应译文段落。
- `published_date` 与 `added_date` 只接受精确 `YYYY-MM-DD`；`20260715`、`2026-W29-3` 等虽可被部分日期库解析，也会被契约拒绝。
- helper 自动生成 `source_domain`、`added_date` 与 `slug`，并在写文件前用本契约的同一解析器完整校验。
- 正文必须非空；`summary` 必须是非空单行；`tags` 必须是非空字符串组成的列表。
- 全库已有相同 `source_url` 或目标 slug 时拒绝创建，不更新、不覆盖已有文章。
- 新文件经同目录临时文件原子创建；任何校验或落盘失败都不得留下正式文件或覆盖旧内容。

## 媒体路径约定

- skill 在 `cover` 与 Markdown 正文图片中仅保留原始 **HTTPS** URL；不下载、不提交二进制媒体，也不使用 COS 凭据或上传媒体。
- Horizon 的文章发布 CI 扫描封面和 `![](...)` 图片（不会把普通 Markdown 超链接当媒体），下载成功后写入 `output_dir/assets/articles/{slug}/`，并仅在详情页将该 URL 改写为 `../assets/articles/{slug}/...`。下载请求只允许 HTTPS，并在每次重定向前重新校验目标；localhost、私有/保留 IP、解析到非公网地址的域名和非图片/视频响应均拒绝。
- 网络失败、HTTP 非 200 或超过 `max_media_mb` 时不生成本地路径，详情页保留原始 HTTPS URL，因此不会指向未写入站点目录的文件。
- 当前入库契约不接受本地相对媒体路径；需要迁移旧内容时，应先将其改回可访问的 HTTPS 原始 URL，再由 CI 本地化。

## URL 安全规则

- `source_url` 必须是带主机名的绝对 `http` 或 `https` URL。
- `cover` 和正文 Markdown 图片必须是带主机名的绝对 `https` URL；`file:`、`data:`、`javascript:`、协议相对 URL、相对路径与 HTTP 图片均会在解析阶段以带文件名的错误拒绝。
- 下载器只消费上述已通过校验的 HTTPS 图片，并对全部重定向目标执行公网地址校验；下载错误会记录 URL 与原因，随后回退到原始 HTTPS URL。skill 不参与下载、渲染或部署。

## HTML 渲染安全

- Markdown 正文及 `intro` 都是不可信输入，转为 HTML 后必须经过标签、属性与 URL allowlist，再进入详情页模板。
- 允许普通排版、链接、图片和安全的 HTTPS `<video>` / `<source>`；事件处理属性、`javascript:`、不安全媒体 URL 会被移除。
- `script`、`iframe`、`object`、`embed`、表单、SVG 等主动或可嵌入内容不进入最终页面；详情页同时设置限制性的 Content Security Policy，作为第二道防线。
- 原始抓取与中文译文仍保留媒体标签用于保真校验；“源文件保留”不代表浏览器会执行其中的主动内容。

## 必填校验

Horizon 在写入页面前解析并校验所有文章；缺失必填字段或违反 URL/slug 规则会抛出明确错误，不产出半成品 HTML 页面。

## 变更同步

本契约、校验代码与 `horizon-add-article` skill 同在 Horizon 仓库。字段变更时应在提交信息注明，并尽量在同一提交中同步更新三者；当前不引入 `schema_version`。

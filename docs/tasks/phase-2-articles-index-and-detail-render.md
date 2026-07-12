# Phase 2：文章库索引页、详情页渲染与入库契约

## Goal

定义精华文章入库契约（frontmatter、目录、slug、媒体路径），并让 Horizon `site.py` 扫描 `articles/*.md` 渲染精华文章详情页 `/articles/{slug}.html` 与按月分组索引页 `/articles/`，复用现有暖纸刊物风格。

## Dependencies

- Phase 1 已完成（`/articles/` 目录已腾空，地址结构就位）。
- 关键代码：`src/render/site.py`（`_page`、`_index_page` 按月分组模式、`_resolver`、`SITE_CSS`）、`src/render/assets.py`（`MediaDownloader`）。
- 文章源文件 `articles/*.md` 由独立 skill repo 产出（见 `../../discuss/article-skill-repo-plan.md`）；本阶段用手工 fixture 验证渲染，不依赖 skill 完成。

## Tasks

**入库契约（skill repo 对接接口）**

- [ ] 定义 `articles/{slug}.md` 源文件格式：YAML frontmatter + markdown 正文。
- [ ] 固化 frontmatter 字段：`title`、`source_url`、`source_domain`、`published_date`、`added_date`、`tags`（列表）、`summary`（一行）、`slug`、`cover`（可选）、`intro`（可选导读）。
- [ ] 定义 slug 规则（如 `{source_domain}-{yyyymmdd}-{短标题}`，保证文件名安全与排序稳定）。
- [ ] 定义媒体路径约定：`assets/articles/{slug}/`，正文用相对路径引用。
- [ ] 将契约写入 `docs/article-frontmatter-spec.md`，作为 skill repo 实现依据。

**渲染**

- [ ] 新增 frontmatter 解析（YAML，含必填字段校验与友好报错）。
- [ ] 新增精华文章详情页渲染：复用 `_page` + `SITE_CSS`，结构为 标题 → 等宽元信息（来源/日期/标签）→ 醒目原文链 + 转载声明 → [可选导读] → 正文（markdown 渲染）→ 上下篇导航。
- [ ] 原文链醒目展示，旁注「本文转载自 {source_domain}，版权归原作者所有」。
- [ ] 上下篇导航：按 `added_date` 排序，链向相邻文章。
- [ ] 新增索引页 `/articles/index.html`：按 `added_date` 月份分组（复用 `_index_page` 模式），每条含 标题/来源域/日期/一行摘要/标签。
- [ ] `SiteRenderer` 的 articles 源目录参数化：默认扫仓库根 `articles/`，测试时可指向 `tests/fixtures/articles/`，不污染真实文章库。
- [ ] 渲染接入主流程：`SiteRenderer.render` 扫描 articles 源目录，生成详情页与索引页，纳入返回路径列表。
- [ ] 详情页内媒体引用经 `MediaDownloader` / `_resolver` 本地化（与 digest 媒体链路一致）。

## Validation

- [ ] 文件检查：`docs/article-frontmatter-spec.md` 存在且字段清单完整。
- [ ] 准备 ≥3 篇手工 fixture 放 `tests/fixtures/articles/`（覆盖不同来源域、含/不含封面与导读、跨月份），经参数化路径本地渲染通过。
- [ ] 单元测试（参照现有 `tests/test_article_html.py` 模式）：frontmatter 解析正确；缺必填字段时抛明确错误；slug 规则函数稳定；按月分组顺序正确。
- [ ] Playwright 打开 `/articles/index.html`，确认按月分组、条目字段齐全、链接指向 `/articles/{slug}.html`。
- [ ] Playwright 打开详情页，确认结构顺序（标题/元信息/原文链/转载声明/导读/正文/上下篇）、原文链可点、上下篇导航正确。
- [ ] Playwright 确认首尾文章的上下篇边界（首篇无「上一篇」、末篇无「下一篇」），不出现死链。
- [ ] Playwright 确认详情页样式与 digest 同系（暖纸刊物风、复用 SITE_CSS），媒体正常显示。
- [ ] 缺字段 fixture 渲染时给出明确错误（不产出半成品页面）。
- [ ] 无文章时索引页优雅空态（不报错）。

## Out of Scope

- 不实现抓取（由独立 skill repo 承担）。
- 不做日报页入口与计数（Phase 3）。
- 不做邮件 section（Phase 4）。
- 不做全文搜索 / 标签聚合页。

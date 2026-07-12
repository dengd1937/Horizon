# Horizon 增量任务拆分

本文档集由 `../../discuss/curated-articles-plan.md` 拆分而来，用于按阶段推进 Horizon「精华文章库 + 分区入口 + 地址重构」增量。

## 阶段顺序

1. [Phase 1：地址结构重构](./phase-1-site-url-restructure.md)
2. [Phase 2：文章库索引页、详情页渲染与入库契约](./phase-2-articles-index-and-detail-render.md)
3. [Phase 3：日报页文章库入口](./phase-3-daily-page-articles-entry.md)
4. [Phase 4：邮件「本期新增」与 footer](./phase-4-email-new-articles-section.md)

## 范围说明

- 精华文章的**抓取**（URL → 文章源文件）由**独立 skill repo** 承担，不在 Horizon 代码内。该 skill 跨 Claude Code / Codex / Trae 通用，调研与计划见 `../discuss/article-skill-repo-plan.md`。
- Horizon 作为**消费方**，只负责：定义入库契约（Phase 2）、渲染索引页与详情页（Phase 2）、站点入口（Phase 3）、邮件落点（Phase 4）、地址重构（Phase 1）。

## 决策基线

- 技术栈：Horizon 现状（静态站点生成器，GitHub Actions 定时抓取 + 本地渲染，腾讯 COS 部署）。
- 地址结构：`/daily/`（Twitter 日报）与 `/articles/`（精华文章）两区对称，根 `/` 跳最新日报。
- 文章源文件：`articles/{slug}.md`（YAML frontmatter + markdown 正文），由 skill repo 产出并 commit，Horizon 渲染器扫描消费。
- 详情页渲染：由 Horizon `site.py` 统一渲染（复用 `SITE_CSS`），不由 skill 直出 HTML。
- 媒体：沿用 Horizon 现有 `MediaDownloader` 链路，落地 `assets/`。
- 展示与部署：零改动（香港 COS + 备案域名）。

## 交付约定

- 每个阶段完成后必须满足对应文档的 `Validation`，统一使用 `- [ ]` 清单。
- 验收手段：本地运行渲染器生成 `output_dir/` → 用 Playwright CLI Skill 打开产物 HTML 验布局/链接/导航；纯函数（frontmatter 解析、路径生成、计数、邮件 section 拼装）配单元测试。
- 本地预览静态产物需起简易服务器（如 `python -m http.server` 于 `output_dir/`），避免 `file://` 下相对路径与 meta refresh 行为偏差。
- 不跨阶段提前引入能力，除非当前阶段验收依赖。
- 断链不是约束，借重构机会清理旧路径。

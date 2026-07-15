# Horizon 增量任务拆分

本文档集由 `../../discuss/curated-articles-plan.md` 拆分而来，用于按阶段推进 Horizon「精华文章库 + 分区入口 + 地址重构」增量。

## 阶段顺序

1. [Phase 1：地址结构重构](./phase-1-site-url-restructure.md)
2. [Phase 2：文章库索引页、详情页渲染与入库契约](./phase-2-articles-index-and-detail-render.md)
3. [Phase 3：日报页文章库入口](./phase-3-daily-page-articles-entry.md)
4. [Phase 4：邮件「本期新增」与 footer](./phase-4-email-new-articles-section.md)
5. [Phase 5：`horizon-add-article` 文章入库 Skill](./phase-5-horizon-add-article-skill.md)

> Phase 2 同时包含文章媒体本地化和 `articles/**` 推送上线的 CI
> 集成；它们是文章库可发布的必要条件，而不是后续优化。

## 范围说明

- 精华文章的**通用网页抓取**（URL → Markdown）由外部 `baoyu-fetch` 承担；Horizon 仓库内维护项目级 `horizon-add-article` skill（Phase 5），负责编排抓取、生成结构保真的简体中文译文、在仓库外生成隔离的本地预览，或按契约写入并提交 `articles/{slug}.md`。skill 不持有 COS 凭据、不执行生产渲染、不上传站点。
- Horizon 作为**入库契约所有者、消费方与发布方**，负责：确定性生成与校验文章源文件、定义入库契约（Phase 2）、下载并本地化文章媒体（Phase 2）、渲染索引页与详情页（Phase 2）、在 `articles/**` 推送时触发独立 CI 发布（Phase 2）、站点入口（Phase 3）、邮件落点（Phase 4）、地址重构（Phase 1）。
- SignalFeed 的归档封存是原始方案中的独立人工处置项，不属于本仓库 Phase 1–5；不要借本任务重新引入 Admin Console、PV 或运行记录能力。

## 决策基线

- 技术栈：Horizon 现状（静态站点生成器，GitHub Actions 定时抓取 + 本地渲染，腾讯 COS 部署）。
- 地址结构：`/daily/`（Twitter 日报）与 `/articles/`（精华文章）两区对称，根 `/` 跳最新日报。
- 文章源文件：`articles/{slug}.md`（YAML frontmatter + markdown 正文），由仓库内 `horizon-add-article` skill 调用 Horizon helper 产出并 commit，Horizon 渲染器扫描消费。原始方案中“skill 生成 `articles/{slug}.html`”是早期草案，已由 Markdown 入库契约取代。
- 详情页渲染：由 Horizon `site.py` 统一渲染（复用 `SITE_CSS`）；skill 的本地预览只在仓库外调用同一渲染器，不另行拼接详情页 HTML。
- 媒体：skill 保留封面和正文图片的原始 HTTPS URL；Horizon CI 复用/扩展 `MediaDownloader` 下载到 `output_dir/assets/articles/{slug}/`，并在文章详情 HTML 中改写为相对路径。下载失败可降级保留原 URL，不能产出指向不存在本地文件的链接。
- 展示与部署：继续香港 COS + 备案域名和 `deploy_command`，不转 GitHub Pages；文章发布只增补触发入口，不改变日常 Twitter 抓取、邮件发送或 COS 目标。
- Twitter 的线程合并、QRT 判定、跨账号去重、card/X Article 解析保持不动；RSS 仅不配置，保留 scraper 代码。

## 交付约定

- 每个阶段完成后必须满足对应文档的 `Validation`，统一使用 `- [ ]` 清单。
- 验收手段：本地运行渲染器生成 `output_dir/` → 用 Playwright CLI Skill 打开产物 HTML 验布局/链接/导航；纯函数（frontmatter 解析、路径生成、计数、邮件 section 拼装）配单元测试。
- 本地预览静态产物需起简易服务器（如 `python -m http.server` 于 `output_dir/`），避免 `file://` 下相对路径与 meta refresh 行为偏差。
- 不跨阶段提前引入能力，除非当前阶段验收依赖。
- 断链不是约束，借重构机会清理旧路径。
- CI 验收同时检查部署工作流与上述决策一致：不得因 `articles/**` 的发布而抓 Twitter、发送邮件或改用 GitHub Pages。

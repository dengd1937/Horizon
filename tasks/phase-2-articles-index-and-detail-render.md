# Phase 2：文章库索引页、详情页渲染与入库契约

## Goal

定义精华文章入库契约（frontmatter、目录、slug、媒体路径），并让 Horizon 扫描 `articles/*.md` 渲染精华文章详情页 `/articles/{slug}.html` 与按月分组索引页 `/articles/`，复用现有暖纸刊物风格；同时在 `articles/**` 提交后由 CI 本地化媒体并发布到既有 COS 站点。

## Dependencies

- Phase 1 已完成（`/articles/` 目录已腾空，地址结构就位）。
- 关键代码：`src/render/site.py`（`_page`、`_index_page` 按月分组模式、`_resolver`、`SITE_CSS`）、`src/render/curated.py`、`src/render/assets.py`（`MediaDownloader`）、`.github/workflows/`（文章提交触发与 COS 发布）。
- 文章源文件 `articles/*.md` 最终由 Phase 5 的项目级 `horizon-add-article` skill 与入库 helper 产出（见 [`phase-5-horizon-add-article-skill.md`](./phase-5-horizon-add-article-skill.md)）；本阶段用手工 fixture 验证渲染，不依赖 Phase 5 完成。

## Tasks

**入库契约（项目级 skill 与 Horizon 入库 helper 的接口）**

- [x] 定义 `articles/{slug}.md` 源文件格式：YAML frontmatter + markdown 正文。
- [x] 固化 frontmatter 字段：`title`、`source_url`、`source_domain`、`published_date`、`added_date`、`tags`（列表）、`summary`（一行）、`slug`、`cover`（可选）、`intro`（可选导读）。
- [x] 定义 slug 规则（如 `{source_domain}-{yyyymmdd}-{短标题}`，保证文件名安全与排序稳定）。
- [x] 定义媒体约定：skill 在 `cover` 与正文中保留原始 HTTPS URL，不下载、不提交媒体文件；Horizon CI 下载成功后落地 `output_dir/assets/articles/{slug}/` 并把详情页改写为相对路径。若保留本地相对路径作为兼容输入，需明确其复制到 `output_dir/` 的规则。
- [x] 将契约写入 `docs/article-frontmatter-spec.md`，作为项目级 skill 与 Horizon 入库 helper 的实现依据。
- [x] 在契约中明确 `source_url`、`cover`、正文图片的 URL 安全规则、允许的协议和下载失败降级行为；禁止由 skill 使用 COS 凭据或直接上传媒体。
- [x] 将 `published_date` 与 `added_date` 的格式收紧为精确、零补齐的 `YYYY-MM-DD`；拒绝 compact date、ISO week date 等 `date.fromisoformat` 可接受但渲染契约不支持的形式。

**渲染**

- [x] 新增 frontmatter 解析（YAML，含必填字段校验与友好报错）。
- [x] 新增精华文章详情页渲染：复用 `_page` + `SITE_CSS`，结构为 标题 → 等宽元信息（来源/日期/标签）→ 醒目原文链 + 转载声明 → [可选导读] → 正文（markdown 渲染）→ 上下篇导航。
- [x] 正文中的图片和视频最大宽度与正文段落栏一致，在桌面端和移动端均不得按原始媒体尺寸横向溢出；媒体保持自身比例。iframe 属主动嵌入内容，不进入最终 HTML。
- [x] Markdown 与导读渲染后经过 HTML allowlist 与 URL 清洗，并设置限制性 CSP；移除脚本、iframe、事件属性、`javascript:` 链接及私有地址媒体，同时保留安全排版和 HTTPS 图片/视频。
- [x] 原文链醒目展示，旁注「本文转载自 {source_domain}，版权归原作者所有」。
- [x] 上下篇导航：按 `added_date` 排序，链向相邻文章。
- [x] 新增索引页 `/articles/index.html`：按 `added_date` 月份分组（复用 `_index_page` 模式），每条含 标题/来源域/日期/一行摘要/标签。
- [x] `SiteRenderer` 的 articles 源目录参数化：默认扫仓库根 `articles/`，测试时可指向 `tests/fixtures/articles/`，不污染真实文章库。
- [x] 渲染接入主流程：`SiteRenderer.render` 扫描 articles 源目录，生成详情页与索引页，纳入返回路径列表。
- [x] 增加精华文章媒体收集与本地化：扫描 `cover` 和 Markdown 正文的远程图片 URL，复用或扩展 `MediaDownloader` 下载到 `assets/articles/{slug}/`，在详情 HTML 中改写为 `../assets/articles/{slug}/...`；不能误把普通超链接当媒体。
- [x] 下载失败、超出大小限制或不支持协议时优雅降级为原始 HTTPS URL，并记录可定位的日志；不能生成指向未写入 `output_dir/` 的相对路径。
- [x] 媒体下载只允许 HTTPS；初始请求与每次重定向均校验目标为公网地址，拒绝 localhost、私有/保留 IP 与解析到非公网地址的域名，并要求响应 Content-Type 为图片或视频。
- [x] 新增仅处理 `articles/**` 推送的 CI workflow：checkout → 读取文章 → 渲染/媒体本地化 → 使用现有 COS 凭据与发布链路同步 `output_dir/`。该 workflow 不抓 Twitter、不调用 AI、不发邮件，也不需要新增 Horizon CLI 子命令。
- [x] 保证文章发布不会破坏已有日报归档：按既有部署策略保留 `daily/`、根入口和历史 `assets/`；必要时从 COS 拉取所需站点状态再同步。
- [x] 文章发布仅允许 `main` 的 `articles/**` push 或在 `main` 手动触发；与日报发布共享同一 concurrency group，远端站点拉取失败即停止，避免并发覆盖或在缺失基线时执行 `--delete`。

## Validation

- [x] 文件检查：`docs/article-frontmatter-spec.md` 存在且字段清单完整。
- [x] 准备 ≥3 篇手工 fixture 放 `tests/fixtures/articles/`（覆盖不同来源域、含/不含封面与导读、跨月份），经参数化路径本地渲染通过。
- [x] 单元测试（参照现有 `tests/test_article_html.py` 模式）：frontmatter 解析正确；缺必填字段时抛明确错误；slug 规则函数稳定；按月分组顺序正确。
- [x] 单元测试：远程封面和正文图片会下载到 `assets/articles/{slug}/` 并改写为详情页相对路径；下载失败、超限和非图片链接不会产生断开的本地 `src`。
- [x] Playwright 打开 `/articles/index.html`，确认按月分组、条目字段齐全、链接指向 `/articles/{slug}.html`。
- [x] Playwright 打开详情页，确认结构顺序（标题/元信息/原文链/转载声明/导读/正文/上下篇）、原文链可点、上下篇导航正确。
- [x] Playwright 确认首尾文章的上下篇边界（首篇无「上一篇」、末篇无「下一篇」），不出现死链。
- [x] Playwright 确认详情页样式与 digest 同系（暖纸刊物风、复用 SITE_CSS），媒体正常显示且图片、视频宽度不超过正文段落栏；iframe 不出现在最终页面。
- [x] 用包含真实媒体 fixture 的静态产物起本地服务器，确认封面和正文图片均为 200；不得只断言 HTML 中出现 `../assets/...` 字符串。
- [x] 缺字段 fixture 渲染时给出明确错误（不产出半成品页面）。
- [x] 无文章时索引页优雅空态（不报错）。
- [x] CI 验收：向 `main` 的 `articles/**` 测试提交会触发文章发布 workflow；其他分支不触发生产部署。该 workflow 不执行 Twitter 抓取、AI 调用、邮件发送，且发布目标仍为 COS 而非 GitHub Pages。
- [x] 安全回归：原始 `<script>`、事件属性、`javascript:` 链接、私有地址媒体与 iframe 不进入详情 HTML；媒体下载不会跟随重定向访问回环/私网地址，也不保存 HTML 响应。
- [x] workflow 静态契约测试：只允许 `main`，日报与文章 workflow 共用串行化边界，COS 拉取与 coscli 安装均 fail closed。

## Out of Scope

- 不在渲染流程中实现通用网页抓取；该能力由外部 `baoyu-fetch` 提供，项目级 skill 只做编排。
- 不做日报页入口与计数（Phase 3）。
- 不做邮件 section（Phase 4）。
- 不做全文搜索 / 标签聚合页。
- 不让 skill 下载媒体、访问 COS 或自行拼接生产站点 HTML；生产渲染仍是 Horizon CI 的消费/发布职责，Phase 5 的仓库外本地预览只复用本阶段渲染器。

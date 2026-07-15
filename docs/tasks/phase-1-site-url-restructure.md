# Phase 1：地址结构重构

## Goal

把站点从「根目录平铺」重构为 `/daily/`（Twitter 日报）与 `/articles/`（精华文章）两区对称结构，根 `/` 跳转最新日报，为 Phase 2 引入精华文章库腾出 `articles/` 目录。

## Dependencies

- 无前置阶段。
- 关键代码：`src/render/site.py`（`:101` digest 输出、`:111`/`:471` 归档索引、`:398`/`:448` X Article 详情与链接）。

## Tasks

- [x] digest 页由根 `{date}.html` 改为 `daily/{date}.html`（`site.py:101` `render`）。
- [x] X Article 详情页由 `articles/{article_id}.html` 改为 `daily/article-{article_id}.html`（`site.py:398` `_article_card` 链接、`:448` `_article_page` 输出路径）。
- [x] digest 内部链接同步：返回当日锚点链接（`site.py:433` `back`）、X Article 卡片 href 调整为 `daily/` 下正确的相对路径。
- [x] 同步邮件 digest 深链：`src/ai/summarizer.py:107` `page_url` 与 `:232` `original_url` 的 `{date}.html` → `daily/{date}.html`（邮件里指向阅读站的链接）。
- [x] 归档索引页由根 `index.html` 改为 `daily/index.html`（`site.py:111`），归档条目链接加 `daily/` 前缀。
- [x] 新增根 `index.html`：读取 `site_manifest.json` 最新日期，用 meta refresh 跳转 `daily/{latest}.html`；无历史日期时跳 `daily/index.html`。
- [x] 处理迁移遗留物：渲染到已有 `output_dir/` 或部署到已有 COS 前，删除/覆盖旧根 `{date}.html` 与旧 `articles/{id}.html`，确保迁移后根目录只保留入口页，`articles/` 只保留精华文章产物。
- [x] 调整 assets 相对路径：`daily/` 下页面引用 `assets/{date}/` 改为 `../assets/{date}/`（复用现有 `_resolver` prefix 机制）。
- [x] 路径生成抽取为纯函数（如 `daily_digest_path(date)`、`daily_article_path(id)`、`archive_index_path()`），供渲染与测试复用。
- [x] 排查并更新 CI / `deploy_command` 中的硬编码路径引用（如有）；部署目标继续腾讯 COS + 备案域名，不因本次重构切换到 GitHub Pages。若现有 workflow 留有 GitHub Pages 发布步骤，明确移除或禁用，避免双轨产物与地址结构不一致。

## Validation

- [x] 本地运行渲染器生成 `output_dir/`，确认产物结构为 `index.html` + `daily/{date}.html` + `daily/article-{id}.html` + `daily/index.html` + `assets/{date}/`。
- [x] 单元测试：路径生成函数返回预期值；根 `index.html` 的 meta refresh 目标取自 manifest 最新日期。
- [x] 更新 `tests/test_site_renderer.py` 中所有路径硬编码断言（如 `2026-07-05.html`、`articles/900.html`、`../assets/...`）以匹配新结构。
- [x] Playwright CLI Skill 起本地静态服务，打开根 `/`，确认自动跳转到最新 `daily/{date}.html`。
- [x] Playwright 打开 `daily/{date}.html`，确认样式、媒体（图/视频/GIF）、评分条、目录锚点正常。
- [x] Playwright 点击 digest 内 X Article 卡片，确认跳转到 `daily/article-{id}.html`，且详情页「返回」链接正确回到当日锚点。
- [x] Playwright 打开 `daily/index.html`，确认按月分组归档，条目链接指向 `daily/{date}.html`。
- [x] Playwright 确认无残留旧路径（根下不再有 `{date}.html`；`articles/` 目录不再含 X Article）。
- [x] 全站无 404（Playwright 抓取页面内全部内部链接确认可达）。
- [x] 在已有旧产物的 `output_dir/` 上执行一次迁移渲染/部署 dry-run，确认旧路径对象被清理而非仅在全新目录中“看起来正确”。
- [x] 检查发布 workflow：站点仍由 COS 的 `deploy_command` 发布；不存在启用中的 GitHub Pages 发布作为替代或并行目标。

## Out of Scope

- 不引入精华文章库内容（Phase 2）。
- 不改 X Article 渲染逻辑（`article_html.py`），只改输出路径与链接。
- 不改邮件发送逻辑与模板（仅同步 `summarizer.py` 中指向阅读站的 digest 路径；邮件 section 新增属 Phase 4）。
- 不改变 COS 域名、桶、凭据或媒体总链路；仅清理与既定 COS 发布冲突的遗留 GitHub Pages 配置。

# Horizon 增量计划：精华文章库 + 分区入口 + 地址重构

## 1. 背景

原计划新建 SignalFeed（单体 Web 应用 + 香港服务器 + Admin Console）做每日智能简报，已完成 Phase 0–6。重新评估后发现：

- **成本**：香港 Lighthouse 对"自己 + 少量同事"规模 ROI 低（~1200 元/年）。
- **规模**：SignalFeed 的增量（Admin 后台、PV、运行记录）对此规模无真实需求。
- **稳定**：Horizon 已在 GitHub Actions 上稳定运行两周，Twitter 抓取路径已验证。

**结论：中止 SignalFeed 单体路线，回到 Horizon 增强。** SignalFeed 仓库归档封存，留作参考。

## 2. 最终形态

**Horizon 现状（不动）+ 精华文章库 + 分区入口 + 地址重构**：

- 定时抓 Twitter（Actions，保留 Horizon 现有流程）
- 不定时人工精选博客文章（本地 Claude Desktop skill 抓 URL → 生成 HTML → commit）
- 展示：香港 COS + 备案域名（Horizon 现状，零改动）
- 媒体：COS（Horizon 现状，零改动）
- 邮件 + 地址结构：增量改造

## 3. 设计决策

### 信息源
- **Twitter**：保留现有 Playwright 抓取，**不裁剪高级解析**（线程合并 / QRT 实质评论判定 / 跨账号去重 / card / article 全保留——已稳定两周，动它们 risk > reward）。
- **RSS**：不配置 RSS source 即可，**不删 RSS scraper 代码**（留 dead code 无害）。

### 精华文章
- **独立文章库**，不绑定某期日报（`/articles/` 索引 + `/articles/{slug}.html` 详情）。
- **不过 AI 流水线**：人工挑选即入选，跳过评分筛选。
- **抓取方式（先复用后自建）**：
  1. 先调研现成方案：社区 Claude skills / MCP server / 开源 URL→正文工具（如 jina reader、trafilatura、readability、各类 web-reader MCP）。
  2. 若可用：直接用或适配，跳过自建。
  3. 若无：自建 Claude Desktop skill，给定 URL → 抓正文 → 生成规定 HTML → commit `articles/{slug}.html`。用 LLM 替代传统提取器，解决付费墙 / JS 渲染 / 非标准 HTML；抓不到时和 Claude 对话补充。

### 详情页
- **全文转载 + 开头醒目原文链**（连贯性优先）。
- 开头原文链旁加「本文转载自 {域名}，版权归原作者所有」标注。
- 结构：标题 → 等宽元信息（来源/日期/标签）→ 醒目原文链（开头）→ [可选导读] → 正文全文 → 上下篇导航。

### 索引页 `/articles/`
- **按月分组的时间流**（延续 Horizon 暖纸刊物风格）。
- 每条：标题 / 来源域 / 日期 / 一行摘要 / 标签。
- 可复用 Horizon 归档页 `_index_page` 的按月分组模式。

### 邮件（落点基于 Horizon 实际）
- Horizon 邮件是 `summary_md`（markdown）经 `markdown.markdown()` 渲染（`src/services/email.py:154`），无结构化条目。
- **分区落点**：在 `summary_md` 末尾追加 markdown 小节 `## 本期新增精选文章` + 文章列表（标题/来源/摘要/详情页链接）。
- **footer**：现有 footer（`email.py:183`）加一行 `文章库：{site_url}/articles/`。
- **"本期新增"**：发邮件时 Actions 扫 `articles/`，按 frontmatter `added_date` 找自上次邮件以来新增的；某期无新增则隐藏该 section。
- 纯文本 alternative 自动带同段，两边一致。

### 日报页
- 加文章库入口（顶部导航「文章库」与「归档」并列；footer 计数入口如「文章库本周 +3」）。

### 地址结构（重构）
两区对称，根目录干净：

```text
/                         跳转到 /daily/{today}.html（meta refresh 或 JS）
/daily/                   日报归档索引（按月分组）
/daily/{date}.html        每日 Twitter 速递
/daily/article-{id}.html  推文 X Article 详情（从 /articles/ 挪来）
/articles/                精华文章库索引（按月分组）
/articles/{slug}.html     精华文章详情
/assets/{date}/           媒体
```

- **两个内容区对称**：`/daily/`（Twitter 日报）和 `/articles/`（精华文章）各占一个目录。
- **`articles/` 让给精华文章库**——"articles"语义给人工精选博客最贴切；Twitter X Article 本质是「某条推文附带的长文」，归到 `/daily/` 作日报子页更合逻辑。文件名 `article-{id}.html` 避开和 `{date}.html` 混淆。
- **断链不是约束**，借机重构（现有外部/邮件链接无需保留）。

### 媒体 / 展示 / 部署
- **零改动**。展示继续香港 COS + 备案域名；媒体继续 Horizon 现有链路（`MediaDownloader` 本地化 `output_dir/assets/{date}/` → 随 `coscli sync` 整站上 COS → 相对路径引用）；部署继续 `deploy_command`。
- 曾考虑转 GitHub Pages，因公司网访问不稳定 + 媒体链路要拆改，放弃，留 COS。

## 4. 增量清单（可执行）

| # | 项 | 落点 | 改动 |
|---|----|------|------|
| 1 | 精华文章抓取 | 本地（非 Horizon 代码） | **先调研现成方案**（Claude skills / MCP / 开源 URL→HTML 工具）；无可用再自建 skill：抓 URL → 生成详情页 HTML（规定模板）→ commit `articles/{slug}.html`；媒体细节（commit 相对路径 vs skill 直传 COS 绝对 URL）后续定 |
| 2 | 文章库索引页 `/articles/` | Horizon `render/site.py` | 新代码：扫 `articles/` 生成按月分组索引页（复用 `_index_page` 模式） |
| 3 | 日报页文章库入口 | Horizon `render/site.py` | 日报模板加导航 / 计数入口 |
| 4 | 邮件「本期新增」section + footer | Horizon `email.py` + summary 生成处 | footer 加文章库链接；summary 生成处扫 `articles/` 拼 markdown 小节 |
| 5 | 地址结构重构 | Horizon `render/site.py` | digest `{date}.html` → `daily/{date}.html`；X Article `articles/{id}.html` → `daily/article-{id}.html`；归档/返回链接同步；根 `index.html` 跳最新日报 |

## 5. 明确不做

- 不做后台 / Admin Console（已弃单体路线）
- 不砍 RSS 代码（不配置即可）
- 不裁 Twitter 高级解析（保留已稳定功能）
- 不转 GitHub Pages（公司网不稳 + 媒体要拆改）
- 不改媒体链路（站点留 COS，耦合恢复）
- AI 链路保持现状（不单趟化）

## 6. 关键代码定位（新会话参考）

- `src/services/email.py:154` `send_daily_summary(summary_md, subject, subscribers)` —— 邮件 = markdown 渲染 HTML + footer
- `src/render/assets.py` `MediaDownloader` —— 媒体本地化到 `output_dir/assets/{date}/`
- `src/render/deploy.py` `deploy_site` —— `deploy_command`（coscli sync 整站）
- `src/render/site.py` 站点渲染：
  - `:101` digest = `{date}.html`（重构项：→ `daily/{date}.html`）
  - `:111` `index.html` 归档
  - `:398,448` `articles/{article_id}.html` X Article（重构项：→ `daily/article-{id}.html`）
  - `:471` `_index_page` 按月分组归档（精华文章库索引可复用此模式）
  - `:173,184` 品牌 `HORIZON`
- `src/render/article_html.py` —— X Article（draft.js）渲染，与精华文章无关，但 `asset_resolver` 模式可借鉴
- `src/scrapers/twitter_parsing.py` —— Twitter 解析纯函数（稳定，不动）
- `src/orchestrator.py` —— 编排全流程（summary 生成、邮件触发在此）

## 7. SignalFeed 仓库处置

归档封存：`/Users/dengdi/MySpace/Projects/SignalFeed`，加 README 注明"已转向 Horizon 增强，Phase 0–6 成果与 Phase 7 设计文档留作参考"，不删。

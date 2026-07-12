# 精华文章抓取 Skill Repo 草稿（讨论）

> 本文档为待建独立 skill repo 的调研与计划草稿，非 Horizon 代码的一部分。Horizon 作为消费方，对接契约见 `../docs/tasks/phase-2-articles-index-and-detail-render.md`。

## 背景

Horizon 增量计划需要「人工精选博客文章 → 入库」的能力。该能力：

- **不属于 Horizon 项目代码**：Horizon 是静态站点生成器，抓取是另一类工具。
- **有跨 agent 通用性**：作者日常混用 Claude Code、Codex、Trae，希望任一 agent 都能把看到的 URL 抓成 Horizon 文章源文件入库。
- **SKILL.md 已是跨平台开放标准（2026）**：Claude Code（原生）、Codex CLI（2025-12 实验性支持，`~/.agents/skills/`）、Trae（官方文档 docs.trae.ai/ide/skills）、Cursor、Google Antigravity、AWS 均认同一 SKILL.md 规范。一个 SKILL.md 三端通吃，无需为每个 agent 单做入口。

结论：把「抓取并入库」做成**独立 skill repo**，一个标准 SKILL.md + 必要脚本，用户在各 agent 的 skills 目录软链 / 拷贝即可。

## Skill 职责边界

**skill 负责（通用部分）**：
- 输入：文章 URL（可能付费墙 / JS 渲染 / 非标准 HTML）。
- 抓取正文与元数据（评估 Jina Reader / Firecrawl / trafilatura / readability / web-reader MCP，或 LLM 兜底）。
- 媒体下载与本地化。
- 按 Horizon 入库契约产出 `articles/{slug}.md`（YAML frontmatter + markdown 正文）。
- 抓不到时与用户对话补充。

**Horizon 负责（消费部分）**：
- 定义并维护入库契约（frontmatter 字段、slug、目录、媒体路径，见 `../docs/tasks/phase-2-articles-index-and-detail-render.md`）。
- 扫描 `articles/*.md` 渲染索引页与详情页。
- 不关心 skill 如何抓取。

**入库落点**：skill 产出文件后，由当前 agent 在 Horizon 工作目录 commit（skill 不直接耦合 Horizon 仓库路径，通过参数 / 约定指定输出目录）。

## 待调研项

- [ ] reader 选型：现成方案（Jina Reader API / web-reader MCP / trafilatura）对付费墙、JS 渲染、非标准 HTML 的命中率；是否需要 LLM 兜底。
- [ ] 媒体处理：复用 Horizon `MediaDownloader` 模式，还是 skill 自带轻量下载。
- [ ] frontmatter 来源：发布日期 / 作者 / 标签的自动抽取准确率，哪些需人工补。
- [ ] 跨 agent 目录约定：Claude `~/.claude/skills/`、Codex `~/.agents/skills/`、Trae 的 skills 目录路径与加载差异；是否用一个 install 脚本统一软链。
- [ ] 失败兜底：对话补充的交互范式（skill 中断点 / 半成品 frontmatter 标记）。

## 独立 repo 形态

GitHub 公开仓库 `web-article-clipper`：

```text
web-article-clipper/
├── SKILL.md                  # 三端通用入口
├── scripts/                  # 抓取 / 媒体 / 校验脚本
├── templates/                # frontmatter 模板
├── CHANGELOG.md              # frontmatter 契约变更同步
└── README.md                 # 安装到各 agent 的说明 + 指向 Horizon 契约文档
```

契约对齐：frontmatter 字段严格遵循 Horizon `docs/tasks/phase-2` 定义；版本化字段，避免 skill 与 Horizon 渲染器错位。

## 已定决策

- **仓库**：GitHub 公开 `web-article-clipper`（通用名、不绑 Horizon）。
- **契约治理**：轻量方案——权威文档放 Horizon `docs/article-frontmatter-spec.md`，本 repo README 指向它，字段变更靠 `CHANGELOG.md` 同步；不引入 `schema_version` 或共享 JSON Schema，等出现第二个消费者再上。
- **MCP server**：先只做 SKILL.md（已覆盖 Claude Code / Codex / Trae）；MCP 留作未来开放选项，等出现非-coding-agent 消费者再评估。
- **reader**：调研期对 Jina Reader / 本地库（trafilatura 等）/ 纯 LLM 提取多方案对比再定首层，不预先锁死。

## 下一步

待 Horizon Phase 2 入库契约定稿后，在本 repo（或新 repo）启动 skill 调研与实现。

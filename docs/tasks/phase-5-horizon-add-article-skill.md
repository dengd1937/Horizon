# Phase 5：`horizon-add-article` 文章入库 Skill

## Goal

在 Horizon 仓库内实现项目级 `horizon-add-article` skill：在 Codex Desktop 中接收文章 URL，调用外部 `baoyu-fetch` 抓取正文，生成结构保真的简体中文译文，再由 Horizon 确定性代码校验内容。用户可以选择在仓库外生成隔离的本地站点预览，或生成 `articles/{slug}.md`，经审阅后精确 commit & push，触发 Phase 2 已有文章发布 CI。skill 源码随 Horizon 维护，不建立独立 repo；个人环境中的安装方式不属于本阶段交付。

## Dependencies

- Phase 2 已完成：[`../article-frontmatter-spec.md`](../article-frontmatter-spec.md)、`src/render/curated.py` 的解析/slug/校验逻辑、文章索引与详情页渲染、文章媒体本地化及 `.github/workflows/publish-articles.yml` 均可用。
- live 验收依赖已安装且可用的外部 `baoyu-url-to-markdown`（`baoyu-fetch` CLI，Chrome CDP + Defuddle），并需要为 Anthropic 博客、知乎专栏、微信公众号各准备一个可公开访问的真实 URL。
- Codex Desktop 验收需要 Horizon 可写 workspace、本机 `origin/main` push 凭据、按 commit SHA 查询该仓库 GitHub Actions 的权限，以及能发现待验收 skill 的全新任务。

## Tasks

**归属与目录**

- [x] 在 Horizon 新建 `skills/horizon-add-article/SKILL.md`，`name` 使用 `horizon-add-article`；该目录是唯一权威版本，不建立 `web-article-clipper` 或其他独立 repo。
- [x] 保持 skill 精简：只保存 agent 工作流及必要的轻量资源，不复制 frontmatter 契约、渲染器、部署代码或 COS 配置。
- [x] 在 skill 中明确能力边界：通用 URL → Markdown 由 `baoyu-fetch` 负责；Horizon helper 负责生成、校验、去重和落盘；本地预览只在仓库外复用 Phase 2 渲染器；CI 负责生产媒体、渲染与部署。
- [x] 将唯一 publication target 固化为 `origin/main`；skill 不从当前分支或其他 remote 猜测发布目标，也不允许调用时临时改写目标。

**确定性入库 helper**

- [x] 将 `src/render/curated.py` 中可共享的 frontmatter 解析、slug 和校验逻辑复用或抽取到中立的文章契约模块，确保渲染器与入库 helper 使用同一套规则。
- [x] 实现结构化入库接口：接收 source URL、抓取后的正文和元数据，规范化 `source_domain`，生成 `added_date` 与 slug，安全序列化 YAML，并原子写入 `articles/{slug}.md`。
- [x] 实现全库重复检查：同一 `source_url` 和同一 slug 不得静默创建第二份文件；冲突时给出可操作错误，不覆盖已发布文章。
- [x] 在写入前执行 [`../article-frontmatter-spec.md`](../article-frontmatter-spec.md) 的全部字段、日期、URL、图片与文件名校验；失败时不在 `articles/` 留下半成品。
- [x] 为 helper 提供稳定的命令行入口供 skill 调用；参数或结构化输入不得要求 agent 手工拼接 YAML。
- [x] 在契约中明确并固化 `published_date` 缺失时的处理、slug 短标题的归一化/截断规则、`added_date` 使用的命名时区；每项都必须有固定输入对应唯一结果或明确错误，不能留给 agent 临场判断。

**Skill 工作流**

- [x] 将调用分为“本地预览”和“正式发布”两种模式；只有用户明确要求本地测试或预览时才进入本地预览，且不执行发布 preflight、Git 审阅、commit、push 或 CI 查询。
- [x] 接收单个 URL 及可选 tags / intro，定位 Codex Desktop 当前 Horizon workspace，并用 Git 根目录、`pyproject.toml` 项目名和文章契约文件验证仓库身份；workspace 不匹配或无写权限时给出明确提示并停止。
- [x] 开始前记录当前 HEAD、publication remote/branch 及远端旧 SHA；拒绝 detached HEAD、非发布分支、HEAD 未与远端旧 SHA 对齐或已经夹带本地未推送提交的状态。
- [x] 检查工作区已有修改但不强制要求完全干净：允许无关的未 staged / untracked 文件；若 index 已有任何 staged changes，则在修改 index 前停止并要求用户先处理，避免普通 `git commit` 混入既有暂存内容。
- [x] 调用 `baoyu-fetch` 获取正文及 title / author / cover / summary 等元数据，为外部进程设置超时并校验退出码与输出结构；CLI 缺失、Chrome/CDP 不可用、非零退出、超时、空/畸形输出或疑似截断均按失败处理。
- [x] 将网页正文和元数据视为不可信数据：正文中的提示词或操作指令不得改变 skill 工作流、触发额外命令、读取凭据或扩大文件访问范围。
- [x] 抓取失败、正文不完整或必填元数据不确定时暂停并向用户说明；不得调用入库 helper，不得在正式 `articles/` 写 draft 或半成品。
- [x] 抓取成功后必须生成简体中文标题、摘要与正文；若原文已经是中文则保持原文。译文不得概括、遗漏、增补或重排，必须逐段对应并保留 Markdown 层级、列表、引用、链接与媒体顺序，并逐字保留代码块和原始 HTML 媒体标签。
- [x] 在预览和正式创建前，将原始 `fetched.md` 与中文 `body.md` 一并交给 helper；校验正文中文占比、逐段 block 序列以及章节结构、链接、图片、视频和代码块的保真性，失败时不渲染、不写正式文章。
- [x] 明确源 HTML 与最终页面的信任边界：skill 为保真保留原始标记，Horizon 渲染器用 allowlist/CSP 移除脚本、iframe、事件属性与不安全 URL，只呈现安全正文和 HTTPS 图片/视频。
- [x] 实现隔离的本地预览命令：抓取结果、结构化 manifest、临时文章源和渲染站点全部位于 Horizon workspace 之外；复用正式文章契约、`load_articles` 和 `render_curated`，且拒绝非空预览目录及位于 workspace 内的目标。
- [x] 本地预览通过只绑定 `127.0.0.1` 的静态服务器提供页面，并在 Codex Desktop 的真实浏览器中检查详情页、索引页、中文标题和正文、来源链接、日期、导航、图片及视频；断言正文媒体不超过段落栏宽，向用户报告本地 URL，并保持服务器运行供其检查。
- [x] 调用入库 helper 生成文章，展示元数据摘要、目标文件路径和完整 diff，确认正文图片与 `cover` 仍为原始 HTTPS URL。
- [x] 展示完整 diff 后要求用户明确选择“批准 commit & push”或“取消”；取消时不得 stage、commit、push 或触发 CI，并由用户选择保留或删除本次新生成的未提交文章文件。
- [x] 将用户批准绑定到文章文件哈希、完整 diff、提交信息、当前 HEAD、目标 remote/branch；提交前重新校验，任一值变化都必须重新展示 diff 并再次确认。
- [x] 获得批准后只 `git add articles/{slug}.md`，并断言 staged path 恰好只有该文件；提交信息精确使用 `clip(article): {slug}`，禁止 `git add .`，最终 commit patch 必须与用户批准的 diff 完全一致。
- [x] 使用显式 remote、branch 和非 force refspec 只推送本次文章 commit；push 前再次确认该 commit 的父提交等于已记录的远端旧 SHA，禁止推送额外 ref 或既有未推送提交。
- [x] push 失败时保留并报告唯一的本地 commit SHA、目标 ref 与失败原因，不得声称 CI 已触发；重试前重新读取远端状态并再次获得用户授权，只推送同一 SHA，不重新生成或重复提交。
- [x] push 成功后按 commit SHA 查询 `publish-articles.yml` run，报告 workflow URL、event、head branch、状态与 conclusion；不得用“最新一次 run”代替 SHA 关联，也不得把“已 push”表述为“已部署成功”。

## Validation

- [x] 使用 `skill-creator` 的结构校验器检查 `skills/horizon-add-article/SKILL.md` 的 frontmatter、名称、目录结构与 `agents/openai.yaml`。
- [x] 在全新 Codex Desktop 任务中确认既能显式调用，也能根据自然语言请求正确触发，并核实实际加载路径解析到当前 Horizon 工作副本中的权威 `SKILL.md`，而不是同名旧副本或缓存。
- [x] 单元测试入库 helper：YAML 转义、domain 规范化、日期、slug、tags、summary、cover、正文图片与原子写入均符合契约。
- [x] 单元测试重复 `source_url`、slug 冲突、缺失 `published_date`、非法 URL、非 HTTPS 图片和目标文件已存在场景；所有失败均不得覆盖文件或留下半成品。
- [x] 使用固定当前时间及时区边界样例，断言 `published_date` 缺失、slug 短标题和 `added_date` 三项规则得到契约规定的唯一日期、slug 或错误结果。
- [x] 分别模拟 `baoyu-fetch` CLI 缺失、CDP 不可用、非零退出、超时、空输出、畸形输出、正文疑似截断和关键元数据不确定；失败止于临时抓取输出，不调用入库 helper，也不触碰 Horizon 的 articles、index、HEAD、远端或 CI。
- [x] 使用包含“要求 agent 执行命令、读取凭据或忽略 skill”的正文 fixture 验证提示注入隔离；这些文字只能作为文章内容处理，不能产生额外工具调用或越权访问。
- [x] 在仓库中预先放置无关未 staged 修改与 untracked 文件后执行完整流程，断言最终 commit 只包含 `articles/{slug}.md`，其他工作区状态不变；再放置已有 staged changes，确认 skill 在修改 index 前停止且 staged 内容不变。
- [x] 对一篇有效文章执行到审阅阶段后选择取消；断言 HEAD、index、远端 refs 均未改变，并分别验证新文件被保留或安全删除；未 push 因而不会产生 CI run。
- [x] 在用户批准后、commit 前模拟文章文件或 HEAD 变化，确认 skill 强制重新校验与审阅；正常路径中断言最终 commit patch、commit message、目标 remote/branch 与批准内容完全一致。
- [x] 用合成的稳定 `baoyu-fetch` 输出 fixture 覆盖成功、错误页、异常退出、超时、空/畸形/缺字段/疑似截断和提示注入形态，并确认成功结果可由共享文章契约消费。
- [x] 单元测试本地预览：断言正式契约和渲染器可消费抓取结果、输出只位于仓库外、非空目标和 workspace 内目标被拒绝，并且 Horizon 的完整 Git 状态在预览前后保持不变。
- [x] 单元测试中文译文校验：纯英文正文、非中文标题/摘要、链接或媒体丢失、Markdown 结构变化及代码块修改均必须失败；合法中文译文可供预览与正式入库共同消费。
- [x] 单元测试普通段落保真：即使标题、列表、链接和媒体数量不变，缺少任一普通正文段落也必须失败。
- [x] 在 Codex Desktop 做一次本地端到端验收：输入真实 URL，经 `baoyu-fetch` 抓取、简体中文翻译、结构保真与共享契约校验和 Phase 2 渲染后，由 loopback HTTP 服务打开页面；确认文章详情、索引导航、所有远程图片和视频实际加载，且媒体宽度不超过正文栏。
- [x] 分别抓取 Anthropic 博客、知乎专栏和微信公众号真实 URL 做 live smoke test；确认正文完整、frontmatter 可由 `load_article` 读取、CI 渲染器可消费。
- [x] 在 Codex Desktop 中新建以 Horizon 为 workspace 的任务并调用 skill，确认它只访问当前 workspace；遇到未授权操作时只请求正常权限，不绕过沙箱。
- [x] 在临时 Git remote 验证 push 语义：远端 publication ref 只能从记录的旧 SHA 移动到批准的 commit SHA，不能多推 commit/ref；模拟 non-fast-forward、鉴权失败和网络中断，确认失败后重试只推送原 commit 一次。
- [ ] 真实 CI 验收只使用经用户授权的 Horizon `main` 和一篇确实待发布的文章；push 后查询 Actions run，断言 `workflow=publish-articles.yml`、`event=push`、`head_sha` 等于本次 commit、`head_branch=main`，并记录 run URL 与最终 conclusion。workflow 已限制为 `main`，测试分支不会触发生产部署，不能替代本项验收。

Codex Desktop 已在全新 Horizon 任务中确认两个 skill 均已注册：`baoyu-url-to-markdown` 从 `~/.agents/skills/baoyu-url-to-markdown/SKILL.md` 加载，`horizon-add-article` 经用户级软连接解析到当前 Horizon 工作副本中的权威 `skills/horizon-add-article/SKILL.md`。live smoke test 使用 Anthropic `Claude takes research to new places`、知乎 `python OR-Tools解决约束规划问题`、微信公众号 `如何用《玉树芝兰》入门数据科学？` 三个公开页面；临时抓取正文分别为 6,084、4,440、14,319 字，均通过共享契约 `load_article`、详情页与索引页渲染，未写入正式 `articles/`。本地端到端验收再次使用 Anthropic 页面，在 `/private/tmp` 中完成抓取、简体中文翻译、结构保真校验和站点生成，通过 `127.0.0.1` 打开详情页；浏览器确认中文标题、章节、段落、列表、链接文字和图片说明均正常，原始链接与媒体未丢失。桌面端实测正文栏、普通段落、一个视频和两张正文图片宽度均为 680px，视频按约 16:9 加载，所有媒体均未超出正文栏。当前只剩真实 CI 验收：Horizon `main` 的本地 HEAD 仍领先 `origin/main`，安全 preflight 会按设计停止；同时还没有一篇经用户确认确实待发布的文章。因此未为通过清单而改写 Git 历史或向生产分支推送测试文章。

## Out of Scope

- 不自行实现通用网页正文提取器，也不 fork `baoyu-url-to-markdown`。
- 不建立独立 skill repo、插件市场包或 MCP server。
- 不提供或验收用户级手动安装、软链接管理和自动安装脚本。
- 不在本阶段验证 Claude Code、Trae、Cursor 等其他 agent 对该 skill 的发现与兼容性；`SKILL.md` 保持标准格式，为后续验证保留条件。
- 不支持无需本地 Horizon 工作副本、直接通过 GitHub API 入库的远端模式。
- V1 不支持批量 URL、草稿状态、付费墙绕过或自动修复不完整正文。
- 不由 skill 下载媒体、访问 COS、执行生产 HTML 渲染、发送邮件或运行 Twitter/AI 日报流水线；仓库外的隔离本地预览只复用 Phase 2 已有渲染器。
- 不修改 Phase 2 的文章详情、索引、媒体本地化与 CI 发布实现，除非为复用契约校验做必要的无行为变化重构。

# Phase 6：生产站点规范域名迁移

## Goal

将 Horizon 的生产规范地址从 `https://daily.signalfeed.site/d/${COS_SITE_PREFIX}` 迁移到 `https://www.signalfeed.site`，让 Phase 1 定义的根 `/`、`/daily/` 与 `/articles/` 结构直接位于规范域名下。迁移必须保留历史日报、精华文章、媒体与邮件交付状态；两个生产 workflow 使用同一部署根；旧公网链接按原路径永久重定向到新域名。COS 内部对象前缀可以因 bucket 隔离继续存在，但不得再出现在公开 URL、邮件链接或页面导航中。

## Dependencies

- Phase 1–5 已完成；当前生产树位于 COS 的 `d/${COS_SITE_PREFIX}/`，由 `.github/workflows/daily-summary.yml` 与 `.github/workflows/publish-articles.yml` 共同维护。
- 需要腾讯云 DNS、COS/CDN 自定义域名、HTTPS 证书和重定向规则的管理权限，以及 Horizon GitHub Actions secrets 的维护权限。
- 开始迁移前必须确认 `signalfeed-1257788828` bucket 根目录是否只供 Horizon 使用；未确认前不得把带 `--delete` 的同步目标改到 bucket 根目录。
- 当前 `COS_SITE_PREFIX` 仅从现有 secret 读取；不得把其真实值写入仓库、任务文档、测试 fixture 或 workflow 日志。

## Tasks

**目标地址与迁移决策**

- [x] 将唯一规范站点地址固化为 `https://www.signalfeed.site`；目标路径为根 `/`、日报 `/daily/{date}.html`、日报归档 `/daily/index.html`、文章库 `/articles/index.html` 与详情 `/articles/{slug}.html`。
- [x] 盘点 bucket 根目录和现有 `d/${COS_SITE_PREFIX}/` 的对象数量、总大小、关键文件及所有权，确认是否存在 Horizon 之外的对象；盘点过程只输出路径摘要和计数，不输出凭据或 secret 值。
- [x] 在以下两种策略中完成并记录唯一选择：专用 bucket 时把 Horizon 部署树迁到 bucket 根目录；共享 bucket 时保留内部对象前缀，并由 CDN/反向代理把 `www.signalfeed.site/*` 映射到该前缀。无论选择哪种策略，公网 URL 都不得包含 COS 前缀。
- [x] 制定可执行回滚点：保存迁移前对象清单与关键状态文件校验值，记录旧 DNS/CDN 配置和旧 workflow commit；回滚不得依赖 GitHub runner 临时磁盘。
- [x] 明确切换顺序为“新域名预部署并验证 → 修改应用规范地址 → 启用旧地址重定向 → 观察后清理可删除遗留物”，避免先改链接造成生产 404。

**DNS、HTTPS 与兼容入口**

- [x] 为 `www.signalfeed.site` 配置指向 Horizon COS/CDN 站点的 DNS 记录、自定义域名和有效 HTTPS 证书；裸域 `signalfeed.site` 与旧 `daily.signalfeed.site` 即使只承载重定向也必须保持有效证书，所有证书的域名、有效期与完整链均通过校验。
- [x] 在不影响当前站点的前提下，将现有生产树复制或映射到新域名；首次迁移不得使用会删除 bucket 根目录未知对象的命令。
- [x] 配置 `http://www.signalfeed.site/*` 到 `https://www.signalfeed.site/*` 的永久重定向，并为裸域 `https://signalfeed.site/*` 配置到 `https://www.signalfeed.site/*` 的永久重定向。
- [x] 配置旧地址 `https://daily.signalfeed.site/d/${COS_SITE_PREFIX}/{path}` 到 `https://www.signalfeed.site/{path}` 的永久重定向，保留路径和查询参数；旧域名根及其他 Horizon 旧入口也必须有确定的跳转目标。
- [x] 确保旧地址兼容层不会暴露 COS 控制台、目录列表、凭据或其他 bucket 对象；`COS_SITE_PREFIX` 不是访问控制机制。
- [x] 为 DNS、证书、CDN 回源/重写与重定向配置保留可审计记录，但仓库只记录非敏感配置说明，不提交云凭据或 secret 值。

**仓库配置与部署 workflow**

- [x] 将 `data/config.github.json` 的 `site.base_url` 改为精确值 `https://www.signalfeed.site`，不含尾部斜杠、路径前缀或环境变量占位符。
- [x] 根据已选迁移策略更新 `site.deploy_command`：专用 bucket 使用确认安全的根目录目标；共享 bucket 继续使用内部部署前缀。公开 `base_url` 与内部部署目标必须解耦。
- [x] 同步更新 `.github/workflows/daily-summary.yml` 和 `.github/workflows/publish-articles.yml` 的生产树恢复路径、发布路径与环境变量，确保两个 workflow 拉取和写回同一棵站点树。
- [x] 保持现有 `horizon-production-site` concurrency group，保证日报发布、文章发布和迁移操作不会并发覆盖站点。
- [x] 保留 `.horizon-state/email_delivery_state.json` 的恢复与独立写回语义；域名迁移不得重置已投递日期或文章 slug。
- [x] 保证 Phase 1 的根 `index.html` 仍由 `site_manifest.json` 跳转最新日报；不得用云端固定重定向绕过生成器而破坏无历史数据时的 `/daily/index.html` 回退。
- [x] 更新 workflow 静态测试，断言规范 `base_url`、两个 workflow 的同一部署根、状态文件路径、并发组及禁止 GitHub Pages 的约束；测试不得依赖真实 secret 值。
- [x] 排查代码、配置、文档模板和测试中作为生产地址使用的 `daily.signalfeed.site` 或 `/d/${COS_SITE_PREFIX}`；保留内容只能是明确标注的旧地址兼容规则或迁移说明。

**内容、邮件与缓存切换**

- [x] 用现有生产树生成新域名首批内容，确认 HTML 内导航、文章来源页之外的站内绝对链接、邮件 footer 与「本期新增精选文章」链接统一使用 `https://www.signalfeed.site`。
- [x] 确认 CSS、图片、视频和 GIF 仍通过相对资源路径加载，不因域名或内部对象前缀变化产生跨域、CSP、缓存键或 MIME 类型问题。
- [x] 在启用永久缓存前完成一次短 TTL 验证；切换稳定后再恢复生产缓存策略，避免错误重定向或 404 被长期缓存。
- [x] 迁移过程中保留旧站点可用，直到新域名端到端验收和两个生产 workflow 各成功运行一次；不得以删除旧对象作为切换完成的前置条件。
- [x] 记录旧地址兼容层的长期保留策略；已通过邮件或外部分享发布的 URL 不得在无重定向替代时失效。

## Validation

- [x] 本地加载生产配置 fixture，断言 `site.base_url == "https://www.signalfeed.site"`，渲染后的日报、文章库、详情页和邮件链接均不含 `daily.signalfeed.site`、`/d/` 前缀或未展开的环境变量。
- [x] 单元/静态测试覆盖已选部署策略的安全约束：根目录同步使用锚定排除规则保留兼容层；两个 workflow 必须使用同一恢复/发布根并保留 `.horizon-state`。
- [x] DNS 验收确认 `www.signalfeed.site` 解析到预期 COS/CDN 服务；HTTPS 验收确认证书覆盖 `www.signalfeed.site`、证书链有效且 HTTP 自动跳转 HTTPS。
- [x] 在 Codex Desktop 真实浏览器打开 `https://www.signalfeed.site/`，确认根入口跳转最新 `/daily/{date}.html`，页面样式、导航和媒体正常。
- [x] 打开 `/daily/index.html`、一篇历史日报、`/articles/index.html` 和至少一篇精华文章详情，确认均返回成功、站内导航正确、正文为预期内容且媒体全部加载。
- [x] 浏览器检查精华文章正文图片和视频不超过段落栏宽；控制台无 CSP、混合内容、跨域、404 或媒体解码错误。
- [x] 抓取新域名已发布 HTML 的站内链接与媒体 URL，确认不存在意外的旧域名、COS 前缀、localhost、runner 路径或未展开变量，并对全部内部链接执行可达性检查。
- [x] 分别请求旧日报、旧文章库和旧文章详情 URL，确认返回 `301` 或 `308` 永久重定向并落到路径等价的新 URL；查询参数保留且不存在循环或多余跳转链。
- [x] 用截获的 MIME 邮件执行 dry-run，确认 HTML、纯文本正文和 footer 中的日报/文章库链接全部使用新规范域名；不实际发送邮件。
- [x] 手动触发一次 `daily-summary.yml`，记录 run URL、commit SHA 和 conclusion；确认历史页面、文章、媒体和邮件交付状态均保留，发布目标未触碰 bucket 中无关对象。
- [x] 通过一篇经用户批准的新文章触发一次 `publish-articles.yml`，按文章 commit SHA 验证 workflow；确认新详情页出现在 `www.signalfeed.site`，日报树与状态文件未被覆盖。
- [x] 在两个 workflow 成功后复核 COS 对象清单与迁移前基线，解释所有新增、更新和删除；发现范围外删除时立即按记录的回滚点恢复。
- [x] 验收完成后记录最终 DNS/CDN 策略、两个 Actions run、旧地址重定向样例和浏览器验证结果；敏感值保持脱敏。

## Completion Record（2026-07-16）

- **迁移策略**：该 bucket 经盘点确认只承载 Horizon，规范树迁到 bucket 根目录；`d/${COS_SITE_PREFIX}/` 保持原样作为长期兼容与云端回滚副本。两个 workflow 都从 bucket 根恢复并向根发布，`--delete` 同步使用锚定的 `^d/.*$` 排除规则，不会删除兼容层。
- **回滚基线**：迁移前 workflow commit 为 `3f6d8de`；兼容树为 118 个对象、296.36 MB，迁移前 `index.html` 与 `site_manifest.json` 的 SHA-256 分别为 `372e22c145d6d82bce617d5d9904970338a5a0ceaf8fc103b02bcc5c44b5c90c` 和 `076bc5c27bbda68b56cc57f69087a53933fb6bfe26875d2ea2f587837dc3eae2`。回滚可将 DNS CNAME 恢复到 COS 静态网站入口并切回旧 commit，原兼容树无需从 runner 恢复。
- **DNS/CDN/HTTPS**：`www`、裸域和 `daily` 均通过腾讯 CDN 且状态为 `online`；`www` 回源现有 COS 静态网站，裸域与 `daily` 只承载 301。`www`/裸域证书有效期为 2026-07-15 至 2026-10-13，`daily` 为 2026-07-06 至 2026-10-04，三者均通过主机名和完整链校验。HTTP 强制跳转 HTTPS；旧日报 HTML 跳到 `/daily/`，旧文章与资产分别跳到 `/articles/` 和 `/assets/`，查询参数保持不变。
- **缓存策略**：切换期 DNS TTL 为 600 秒；发现预部署旧首页缓存后执行两次目录刷新并确认任务完成。最终 CDN 规则为首页、HTML、HTM 与 JSON 缓存 300 秒，其他指纹化静态资源缓存 30 天。
- **生产 runs**：[`daily-summary.yml` run 29433434309](https://github.com/dengd1937/Horizon/actions/runs/29433434309) 在 `e1827540d2e861b6d906426693dd543d89afa83c` 上成功；[`publish-articles.yml` run 29434589769](https://github.com/dengd1937/Horizon/actions/runs/29434589769) 在 `64590e603c1a46d06ad96ae312b53e379b4aa3c8` 上成功。日报 run 暴露的 `Path` 局部导入遮蔽问题已由 `64590e6` 修复，并加入日报编排回归测试；为避免同日重复邮件，修复后只重跑无邮件副作用的文章发布 workflow。
- **对象复核**：迁移后共 245 个对象、653.42 MB；其中旧兼容树仍为 118 个对象、296.36 MB，规范根为 127 个对象。相对迁移前总量净增 9 个，来自 `/daily/` 分区、最新日报媒体和根级 `.horizon-state/email_delivery_state.json`；未发现范围外删除。
- **自动验证**：432 项 pytest 通过；截获的 `multipart/alternative` MIME 中 HTML/纯文本/footer 均只使用规范域名且未实际发送。生产爬虫检查 15 个 HTML 页面和 112 个内部链接/媒体目标，全部可达，未发现旧域名、旧前缀、localhost、runner 路径或未展开变量。
- **浏览器验证**：Codex Desktop 中根入口跳到 `/daily/2026-07-15.html`；日报归档、历史日报、文章库和中文文章详情均正常。文章 1 张封面与 8 张懒加载正文图全部从 `/assets/articles/` 加载，正文图宽度为 680px，与段落栏相同；控制台为空。
- **长期策略**：不清理 `d/${COS_SITE_PREFIX}/` 兼容树，不把隐藏路径当成鉴权；已发布旧链接由 CDN 永久重定向。变更云配置时只在仓库记录域名、状态、计数和 run ID，不记录凭据或真实前缀。

## Out of Scope

- 不重新设计 Horizon 页面、品牌、导航或文章样式。
- 不迁移到 GitHub Pages、Vercel 或其他托管平台；仍使用腾讯 COS/CDN。
- 不把 `COS_SITE_PREFIX`、COS 凭据或云配置导出到仓库，也不以隐藏路径替代身份认证。
- 不改日报抓取、AI 摘要、文章翻译/入库或邮件投递业务逻辑；只更新它们生成和发布的规范站点地址。
- 不引入分析统计、访问鉴权、订阅管理或新的环境站点。

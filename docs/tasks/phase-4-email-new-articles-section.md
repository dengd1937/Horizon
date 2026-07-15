# Phase 4：邮件「本期新增」与 footer

## Goal

在每日摘要邮件中加入「本期新增精选文章」section（扫描 `articles/` 按入库时间筛选尚未投递的新增文章，无新增则隐藏），并在 footer 加文章库链接；markdown 与纯文本 alternative 两端一致，且跨 GitHub Actions runner 重启不丢交付状态。

## Dependencies

- Phase 2（frontmatter 规范与 `added_date`）已完成。
- 关键代码：`src/orchestrator.py`（`:241-250` 邮件 summary 生成与发送）、`src/services/email.py`（`:154` `send_daily_summary`、`:183` footer）、`src/ai/summarizer.py`（`generate_summary` 生成邮件版 markdown）。
- 邮件 summary 由 `DailySummarizer.generate_summary(site_base_url=...)` 生成（带阅读站深链的 markdown），经 `markdown.markdown()` 渲染，无结构化条目。

## Tasks

- [x] 在 `orchestrator.py` 邮件分支（`email_summary` 赋值后、`send_daily_summary` 调用前，约 `:249-250`）追加 markdown 小节 `## 本期新增精选文章`（扫 articles 源目录拼装，非改 AI prompt），内容为条目列表（标题 / 来源域 / 一行摘要 / 详情页链接 `{base_url}/articles/{slug}.html`）。
- [x] 实现「本期新增」判定纯函数：扫描 `articles/*.md`，按 `added_date` 与「上次发信日期」比较筛选；无新增时返回空，拼装处隐藏整个 section。
- [x] 「上次发信日期」与已投递文章 slug 由 `StorageManager` 的持久化邮件交付状态（`data/email_delivery_state.json`，按语言）读取；缺失时回退近 1 天。
- [x] 日期窗口包含上次成功日期，并排除该语言已投递 slug；同一天上次发信后新增的文章仍能进入下一封邮件，已投递文章不会因包含式边界重复发送。
- [x] 仅在全部收件人实际成功交付后，原子持久化该发信日期与文章 slug；部分/全部发送失败、禁用邮件、dry-run 或仅文章发布 workflow 均不得推进状态，避免漏报新增文章。
- [x] 每日 workflow 从 COS 恢复交付状态，并在运行结束后独立回写；状态不依赖临时 GitHub runner 文件系统，文章专用 workflow 只透传站点树、不修改交付状态。
- [x] `email.py` footer（`:183`）加一行可点击的 `文章库：{site_url}/articles/`，并规范化 `site_url` 尾部斜杠，避免 `//articles/`。
- [x] 纯文本 alternative 自动带同段（现有 `cleaned_summary` 流程），确认两端内容一致。
- [x] 详情页链接使用站点绝对 URL（`{config.site.base_url}/articles/{slug}.html`，参见 `orchestrator.py:239`），与 Phase 1 地址结构对齐。

## Validation

- [x] 单元测试：新增判定函数在含/不含新增 fixture 下筛选正确；section 拼装函数输出预期 markdown；空新增时 section 隐藏。
- [x] 用 fixture articles 构造 summary_md，调用邮件渲染，确认 HTML 与纯文本均含「本期新增」section 且条目字段完整。
- [x] 检查纯文本与 HTML 内容一致（顺序、条目、链接）。
- [x] 检查 footer 含 `文章库：{site_url}/articles/`。
- [x] 模拟成功、部分失败、全部失败、禁用与 dry-run，确认日期与文章 slug 只在全部收件人成功路径更新；`articles/**` 专用发布 workflow 不读取或更新该状态。
- [x] 单元测试同日边界：上次成功日期当天新增但尚未投递的文章会入选；同日已投递 slug 被排除。
- [x] workflow 静态测试确认每日任务从 COS 恢复并回写 `email_delivery_state.json`，跨 runner 执行仍保留状态。
- [x] 无新增场景下，确认 section 完全隐藏（HTML 与纯文本均不出现空标题）。
- [x] 检查详情页链接为绝对 URL 且路径与 Phase 1 一致（`/articles/{slug}.html`）。
- [x] 不实际发送邮件（用 fake / dry-run 或截获 MIME 对象断言）。

## Out of Scope

- 不做邮件打开率 / 点击追踪。
- 不做订阅人自助退订页。
- 不改邮件视觉模板（仅追加 section 与 footer 一行）。

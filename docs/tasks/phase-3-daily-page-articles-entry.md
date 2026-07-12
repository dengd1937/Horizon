# Phase 3：日报页文章库入口

## Goal

在日报与归档页加入文章库入口：顶部导航「文章库」与「归档」并列；footer 计数入口「文章库本周 +N」，让读者从日报侧发现精华文章库。

## Dependencies

- Phase 1（地址结构）、Phase 2（索引页 `/articles/` 可达）已完成。
- 关键代码：`src/render/site.py` digest mast（`:173`）、footer（`:183-184`）、`_index_page` 归档页头部。

## Tasks

- [ ] digest 页顶部 mast 加「文章库 ↗」入口，与「归档 ↗」并列，链向 `/articles/index.html`（`daily/` 下相对路径 `../articles/index.html`）。
- [ ] 归档页 `daily/index.html` 头部加「文章库」入口。
- [ ] digest footer 加计数入口「文章库本周 +N」（或「本月 +N」），链向文章库索引。
- [ ] 实现周/月新增计数纯函数：扫描 `articles/*.md`，按 `added_date` 统计自最近周/月起的新增数；无新增时不显示计数行。
- [ ] 确认各层级相对路径正确（`daily/{date}.html` → `../articles/`；`daily/index.html` → `../articles/`）。

## Validation

- [ ] 单元测试：周/月计数函数在含跨周/跨月 fixture 下计数正确；空文章库返回 0。
- [ ] Playwright 打开 `daily/{date}.html`，确认顶部「文章库」入口可见且跳转到 `/articles/index.html`。
- [ ] Playwright 确认 footer 计数与扫描结果一致；无新增时计数行隐藏。
- [ ] Playwright 打开 `daily/index.html`，确认头部文章库入口可见且跳转正确。
- [ ] Playwright 确认入口链接无 404。

## Out of Scope

- 不改文章库索引页与详情页本身（Phase 2）。
- 不做邮件中的文章入口（Phase 4）。
- 不做标签云 / 分类导航。

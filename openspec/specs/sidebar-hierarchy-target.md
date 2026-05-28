# 侧边栏层级 + 页面自动选中 — 目标

## CSS 层级
- `#novelPages .nav-item` 左边距 +16px，形成缩进
- `#novelPages .nav-section-label` 左边距 +12px
- 小说选择器下方加一条分割线

## 页面自动选中
- writing → 无独立下拉框（使用 params 传参），需保证 context 传入
- review → rNovel auto-select, trigger _loadReviewChs()
- chapters → cNovel auto-select, trigger _loadChapters()
- outlines → oNovel auto-select, trigger _loadOutlines()
- quality → qNovel auto-select, trigger _loadQuality()
- init-wizard → iwNovel auto-select（无 load 回调）
- gtNovel → _renderTablePage 内的通用选择器，auto-select 不触发 load（参数无法序列化）

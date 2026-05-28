# 侧边栏层级 + 页面自动选中

## Why
侧边栏小说专属链接无视觉层级，与全局链接混在一起没有区分。
部分页面仍需要手动在下拉框重选小说，使用不便。

## What
1. CSS: #novelPages 内 nav-item 左边缩进 16px，形成层级感
2. JS: remaining 6 个页面 (review/chapters/outlines/quality/init-wizard/writing) 的小说选择器自动填充上下文值

## Impact
- style.css: 新增 #novelPages .nav-item / .nav-section-label 样式
- app.js: 6 个 render 函数末尾加 _initNovelSelector 调用

# 侧边栏重构

## Why
侧边栏从最初的15页膨胀到24页，所有链接平铺导致难以导航。
小说专属页面（人物/伏笔/世界观等17页）应在选定小说后才显示。

## What
- 侧边栏顶部添加小说下拉选择器
- 小说专属链接折叠在 `#novelPages` 容器中，选中小说后显示
- `App.currentNovel` 作为全局上下文，页面间保持
- 添加 `_getNovel()` 辅助函数，各页面用上下文做默认值

## Impact
- `index.html`: 侧边栏重构（已完成）
- `app.js`: init() 填充选择器，setNovelContext()，navigate() 守卫
- 各 render 函数: 少量修改以使用 `_getNovel()`
- 无后端改动

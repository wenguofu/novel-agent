# React + Ant Design 重构 — 任务清单

## 最终状态 (2026-05-27)

### 测试
- 25 tests / 9 test files / 全绿
- TypeScript: 零错误

### 页面 (18 个完整 + 1 个占位)
✅ Dashboard, Writing, Review, Chapters, Outlines, Workflow
✅ Characters, Foreshadowing, WorldBuilding, PlotArcs, PacingControl, RevelationSchedule
✅ InitWizard, NewBook, NovelsPage, SearchPage, ConfigPage, QualityPage
🚧 Settings (占位)

### 构建
- Vite build: dist/index.html + 1.2MB JS (gzip 389KB)
- Flask 托管: 自动检测 `frontend/dist/` 存在时优先服务 React 版本

### 待后续
- [ ] Dark mode 切换
- [ ] 代码分割
- [ ] 清理旧 `portal/static/js/` (需用户确认)

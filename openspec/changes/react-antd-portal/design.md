# NovelForge React + Ant Design 重构方案

## 目标
将 portal/ 前端从 vanilla JS SPA（3400行单文件 `app.js`，内联模板字面量）迁移到 React 18 + Ant Design 5 + TypeScript。

## 范围
- 24 个页面，含复杂交互（SSE 流式写作、审稿、自动续写环、向导多步骤）
- ~70 个 API 端点
- Flask 后端不动，仅重写前端

## 技术栈
- React 18 + TypeScript
- Ant Design 5（组件库）
- React Router v6（路由）
- Zustand（状态管理，轻量替代 Redux）
- @microsoft/fetch-event-source（SSE 流式）
- Vite（构建工具）
- react-markdown + rehype-raw（Markdown 渲染）

## 项目结构
```
portal/
├── app.py                    # Flask 后端（不动）
├── content_db.py             # （不动）
├── config.py                 # （不动）
├── frontend/                 # 新 React 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/              # API 调用层
│       │   ├── client.ts     # fetch 封装 + SSE
│       │   ├── novels.ts
│       │   ├── chapters.ts
│       │   ├── ai.ts
│       │   ├── v3.ts         # 世界观/弧线/节奏/释放
│       │   ├── config.ts
│       │   └── workflow.ts
│       ├── stores/           # Zustand
│       │   ├── novelStore.ts # 当前小说上下文
│       │   ├── configStore.ts
│       │   └── uiStore.ts    # 侧栏状态等
│       ├── components/       # 共享组件
│       │   ├── Layout.tsx    # 侧栏 + 主内容
│       │   ├── NovelSelector.tsx
│       │   ├── StreamingOutput.tsx
│       │   ├── Markdown.tsx
│       │   └── WordBadge.tsx
│       └── pages/
│           ├── Dashboard.tsx
│           ├── Novels.tsx
│           ├── NewBook.tsx   # 向导
│           ├── Writing.tsx   # 写作台（核心）
│           ├── Chapters.tsx
│           ├── Outlines.tsx
│           ├── Review.tsx
│           ├── InitWizard.tsx
│           ├── Characters.tsx
│           ├── Foreshadowing.tsx
│           ├── WorldBuilding.tsx
│           ├── PlotArcs.tsx
│           ├── PacingControl.tsx
│           ├── RevelationSchedule.tsx
│           ├── Workflow.tsx
│           ├── Quality.tsx
│           ├── Search.tsx
│           ├── Config.tsx
│           └── Settings.tsx
```

## 路由设计
```
/                       → Dashboard（聚合 + 按小说）
/novels                 → Novels（项目列表）
/novels/new             → NewBook（创建向导）
/novels/:name           → 控制台（单小说视图）

# 以下路由需要 /novels/:name 前缀（从 novelStore 取当前小说）
/novels/:name/writing   → Writing
/novels/:name/chapters  → Chapters
/novels/:name/outlines  → Outlines
/novels/:name/review    → Review
/novels/:name/init      → InitWizard
/novels/:name/characters→ Characters
/novels/:name/foreshadowing → Foreshadowing
/novels/:name/world     → WorldBuilding
/novels/:name/arcs      → PlotArcs
/novels/:name/pacing    → PacingControl
/novels/:name/revelation→ RevelationSchedule
/novels/:name/workflow  → Workflow
/novels/:name/quality   → Quality

# 全局页
/search                 → Search
/config                 → Config
/settings               → Settings
```

## 数据流
```
  Zustand Store
  ┌─────────────────────────┐
  │ novelStore              │
  │ - currentNovel: string  │  ← 全局当前小说名
  │ - novels: Novel[]       │  ← 小说列表（缓存）
  │ - novelDetail: Novel    │  ← 当前小说详情
  ├─────────────────────────┤
  │ configStore             │
  │ - deepseekConfig        │
  │ - configured: bool      │
  ├─────────────────────────┤
  │ uiStore                 │
  │ - sidebarCollapsed      │
  │ - novelPagesVisible     │
  └─────────────────────────┘
```

## 实现策略

### 阶段 1：骨架（1天）
- [ ] Vite + React + AntD 项目初始化
- [ ] Layout（侧栏导航 + 主内容区）
- [ ] 路由配置
- [ ] API client 层（fetch + SSE 封装）
- [ ] novelStore + configStore
- [ ] Flask 后端配置 Vite dev proxy → localhost:35001

### 阶段 2：核心页面（2天）
- [ ] Dashboard（聚合 + 单小说视图）
- [ ] 创建向导（8步交互，最复杂之一）
- [ ] 写作台（SSE 流式 + 自动审稿 + 自动续写环）
- [ ] 审稿（两阶段进度 + 一键优化）

### 阶段 3：管理页面（1.5天）
- [ ] 章节浏览
- [ ] 大纲管理
- [ ] 人物管理
- [ ] 伏笔管理
- [ ] 工作流检查

### 阶段 4：V3 管理页 + 辅助页（1天）
- [ ] 世界观 / 剧情弧线 / 节奏 / 信息释放
- [ ] 初始化向导
- [ ] 质量报告
- [ ] 全文搜索
- [ ] 配置管理 / 设置

### 阶段 5：收尾（0.5天）
- [ ] 侧栏 collapse / dark mode
- [ ] 响应式适配
- [ ] 构建配置（Flask 静态文件托管）
- [ ] 清理旧文件

## 关键风险
1. **SSE 流式写作**：核心体验，需用 `@microsoft/fetch-event-source` 或原生 EventSource
2. **自动续写环**：后台循环生成，React 状态管理较复杂
3. **向导多步骤**：8 步含 AI 步骤，需 loading + 错误处理
4. **模板字面量嵌套**：原 app.js 的 JS 生成 HTML 全部改为 JSX，天然解决

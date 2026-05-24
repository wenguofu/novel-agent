# Novel Agent Architecture Optimization Plan

## Phase 1 — 数据层加固

### 1.1 版本管理
- 优化/重写前自动备份原章节
- 路径: `manuscript/.bak/ch-XXXX.rev{N}.md`
- 版本号递增，最多保留 5 个版本
- Portal 文件 Tab 可查看历史版本

### 1.2 脚本结果入库
- 审稿脚本输出写入 `content.db.reviews` 表
- 增加字段: `wc_ok`, `compliance_ok`, `forbidden_ok`, `bcontrast_count`, `judgment_groups`, `tell_count`
- 支持 SQL 查询: "列出所有字数不达标的章节"

## Phase 2 — 质量闭环

### 2.1 审稿→优化→复审闭环
- 优化完成后自动触发复审
- 对比优化前后分数变化
- 显示改善项/未修复项

### 2.2 质量报告 API
- `GET /api/content/quality-report/<novel>`
- 返回: 字数趋势、通过率、高频问题分布
- Portal 新增"质量报告"页面

## Phase 3 — 智能分析

### 3.1 跨章节一致性检测
- 检测同一角色在不同章节的行为/状态冲突
- 利用 content.db 的 FTS5 搜索角色名 + 关键状态词

### 3.2 写作节奏分析
- 分析高压/低压章节分布
- 检测连续低压疲劳段

## Phase 4 — 运维增强

### 4.1 Portal 仪表盘
- 首页增加小说状态总览卡片
- 待审章节数/待优化数/本周新增字数

### 4.2 Token 用量追踪
- 记录每次 API 调用的 token 消耗
- 新增 `token_usage` 表
- Portal 设置页展示用量

## 实施顺序
Phase 1 → Phase 2 → Phase 3 → Phase 4

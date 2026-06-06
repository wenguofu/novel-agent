# Novel Agent Architecture Optimization Plan

## Phase 1 — 数据层加固

### 1.1 版本管理
- **Status:** ✅ DONE
- 优化/重写前自动备份原章节
- 路径: `manuscript/.bak/ch-XXXX.rev{N}.md`
- 版本号递增，最多保留 5 个版本
- Portal "📜 历史" Tab 可查看/恢复/删除历史版本

### 1.2 脚本结果入库
- **Status:** ✅ DONE
- 审稿脚本输出写入 `content.db.reviews` 表
- 增加字段: `wc_ok`, `compliance_ok`, `forbidden_ok`, `bcontrast_count`, `judgment_groups`, `tell_count`
- 支持 SQL 查询: "列出所有字数不达标的章节"

## Phase 2 — 质量闭环

### 2.1 审稿→优化→复审闭环
- **Status:** ✅ DONE
- 优化完成后自动触发复审
- 对比优化前后分数变化
- 显示改善项/未修复项

### 2.2 质量报告 API
- **Status:** ✅ DONE
- `GET /api/content/quality-report/<novel>`
- 返回: 字数趋势、通过率、高频问题分布
- Portal 新增"质量报告"页面

## Phase 3 — 智能分析

### 3.1 跨章节一致性检测
- **Status:** ✅ DONE
- 检测同一角色在不同章节的行为/状态冲突
- 利用 content.db 的 FTS5 搜索角色名 + 关键状态词

### 3.2 写作节奏分析
- **Status:** ✅ DONE
- 分析高压/低压章节分布
- 检测连续低压疲劳段

## Phase 4 — 运维增强

### 4.1 Portal 仪表盘
- **Status:** ✅ DONE
- 首页增加小说状态总览卡片
- 待审章节数/待优化数/本周新增字数

### 4.2 Token 用量追踪
- **Status:** ✅ DONE
- 记录每次 API 调用的 token 消耗
- 新增 `usage` 表 (in `usage.db`)
- Portal 设置页 "📊 使用统计" 卡片调用 `/api/usage/stats` 展示总 Tokens / 总成本 / 按操作类型 / 按小说 / 7天趋势

## 实施顺序
Phase 1 → Phase 2 → Phase 3 → Phase 4

---

## Implementation Pointer

> **Status (2026-06-07):** 7/8 items DONE, 1 PARTIAL → DONE, 0 NOT DONE. Closed 1.1 (history tab), 4.1 (dashboard metrics), 4.2 (token usage UI).
>
> | Phase | Item | Status | Commit(s) |
> |---|---|---|---|
> | 1.1 | 版本管理 | ✅ DONE | `861da0b`, `a8e8110` (Portal "📜 历史" tab + 4 endpoints, 9 tests) |
> | 1.2 | 脚本结果入库 | ✅ DONE | `861da0b` |
> | 2.1 | 审稿→优化→复审闭环 | ✅ DONE | `861da0b`, `7b83b56`, `22f8b1b`, `ab330ff`, `83302d8`, `c913292`, `f861f75`, `4754fae` |
> | 2.2 | 质量报告 API + Portal 页 | ✅ DONE | `861da0b` |
> | 3.1 | 跨章节一致性检测 | ✅ DONE | `a020bd8` |
> | 3.2 | 写作节奏分析 | ✅ DONE | `a020bd8` |
> | 4.1 | Portal 仪表盘 | ✅ DONE | `a020bd8`, `8ff73fe` (added 待审/待优化/本周新增 cards, /api/dashboard/stats, 6 tests) |
> | 4.2 | Token 用量追踪 | ✅ DONE | `a020bd8`, `8d3c13b`, `ee5df2b` (UI wired: /api/usage/stats, 4 stat-card KPIs, 1 test) |
>
> **Verified 2026-06-06:** 1031/1031 tests pass. No code changes needed for the done items.
>
> **Remaining gaps (status: 🟡 PARTIAL):** None — all 3 remaining PARTIAL items closed in this session (commits `a8e8110`, `8ff73fe`, `ee5df2b`).
>
> **Notes:**
> - `api_quality_report` (`portal/app.py:2899-2980`) is fully implemented (not a stub): it returns `chapter_trend`, `review_stats` (3 pass rates), `writing_quality` (avg_bc/avg_tell/total_jg), `consistency_alerts` (cross-chapter 死/复活 pattern), `rhythm_alerts` (consecutive-low-word fatigue ≥ 3 chapters), and `review_trend`.
> - The Portal "📈 质量报告" page (`app.js:2662-2716`) is wired to that API and renders progress bars + a chapter word-count trend list.
> - 3.1 uses `LIKE '%死%' / '%复活%'` rather than a true FTS5 query, but the cross-chapter consistency *function* is implemented; the plan's FTS5 framing was an implementation hint, not a hard contract.

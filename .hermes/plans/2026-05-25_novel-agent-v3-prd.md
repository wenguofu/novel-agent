# Novel Agent v3 — 智能创作引擎 PRD

**版本**: v3.0.0  
**状态**: DRAFT — Awaiting Review  
**日期**: 2026-05-25  
**作者**: Hermes Agent + 用户

---

## 1. 目标 (Goal)

将 Novel Agent 从"文件驱动 + 固定 prompt"升级为 **"数据库驱动 + 按需加载上下文 + 向量检索"** 的智能创作引擎。

核心原则：**AI 创作时不应该把所有内容塞进 prompt，而应该像人类作者一样，写哪一章就翻看哪一部分资料。**

---

## 2. 当前痛点 (Current Pain Points)

| 痛点 | 现状 | 影响 |
|------|------|------|
| 上下文全量加载 | `_buildSystemPrompt` 一次性加载 project.md + characters.md + genre_bible.md 等 8 个文件，每文件 2500 字符 | Token 浪费严重，大部分内容与当前章节无关 |
| Token 硬编码 | 固定截断 2500/2000/3000 字符，无法按需分配 | 该详细的部分被截断，该简略的占用了空间 |
| 无向量检索 | RAG 有但未集成到写作流 | 无法根据当前章节内容智能检索最相关的上下文 |
| 领域数据散落 | 世界观/角色/伏笔/节奏等混在散文件中 | 无法结构化查询"第3卷需要填的坑有哪些" |
| 情感/节奏缺失 | 没有节奏控制和情感曲线数据 | AI 不知道这章该快还是慢、该爽还是虐 |
| 无法增量更新 | 写完一章后状态变更靠人工 | 角色状态、伏笔状态不会自动推进 |

---

## 3. 领域模型 (Domain Model) — 8 张核心表

### 3.1 novels（项目）
保持现有结构，增加 `style_profile`, `target_audience`, `pacing_profile` 字段。

### 3.2 world_building（世界观）
```
id, novel_id, domain (力量体系/地图/历史/种族/规则/禁忌),
name, content, related_vol, related_ch, tags, created_at
```
- 设计理念：将 world_bible.md 拆解为可查询的原子条目
- 示例：`domain=力量体系, name=斗气等级, content=斗者→斗师→...共9级`

### 3.3 characters（角色）— 已有，扩展
在现有表上增加：
- `emotional_state` — 当前情感状态（JSON: {mood, desire, fear, conflict}）
- `ability_level` — 当前能力等级
- `relationship_map` — 与其他角色的关系（JSON: [{target, type, intimacy, tension}]）

### 3.4 character_events（角色事件）— 已有

### 3.5 plot_arcs（剧情弧线）
```
id, novel_id, name, type (主线/支线/感情线/成长线),
volume_start, chapter_start, volume_end, chapter_end,
summary, milestones (JSON), status, priority
```
- 每条剧情线从起点到终点，包含里程碑节点

### 3.6 foreshadowing（伏笔）— 已有，扩展
增加字段：`hint_method`（暗示方式）, `reveal_method`（揭露方式）, `is_dark`（暗线伏笔）

### 3.7 pacing_control（节奏控制）
```
id, novel_id, volume, chapter_range,
pace_type (高潮/过渡/铺垫/释缓),
intensity (1-10), emotion_target (爽/虐/悬/燃/暖),
word_budget_min, word_budget_max, notes
```
- 每章或每段章节指定节奏类型和情感目标

### 3.8 revelation_schedule（信息释放计划）
```
id, novel_id, name, info_type (世界观/角色秘密/伏笔揭示/规则说明),
reveal_volume, reveal_chapter, content,
audience_knows (bool), protagonist_knows (bool),
priority
```
- 控制"读者知道什么 vs 主角知道什么"的信息差

### 3.9 chapters（章节）— 已有，扩展
增加：`pace_type`, `emotional_beat`, `foreshadowing_touched`（JSON）, `characters_appeared`（JSON）

---

## 4. 向量数据库增强 (Vector DB Enhancement)

### 4.1 分类索引策略
现有 chromadb 已有按类型分 chunk（chapter/character/outline/plot_arc/world_building 等）。
增强点：
- 新增索引类型：`pacing`, `emotional_beat`, `revelation`, `relationship`
- 每个 chunk 增加元数据：`volume`, `chapter`, `priority`, `token_estimate`

### 4.2 分类组合查询 (Category-Aware Query)
```
POST /api/rag/query
{
  "novel": "大强成神啦",
  "queries": [
    {"category": "character", "query": "付大强 当前状态", "max_tokens": 1500},
    {"category": "foreshadowing", "query": "待填坑伏笔 第1卷", "max_tokens": 2000},
    {"category": "pacing", "query": "第1章 节奏 情感", "max_tokens": 500},
    {"category": "world_building", "query": "乐园 规则 系统", "max_tokens": 1500},
    {"category": "plot_arc", "query": "主线剧情 当前进度", "max_tokens": 2000},
    {"category": "chapter_context", "query": "前章结尾 衔接", "max_tokens": 1000},
    {"category": "revelation", "query": "本章该揭示的信息", "max_tokens": 500},
    {"category": "emotional", "query": "角色情感状态 关系", "max_tokens": 1000}
  ],
  "total_max_tokens": 10000
}
```
- 每类独立检索，token 预算按需分配
- 总上限 10000 token（可配置）

### 4.3 智能上下文组装
不再一次性加载所有内容，而是根据：
1. 当前卷/章号 → 筛选相关范围的数据
2. 伏笔的 target_vol/target_ch → 判断是否需要在本章推进
3. 节奏表对应的 pace_type → 决定创作基调
4. 信息释放计划 → 决定哪些设定可以透露

---

## 5. System Prompt 重构 (V3 Prompt Architecture)

### 5.1 分层 Prompt 结构
```
[Layer 0: 核心指令]           ≈ 500 tokens
  - 你是谁，基本规则，质量要求

[Layer 1: 项目元信息]         ≈ 300 tokens
  - 项目名、类型、目标读者、总字数目标
  - 来源: novels 表

[Layer 2: 当前章节上下文]      ≈ 800 tokens
  - 当前卷/章号、卷纲要求、危机关卡
  - 上一章结尾（2000 chars 用于衔接）
  - 来源: outlines + danger_issues + chapters

[Layer 3: 角色按需加载]        ≈ 2000 tokens
  - 本章出场角色档案 + 当前状态 + 情感
  - 来源: characters + character_events (向量检索 top-3 related)

[Layer 4: 伏笔待办]            ≈ 1500 tokens
  - 本章需要推进/填坑的伏笔
  - 来源: foreshadowing (按 target_vol/ch 筛选 + 向量检索)

[Layer 5: 世界观按需]          ≈ 1500 tokens
  - 与本章相关的世界观设定
  - 来源: world_building (向量检索 top-5 related)

[Layer 6: 节奏/情感指引]       ≈ 500 tokens
  - 本章节奏类型、情感目标、字数范围
  - 来源: pacing_control

[Layer 7: 信息释放约束]        ≈ 500 tokens
  - 本章可以/不可以透露的信息
  - 来源: revelation_schedule

[Layer 8: 剧情弧线锚点]        ≈ 1000 tokens
  - 当前卷的主线/支线进度和里程碑
  - 来源: plot_arcs

[Layer 9: 写作风格]            ≈ 500 tokens
  - 风格预设 + 用户自定义指令
  - 来源: style_presets + user input
──────────────────────────────────
  总计:                        ≈ 9100 tokens
  上限:                        10000 tokens
```

### 5.2 动态调整策略
- 如果某层检索结果不足，预算自动分配给其他层
- 优先级：Layer 3 > Layer 4 > Layer 5 > Layer 6/7/8
- 主角章节优先加载角色层，过渡章节优先加载世界观层

---

## 6. API 重构

### 6.1 新增端点
| 端点 | 功能 |
|------|------|
| `POST /api/context/build` | 构建分层上下文（替代 `_buildSystemPrompt` 的大部分逻辑） |
| `POST /api/rag/query` | 分类向量检索，返回结构化结果 |
| `GET /api/context/stats/{novel}/{vol}/{ch}` | 返回该章节可用的上下文统计（各层 token 预估） |
| `POST /api/pacing/generate` | AI 辅助生成节奏表 |
| `POST /api/init/full` | 一键从文件初始化所有领域表 |

### 6.2 废弃端点
- `/api/ai/stream` 的后端 system prompt 构建逻辑 → 移至 `/api/context/build`
- 前端 `_buildSystemPrompt` → 改为调用后端 API

---

## 7. 初始化/迁移流程

### 7.1 首次初始化
```
1. 读取 project.md → novels 表
2. 读取 world_bible.md → 拆解为 world_building 条目
3. 读取 characters.md → characters 表（已有）
4. 读取 full_story_arc.md → plot_arcs 表
5. 读取 outline/vol-XX-chapters.md → foreshadowing + pacing_control + revelation_schedule
6. 构建向量索引（chromadb upsert）
7. 验证：检查所有表数据完整性
```

### 7.2 增量更新
- 每次生成/重写章节后，自动更新：
  - characters.current_status / emotional_state
  - foreshadowing.status（如果本章填了坑）
  - chapters.pace_type / emotional_beat
  - 向量索引增量更新

---

## 8. 开发计划 (TDD)

### Phase 1: 数据库 Schema ✓（先写 migration test）
- [ ] 1.1 编写 `test_schema.py` — 验证所有表创建、外键、索引
- [ ] 1.2 实现 world_building 表 + CRUD
- [ ] 1.3 实现 plot_arcs 表 + CRUD
- [ ] 1.4 实现 pacing_control 表 + CRUD
- [ ] 1.5 实现 revelation_schedule 表 + CRUD
- [ ] 1.6 扩展 characters/foreshadowing/chapters 表字段
- [ ] 1.7 编写 `test_init_from_files.py` — 验证初始化正确性

### Phase 2: 向量检索增强 ✓
- [ ] 2.1 编写 `test_rag_category_query.py` — 验证分类查询正确性
- [ ] 2.2 实现分类查询 API（支持 token 预算分配）
- [ ] 2.3 实现智能 token 预算管理器
- [ ] 2.4 验证结果排序和相关性

### Phase 3: Context Builder ✓
- [ ] 3.1 编写 `test_context_builder.py` — 验证分层 prompt 组装
- [ ] 3.2 实现 `/api/context/build` 端点
- [ ] 3.3 实现 token 预算动态分配
- [ ] 3.4 编写 `test_token_budget.py` — 验证不超 10000 上限

### Phase 4: 前端重构 ✓
- [ ] 4.1 `_buildSystemPrompt` → 替换为 API 调用
- [ ] 4.2 添加「领域数据」管理页面（world/pacing/revelation/plot_arc）
- [ ] 4.3 添加 token 用量可视化
- [ ] 4.4 添加初始化向导（一键初始化全部领域）

### Phase 5: 增量更新 ✓
- [ ] 5.1 章节生成后自动更新角色状态和伏笔状态
- [ ] 5.2 章节保存后触发增量向量索引
- [ ] 5.3 编写 `test_incremental_update.py`

### Phase 6: 集成测试 ✓
- [ ] 6.1 端到端测试：创建项目 → 初始化 → 生成第一章 → 验证上下文质量
- [ ] 6.2 Token 用量回归测试
- [ ] 6.3 性能测试（context build < 3s）

---

## 9. 文件变更清单

### 新增文件
```
portal/content_db.py          # 扩展（+200 lines）
portal/context_builder.py     # 上下文组装引擎（~300 lines）
portal/rag_engine.py          # 向量检索增强（~200 lines）
portal/token_budget.py        # Token 预算管理（~150 lines）
portal/init_engine.py         # 一键初始化引擎（~200 lines）
tests/test_schema.py          # Schema 测试
tests/test_context_builder.py # 上下文构建测试
tests/test_token_budget.py    # Token 预算测试
tests/test_init.py            # 初始化测试
```

### 修改文件
```
portal/app.py                 # 新增 API 端点
portal/static/js/app.js       # 前端简化 _buildSystemPrompt
portal/templates/index.html   # 新增侧边栏链接
```

### 不动文件
```
agent-system/                 # 保持现有 RAG 基础设施
novels/                       # 文件系统不动（DB 是查询层）
```

---

## 10. 风险与权衡

| 风险 | 缓解 |
|------|------|
| 向量检索延迟 | 本地 chromadb，预加载索引；超时 2s fallback 到 DB 查询 |
| Token 预算超限 | 硬限制 + 优先级裁剪（Layer 3 > 4 > 5 > ...） |
| 初始化质量依赖 AI 解析 | 提供手动编辑 UI，允许人工修正 |
| 文件与 DB 不同步 | 每次操作后双写；提供 `sync` 命令手动修复 |
| 复杂度增加 | 分 Phase 交付，Phase 1-2 即可独立工作 |

---

## 11. 成功指标

- [ ] 生成第一章的 token 消耗降低 40%+（当前 ≈9000 tokens 全量，目标 ≈5000 tokens 按需）
- [ ] 上下文相关性提升：人工评审 5 章，确认加载的上下文 80%+ 与本章直接相关
- [ ] 伏笔填坑率：系统自动提醒的待填伏笔中，AI 成功处理率 > 70%
- [ ] Context build API 响应时间 < 3s
- [ ] 所有测试通过（Phase 1-6）

---

*Review 后进入 Phase 1 TDD 开发。*

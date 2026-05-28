# Target Architecture (v3)

## Overview
Novel Agent v3 upgrades from "flat file + fixed prompt" to "domain model + vector retrieval + smart context assembly". The AI gets exactly what it needs for the current chapter, nothing more, nothing less.

## Key Changes

| Dimension | v2 | v3 |
|-----------|----|----|
| Data storage | Filesystem primary, DB secondary | DB primary (domain tables), filesystem as backup |
| Context loading | 8 files × 2500 chars = flat | 9-layer on-demand assembly from DB + vector |
| System prompt | Built in JS client-side | Built server-side via `/api/context/build` |
| Token budget | Hard-coded truncation | Category-aware allocation, max 10000 |
| Vector retrieval | External scripts only | Integrated into context builder |
| Pacing/emotion | None | pacing_control + revelation_schedule tables |
| State updates | Manual | Auto-incremental after chapter save |
| Tests | 0 | TDD: test-first for every module |

## New Database Tables

### world_building
```sql
id, novel_id(FK), domain TEXT, name TEXT, content TEXT,
related_vol INTEGER, related_ch INTEGER, tags TEXT,
created_at, updated_at
```
Domains: 力量体系, 地图, 历史, 种族, 规则, 禁忌, 组织, 其他

### plot_arcs
```sql
id, novel_id(FK), name TEXT, type TEXT, volume_start INTEGER,
chapter_start INTEGER, volume_end INTEGER, chapter_end INTEGER,
summary TEXT, milestones TEXT(JSON), status TEXT, priority TEXT
```
Types: 主线, 支线, 感情线, 成长线

### pacing_control
```sql
id, novel_id(FK), volume INTEGER, chapter_start INTEGER,
chapter_end INTEGER, pace_type TEXT, intensity INTEGER,
emotion_target TEXT, word_budget_min INTEGER,
word_budget_max INTEGER, notes TEXT
```
pace_type: 高潮, 过渡, 铺垫, 释缓
emotion_target: 爽, 虐, 悬, 燃, 暖, 惧

### revelation_schedule
```sql
id, novel_id(FK), name TEXT, info_type TEXT,
reveal_volume INTEGER, reveal_chapter INTEGER,
content TEXT, audience_knows BOOL,
protagonist_knows BOOL, priority TEXT
```
info_type: 世界观, 角色秘密, 伏笔揭示, 规则说明

## Extended Existing Tables

### characters (add columns)
- `emotional_state TEXT` — JSON: {mood, desire, fear, conflict}
- `ability_level TEXT` — current power level
- `relationship_map TEXT` — JSON: [{target, type, intimacy, tension}]

### foreshadowing (add columns)
- `hint_method TEXT` — how it was hinted
- `reveal_method TEXT` — how it should be revealed
- `is_dark BOOL` — dark foreshadowing (hidden from reader)

### chapters (add columns)
- `pace_type TEXT` — assigned pacing type
- `emotional_beat TEXT` — emotional tone achieved
- `foreshadowing_touched TEXT` — JSON: [fid1, fid2, ...]
- `characters_appeared TEXT` — JSON: [{name, role_in_chapter}]

## New API Endpoints

### Context Builder (core)
```
POST /api/context/build
  Request: {novel, volume, chapter_num, style, instructions, max_tokens: 10000}
  Response: {system_prompt, layers: [{name, tokens_used, content}], total_tokens}
```
Replaces `_buildSystemPrompt` in JS. Server-side assembly with:
1. Core instructions (500 tokens)
2. Project meta (300)
3. Chapter context — outline + danger_issue + prev ending (800)
4. Characters on-demand — vector search top-3 (2000)
5. Foreshadowing pending (1500)
6. World building relevant — vector search top-5 (1500)
7. Pacing/emotion guide (500)
8. Revelation constraints (500)
9. Plot arc milestones (1000)
10. Writing style (500)
Total max: 10000 tokens, dynamically allocated

### RAG Enhanced
```
POST /api/rag/query
  Request: {novel, queries: [{category, query, max_tokens}], total_max_tokens}
  Response: {results: [{category, chunks, tokens_used}], total_tokens}
```
Category-aware retrieval with per-category token budgets.

### Init Engine
```
POST /api/init/full
  Request: {novel}
  Response: {tables: {world_building: N, plot_arcs: N, pacing: N, revelation: N, ...}}
```
One-click init from existing files: project.md → novels, world_bible.md → world_building, characters.md → characters, full_story_arc.md → plot_arcs, outlines → pacing_control + revelation_schedule.

### Stats
```
GET /api/context/stats/{novel}/{vol}/{ch}
  Response: {available_layers: [{name, tokens_available, item_count}], total_available}
```

## System Prompt V3 Structure
```
[Layer 0] ═══ 核心指令 (500) ═══
[Layer 1] ═══ 项目元信息 (300) ═══
[Layer 2] ═══ 当前章节上下文 (800) ═══
[Layer 3] ═══ 角色按需 (2000) ═══    ← vector search top-3
[Layer 4] ═══ 伏笔待办 (1500) ═══    ← DB filter by target_vol/ch
[Layer 5] ═══ 世界观按需 (1500) ═══  ← vector search top-5
[Layer 6] ═══ 节奏/情感 (500) ═══    ← DB filter by vol/ch_range
[Layer 7] ═══ 信息释放 (500) ═══     ← DB filter by reveal_vol
[Layer 8] ═══ 剧情弧线 (1000) ═══   ← DB filter by vol range
[Layer 9] ═══ 写作风格 (500) ═══     ← user config
────────────────────────────────────
  Max: 10000 tokens
```

## New Files
```
portal/context_builder.py    # Context assembly engine (~300 lines)
portal/rag_engine.py         # Enhanced vector retrieval (~200 lines)
portal/token_budget.py       # Token budget manager (~150 lines)
portal/init_engine.py        # Full initialization orchestrator (~200 lines)
tests/test_context_builder.py
tests/test_token_budget.py
tests/test_schema.py
tests/test_init.py
tests/test_rag_engine.py
```

## Modified Files
```
portal/content_db.py         # +4 new tables, +extended columns, +init functions
portal/app.py                # +5 new endpoints, context/build replaces JS builder
portal/static/js/app.js      # _buildSystemPrompt → API call, +management pages
portal/static/js/api.js      # +context/build, +rag/query, +init/full
portal/templates/index.html  # +nav items for new pages
```

## Migration
- Filesystem stays as source-of-truth for raw content
- `init/full` reads files, parses, populates DB
- `context/build` reads from DB + vector, never from filesystem directly
- Incremental: after chapter save, update relevant DB rows + vector chunks

## TDD Strategy
Each Phase follows RED-GREEN-REFACTOR:
1. **RED**: Write test that fails (baseline behavior)
2. **GREEN**: Implement minimal code to pass
3. **REFACTOR**: Clean up, close loopholes

Phase 1: Schema tests → table creation → CRUD tests → CRUD implementation
Phase 2: RAG tests → category query → token budget → integration
Phase 3: Context builder tests → layer assembly → token enforcement
Phase 4: Frontend tests → API integration → UI updates
Phase 5: Incremental update tests → state tracking → vector sync
Phase 6: E2E tests → full workflow validation

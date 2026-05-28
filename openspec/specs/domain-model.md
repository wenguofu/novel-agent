# domain-model (v3)

## Purpose
Domain-driven data model for novel planning. 12 tables covering all 8 dimensions of novel architecture.

## Entity-Relationship
```
novels (1)
 ├── outlines (1:N) — volume-level chapter outlines
 ├── chapters (1:N) — individual chapters
 │   └── reviews (1:N) — per-chapter review records
 ├── danger_issues (1:N) — per-chapter crisis design
 ├── characters (1:N) — character profiles
 │   └── character_events (1:N) — state change timeline
 ├── foreshadowing (1:N) — Chekhov's gun management
 ├── world_building (1:N) — world setting entries (v3 NEW)
 ├── plot_arcs (1:N) — story arc definitions (v3 NEW)
 ├── pacing_control (1:N) — chapter pacing/emotion design (v3 NEW)
 └── revelation_schedule (1:N) — information release plan (v3 NEW)
```

## Table Schemas

### world_building (v3 NEW)
```sql
id, novel_id(FK), domain, name, content, related_vol, related_ch, tags
```
Domains: 力量体系, 地图, 历史, 种族, 规则, 禁忌, 组织, 其他
Index: `idx_wb_novel`, `idx_wb_domain`

### plot_arcs (v3 NEW)
```sql
id, novel_id(FK), name, type, volume_start, chapter_start,
volume_end, chapter_end, summary, milestones(JSON), status, priority
```
Types: 主线, 支线, 感情线, 成长线
Index: `idx_pa_novel`

### pacing_control (v3 NEW)
```sql
id, novel_id(FK), volume, chapter_start, chapter_end,
pace_type, intensity(1-10), emotion_target,
word_budget_min, word_budget_max, notes
```
pace_type: 高潮, 过渡, 铺垫, 释缓
emotion_target: 爽, 虐, 悬, 燃, 暖, 惧
Index: `idx_pc_novel`

### revelation_schedule (v3 NEW)
```sql
id, novel_id(FK), name, info_type, reveal_volume, reveal_chapter,
content, audience_knows(BOOL), protagonist_knows(BOOL), priority
```
info_type: 世界观, 角色秘密, 伏笔揭示, 规则说明
Index: `idx_rs_novel`

### characters (v3 EXTENDED)
Added columns: `emotional_state` (TEXT), `ability_level` (TEXT), `relationship_map` (TEXT/JSON)

### foreshadowing (v3 EXTENDED)
Added columns: `hint_method` (TEXT), `reveal_method` (TEXT), `is_dark` (INTEGER)

### chapters (v3 EXTENDED)
Added columns: `pace_type`, `emotional_beat`, `foreshadowing_touched` (JSON), `characters_appeared` (JSON)

## Migration
- `init_db()` creates all tables (idempotent via IF NOT EXISTS)
- `migrate_v3()` adds extended columns (idempotent via try/except)
- Production DB migrated: 4 new tables, characters(22 cols), foreshadowing(19 cols), chapters(15 cols)

## Init Engine
```
init_all_from_files(novel) → {success, tables: {world_building:N, plot_arcs:N, ...}, errors:[]}
  ├── init_world_building_from_file → parses world_bible.md
  ├── init_plot_arcs_from_file → parses full_story_arc.md
  ├── init_pacing_from_outline → parses outline/vol-XX-chapters.md
  ├── init_revelation_from_outline → parses outline for reveal hints
  ├── init_characters_from_files → parses characters.md (smart filtering)
  └── init_foreshadowing_from_outline → scans outline for foreshadowing markers
```
API: `POST /api/init/full/<novel>`

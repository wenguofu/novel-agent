# Current Architecture (v3.3)

> Last updated: 2026-05-30

## Overview
Novel Agent v3.3 is a Flask + React web portal for AI-assisted Chinese web novel writing (1M-3M words). It connects directly to DeepSeek API, manages novels via filesystem + unified database, and provides writing/review/optimization workflows with a multi-agent architecture.

## Stack
- **Backend**: Python 3.9+, Flask + Flask-CORS, SQLAlchemy ORM, httpx
- **Database**: SQLite (dev) / MySQL (production) via `DATABASE_URL` env var, pymysql driver
- **Frontend**: React 18 + TypeScript, Vite, Ant Design 5, Zustand, TanStack Query, react-markdown
- **AI**: DeepSeek API (chat completions + SSE streaming)
- **RAG**: chromadb + sentence-transformers (BAAI/bge-small-zh-v1.5)
- **Port**: 35001

## Database Architecture (v3.3)

### Unified Single Database
All tables consolidated into one database (`DATABASE_URL`). Replaces the old 3-file SQLite architecture.

```
novels, outlines, chapters, reviews, danger_issues,
foreshadowing, characters, character_events,
world_building, plot_arcs, pacing_control, revelation_schedule,
genre_rules, story_volumes, volume_plans, alias_names, project_meta,
banned_words, compliance_rules, alias_registry, style_presets, deepseek_config,
usage, daily_stats
```
**24 tables total** — no FTS5 virtual tables. Full-text search uses LIKE with substring matching.

### Data Access Layer
- **`db.py`** — SQLAlchemy engine/session factory, reads `DATABASE_URL`, auto-configures SQLite PRAGMA or MySQL connection pooling
- **`models_orm.py`** — 26 ORM models (SQLAlchemy declarative base), dialect-agnostic
- **`repository.py`** — Repository pattern with dict-based API, 110+ methods covering all CRUD operations
- **`content_db.py`** — Compatibility layer: all public functions delegate to `repository.get_repo()`
- **`run_v2.py`** — Launcher: initializes schema, seeds config, patches context builder for volume-scoping, starts Flask

### MySQL Migration
```bash
DATABASE_URL=mysql+pymysql://user:pass@host:3306/novel_agent python run_v2.py
```
- Auto-detects engine type from URL
- SQLite: PRAGMA WAL + foreign_keys, NullPool
- MySQL: pymysql driver, QueuePool (pool_size=5, max_overflow=10, pool_recycle=3600)
- Data migration: `scripts/migrate_sqlite_to_mysql.py`

## API Endpoints

### Writing & Generation
- `POST /api/context/build` — 12-layer context assembly with token budget
- `POST /api/ai/stream` — SSE streaming to DeepSeek
- `POST /api/novels/<name>/generate-chapter` — server-side chapter gen + gate check
- `POST /api/novels/<name>/review-chapter` — AI review + script checks → JSON+MD output
- `POST /api/novels/<name>/chapters/<ref>/edit` — save chapter + auto-complete gate + auto-update state
- `GET/POST /api/novels/<name>/outline/<vol>` — outlines in YAML (preferred) or Markdown

### Gate & Workflow
- `GET /api/novels/<name>/gate-status` — auto-init + auto-detect completed phases
- `POST /api/workflow/preflight/<novel>` — pre-generation checks
- `POST /api/workflow/postflight/<novel>` — post-generation enforcement

### Domain CRUD (all RESTful)
| Resource | Endpoint |
|----------|----------|
| Characters | `/api/characters/<novel>` |
| Foreshadowing | `/api/foreshadowing/<novel>` |
| World Building | `/api/world_building/<novel>` |
| Plot Arcs | `/api/plot_arcs/<novel>` |
| Pacing | `/api/pacing_control/<novel>` |
| Revelations | `/api/revelation_schedule/<novel>` |
| Genre Rules | `/api/genre_rules/<novel>` |
| Story Volumes | `/api/story_volumes/<novel>` |
| Volume Plans | `/api/volume_plans/<novel>` |
| Alias Names | `/api/alias_names/<novel>` |
| Project Meta | `/api/project_meta/<novel>` |

### Config & Usage
- `GET/POST /api/config` — DeepSeek API config
- `/api/config-db/<table>` — banned_words, compliance_rules, style_presets, alias_registry CRUD
- `GET /api/usage/stats` — token usage statistics
- `GET /api/usage/daily` — daily aggregated stats

### Content & Search
- `GET /api/content/search?q=<query>` — LIKE-based full-text search (chapters, outlines, reviews)
- `GET /api/content/stats/<novel>` — novel statistics
- `GET /api/content/quality-report/<novel>` — chapter quality metrics

## Context Builder (12-Layer, Token-Budgeted)

```
Layer 0:  Core Instructions (500 tok)
Layer 1:  Project Meta (300 tok) — novels table via repo
Layer 2:  Chapter Context (800 tok) — YAML outline + danger_issue + prev ending
Layer 3:  Characters (2000 tok) — active in current volume
Layer 4:  Foreshadowing (1500 tok) — unresolved, filtered by target_vol
Layer 5:  World Building (1500 tok) — entries in vol±1 range
Layer 6:  Pacing/Emotion (500 tok) — pacing_control lookup
Layer 7:  Revelation (500 tok) — revelation_schedule for current vol
Layer 8:  Plot Arcs (1000 tok) — active arcs spanning current vol
Layer 9:  RAG Memory (2000 tok) — semantic search via ChromaDB
Layer 10: State Evolution (1500 tok) — character/world change tracking
Layer 11: Style (500 tok) — multi-style fingerprint merge
Total: 12000 tok, TokenBudget dynamic allocation
```

All context builder layers use `repository.get_repo()` for data access — no raw SQL.

## File System ↔ DB Sync

- `init_all_from_files(novel_name)` — full initialization from all Markdown/YAML files
- `sync_novel_from_files(novel_name)` — sync outlines, chapters, reviews from filesystem
- `incremental_sync(novel_name, path)` — single-file change sync
- `auto_update_after_save()` — update character appearances, foreshadowing status after chapter save

All sync functions use repository methods for DB writes.

## Stage Gate System

7-phase gate with auto-detection:
- `phase1_opening` — project.md exists
- `phase2_arc` — full_story_arc.md exists
- `phase3_volume_outline` — outline YAML/MD exists
- `phase4_chapter_planning` — manual
- `phase5_writing` — manuscript chapters exist
- `phase6_review` — review files exist
- `phase7_status_update` — current_status.md exists

## Agent System

Located in `agent-system/`:
- `team/agent-*.md` (12 files) — YAML frontmatter with schema, prerequisites, signatures
- `workflows/` — chapter/new-book/volume/review workflows
- `scripts/` — stage_gate, agent_executor, agent_tracker, compliance, style fingerprints, RAG pipeline
- `check_character_arc.py` — uses repository layer for DB access

## Frontend Architecture

- **Framework**: React 18 + TypeScript, Ant Design 5, Vite 8
- **Routing**: react-router-dom v6, 20+ pages
- **State**: Zustand (novelStore, configStore, uiStore)
- **Data Fetching**: TanStack Query (React Query v5)
- **Streaming**: SSE via fetch API + ReadableStream reader

### Key Pages
| Page | Route | Purpose |
|---|---|---|
| Dashboard | `/` | Novel list, stats, token tracking |
| Writing | `/writing` | Single-chapter generation with gate check + auto-review |
| Outlines | `/outlines` | YAML outline editor with AI generation |
| Review | `/review` | Chapter review with script checks + AI |
| Characters | `/characters` | Character CRUD + topology graph |
| WorldBuilding | `/world-building` | World settings CRUD |
| PlotArcs | `/plot-arcs` | Plot arc management |
| Foreshadowing | `/foreshadowing` | Foreshadowing tracker |
| Search | `/search` | Full-text search across content |
| Quality | `/quality` | Quality reports and metrics |
| Config | `/config` | API config + banned words + style presets |
| Onboarding | `/onboarding` | 6-step new book wizard |

## Style System

16 distilled style fingerprints (8 literary + 8 web novel):
- Literary: 鲁迅, 古龙, 余华, 金庸, 海明威, 沈从文, 汪曾祺, 张爱玲
- Web Novel: 番茄, 辰东, 猫腻, 烽火戏诸侯, 老鹰吃小鸡, 卖报小郎君, 会说话的肘子, 爱潜水的乌贼

Multi-style merge: comma-separated → averaged metrics + unioned vocab + combined excerpts.

## Testing

- **Backend**: 77 pytest tests (schema, init, context builder, RAG, reviews, token truncation, sidebar)
- **Frontend**: 8 vitest tests (stores, API client, page rendering)

## Key v3.3 Changes from v3.2

1. **Unified Database**: Single DB via SQLAlchemy ORM, MySQL support via `DATABASE_URL`
2. **Repository Layer**: All DB access through `repository.py` (110+ methods), no raw sqlite3 in production code
3. **FTS5 Removed**: Full-text search uses LIKE with substring matching (MySQL compatible)
4. **Simplified Launcher**: `run_v2.py` handles schema init, config seed, context builder patching
5. **Idempotent Sync**: `init_*_from_file` functions no longer create duplicates on re-run
6. **Connection Leaks Fixed**: `context_builder.py` no longer leaks raw DB connections
7. **init_config_db.py Deprecated**: Configuration now managed by `init_unified_db.py` and `repository.init_config_seed()`

# Current Architecture (v3)

## Overview
Novel Agent v3 is a Flask-based web portal for AI-assisted Chinese web novel writing. It connects directly to DeepSeek API, manages novels via filesystem + SQLite, and provides writing/review/optimization workflows.

## Stack
- **Backend**: Python 3.11, Flask + Flask-CORS, SQLite (2 DBs), httpx
- **Frontend**: Vanilla JS (SPA), no framework, CSS custom properties
- **AI**: DeepSeek API (chat completions + SSE streaming)
- **RAG**: chromadb + sentence-transformers (bge-zh-v1.5)
- **Port**: 35001

## Database Schema

### content.db (12 tables + 3 FTS5 virtual tables)
```
novels: id, name, title, genre, subgenre, word_goal, total_chapters, total_words
outlines: id, novel_id(FK), volume, content, word_count
chapters: id, novel_id(FK), volume, chapter_num, chapter_ref, content, title, word_count, content_hash
reviews: id, novel_id(FK), chapter_ref, chapter_id, ai_review, script_* (4 flag cols), word_count
danger_issues: id, novel_id(FK), volume, chapter_num, content
foreshadowing: id, novel_id(FK), name, description, category, status, introduced_vol/ch, target_vol/ch, resolved_vol/ch, resolution_note, priority
characters: id, novel_id(FK), name, role, gender, age, identity, personality, appearance, background, current_status, current_vol/ch, lifeline, arc, ending, notes
character_events: id, novel_id(FK), character_id(FK), event_type, description, vol, ch, chapter_ref, source
world_building: id, novel_id(FK), domain, name, content, related_vol, related_ch, tags
plot_arcs: id, novel_id(FK), name, type, volume_start/chapter_start/end, summary, milestones(JSON), status
pacing_control: id, novel_id(FK), volume, chapter_start/end, pace_type, intensity, emotion_target, word_budget_min/max
revelation_schedule: id, novel_id(FK), name, info_type, reveal_volume/chapter, content, audience_knows, protagonist_knows
```
FTS5: chapters_fts(title,content), outlines_fts(content), reviews_fts(ai_review,script_detail)

### config.db (4 tables)
banned_words, compliance_rules, alias_registry, style_presets

## API Endpoints (48 routes)

### Core
- `GET /` — SPA entry
- `GET/POST /api/novels` — list novels
- `GET /api/novels/<name>` — novel detail + chapter/volume stats
- `POST /api/novels/create` — create novel with AI-generated outline
- `GET /api/novels/<name>/file?path=` — read any file from novel dir
- `POST /api/novels/<name>/file/write` — write file

### Writing
- `POST /api/novels/<name>/generate-chapter` — server-side chapter generation (streaming)
- `POST /api/ai/stream` — raw SSE streaming endpoint
- `POST /api/novels/<name>/review-chapter` — run scripts + AI review
- `POST /api/novels/<name>/optimize-chapter` — optimize based on review
- `GET /api/novels/<name>/chapters/<ref>` — read chapter
- `POST /api/novels/<name>/chapters/<ref>/edit` — edit/save chapter
- `GET/POST /api/novels/<name>/outline/<vol>` — read/edit outlines
- `GET /api/novels/<name>/danger-issue/<vol>/<ch>` — read danger issues
- `GET /api/novels/<name>/reviews/<ch_ref>` — read reviews
- `GET/POST /api/novels/<name>/status` — read/update status

### Workflow Enforcement
- `POST /api/workflow/preflight/<novel>` — pre-generation gate checks
- `POST /api/workflow/postflight/<novel>` — post-generation enforcement
- `POST /api/novels/<name>/enforce-pipeline` — full 11-step pipeline

### Foreshadowing
- `GET /api/foreshadowing/<novel>` — list, filter by status
- `GET /api/foreshadowing/<novel>/unresolved` — get pending items for current vol/ch
- `POST /api/foreshadowing/<novel>` — add
- `PUT/DELETE /api/foreshadowing/<novel>/<id>` — update/delete
- `POST /api/foreshadowing/<novel>/resolve/<id>` — mark resolved
- `POST /api/foreshadowing/<novel>/init` — init from outline

### Characters
- `GET /api/characters/<novel>` — list
- `GET /api/characters/<novel>/<id>` — detail + events
- `POST /api/characters/<novel>` — add
- `PUT/DELETE /api/characters/<novel>/<id>` — update/delete
- `POST /api/characters/<novel>/<id>/event` — add event
- `POST /api/characters/<novel>/init` — init from characters.md

### Config
- `GET/POST /api/config[/save/test]` — DeepSeek API config
- `GET/POST/PUT/DELETE /api/config-db/<table>` — config.db CRUD

### Content
- `GET /api/content/search?q=&novel=&limit=` — FTS5 search
- `GET /api/content/stats/<novel>` — novel stats
- `POST /api/content/sync` — sync files→DB
- `GET /api/content/quality-report/<novel>` — quality report

### Cleanup
- `POST /api/novels/<name>/cleanup-bak` — delete .bak files

### V3 Context Engine (new)
- `POST /api/context/build` — server-side 9-layer context assembly
- `GET /api/context/stats/<novel>/<vol>/<ch>` — context statistics
- `POST /api/rag/query` — category-aware vector retrieval with token budgets
- `POST /api/init/full/<novel>` — one-click full initialization from files
- `POST /api/characters/<novel>/<id>/event` — add character event

### System Prompt Architecture (v3)
Server-side via `context_builder.py` — 9-layer assembly:
1. Core instructions (500 tok)
2. Project meta — DB lookup (300 tok)
3. Chapter context — outline + danger + prev ending (800 tok)
4. Characters — DB query top-5 (2000 tok)
5. Foreshadowing — DB filter by target_vol (1500 tok)
6. World building — DB query relevant entries (1500 tok)
7. Pacing/emotion — DB filter by vol/ch (500 tok)
8. Revelation — DB filter by reveal_vol (500 tok)
9. Plot arcs — DB filter by vol range (1000 tok)
10. Style (500 tok)
Total: max 10000 tok, dynamically allocated.
JS `_buildSystemPrompt` is now a thin API wrapper (saved ~200 lines).

### System Prompt Architecture (v2 — deprecated)
Located in `_buildSystemPrompt()` in app.js (async, ~100 lines):
1. Loads 6 context files in parallel
2. Loads current_status.md (1500 chars)
3. Loads outline section matching current chapter (2000 chars)
4. Loads danger_issue (1000 chars)
5. Loads unresolved foreshadowing from API (dynamic)
6. Loads previous chapter ending (2000 chars)
7. Assembles into flat system prompt string
**Total**: ~12K chars, hard-coded truncation per file, no vector retrieval

## Frontend Architecture
- Single SPA with hash-routing: `navigate(view, params)`
- Views: dashboard, novels, new-book, writing, chapters, review, outlines, quality, search, config, settings, workflow, foreshadowing, characters
- Writing flow: `_genChapter` → `_streamChapter` → SSE parse → auto-save
- Review flow: `_runReview` → scripts + AI → `_optimizeFromReview` → re-review
- Modal system: `App.modal(title, body, footer, width)` returns modal element
- Markdown renderer: `App.renderMarkdown(text)` — simple regex-based

## Agent System (external scripts)
Located in `agent-system/scripts/`:
- `stage_gate.py` — 7-phase gate enforcement
- `analyze_chapter.py` — word count + structure + binary patterns + banned names
- `detect_forbidden_patterns.py` — forbidden writing patterns
- `check_compliance.py` — compliance rules
- `validate_review.py` — review quality validation
- `verify_continuity.py` — cross-chapter continuity
- `rhythm_check.py` — narrative rhythm analysis
- `rag_index.py` — build chromadb index from novel files
- `rag_query.py` — semantic search with type filters
- `rag_context.py` — auto context injection
- `agent_tracker.py` — agent execution tracking

## Known Issues
1. System prompt assembles all context client-side (JS), no server-side optimization
2. Token budgets are hard-coded per file, no dynamic allocation
3. Vector DB (chromadb) not integrated into writing workflow — only used by external scripts
4. No pacing/emotion/revelation data model
5. FTS5 snippet column index was buggy (fixed: 2→1/0)
6. `_buildSystemPrompt` was called without `await` (fixed)
7. `qualityCards` was undefined (fixed)
8. No automated tests

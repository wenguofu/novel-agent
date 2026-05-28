# Novel Agent v3 — Smart Context Engine

## Why
v2 loads all context blindly (8 files × 2500 chars = 12000 chars flat). The AI gets irrelevant content and misses relevant content. Token waste is ~40%. No pacing/emotion control. No automated state tracking.

## What Changes

### New domain tables
4 new tables (world_building, plot_arcs, pacing_control, revelation_schedule) + 3 existing tables extended (characters, foreshadowing, chapters)

### Context engine replaces JS prompt builder
Server-side `/api/context/build` assembles layered context from DB + vector DB. Categories with per-layer token budgets. Max 10000 tokens.

### Vector retrieval integrated
chromadb queries with category filters. Dynamic token allocation per query. Falls back to DB-only if chromadb unavailable.

### One-click initialization
`/api/init/full` reads existing files, parses, populates all domain tables.

### Auto state tracking
Chapter save triggers: character status updates, foreshadowing resolution checks, vector index increment.

### TDD from day 1
Every module has tests written FIRST, then implementation.

## Impact
- `content_db.py`: +~300 lines (new tables, extended schemas, init functions)
- `app.py`: +~200 lines (new endpoints, context/build replaces JS logic)
- New files: context_builder.py, rag_engine.py, token_budget.py, init_engine.py (~850 lines total)
- `app.js`: -~80 lines (_buildSystemPrompt simplified to API call), +~100 lines (new management pages)
- Tests: ~500 lines across 5 test files
- Zero breaking changes to existing API — all new endpoints are additive
- Filesystem stays as backup/source-of-truth, not primary read target

## Risk
- chromadb dependency: if unavailable, fall back to DB-only context
- Token budget tuning: may need iteration based on real chapter quality
- Init quality: parsing markdown is lossy — UI allows manual correction

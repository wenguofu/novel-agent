# Phase 1: Schema
- [ ] Write `tests/test_schema.py` — verify all 12 tables exist with correct columns
- [ ] Add world_building table to content_db.py SCHEMA
- [ ] Add plot_arcs table
- [ ] Add pacing_control table
- [ ] Add revelation_schedule table
- [ ] Extend characters: add emotional_state, ability_level, relationship_map
- [ ] Extend foreshadowing: add hint_method, reveal_method, is_dark
- [ ] Extend chapters: add pace_type, emotional_beat, foreshadowing_touched, characters_appeared
- [ ] Run tests → all pass
- [ ] Write `tests/test_schema_crud.py` — verify CRUD for all new tables
- [ ] Implement CRUD functions for world_building
- [ ] Implement CRUD for plot_arcs
- [ ] Implement CRUD for pacing_control
- [ ] Implement CRUD for revelation_schedule
- [ ] Run tests → all pass

# Phase 2: Init Engine
- [ ] Write `tests/test_init.py` — verify init from files populates all tables correctly
- [ ] Implement world_building init (parse world_bible.md → domain entries)
- [ ] Implement plot_arcs init (parse full_story_arc.md → arc entries)
- [ ] Implement pacing_control init (parse outline vol-XX-chapters.md → pacing entries)
- [ ] Implement revelation_schedule init (parse outline for info release hints)
- [ ] Implement orchestration in init_engine.py (/api/init/full)
- [ ] Run tests → all pass

# Phase 3: RAG Engine
- [ ] Write `tests/test_rag_engine.py` — verify category queries return relevant results
- [ ] Implement category-aware query builder
- [ ] Implement token budget allocation across categories
- [ ] Implement fallback to DB-only mode
- [ ] Add /api/rag/query endpoint
- [ ] Run tests → all pass

# Phase 4: Context Builder
- [ ] Write `tests/test_context_builder.py` — verify layered prompt assembly
- [ ] Write `tests/test_token_budget.py` — verify max 10000 token enforcement
- [ ] Implement token_budget.py
- [ ] Implement context_builder.py (9-layer assembly)
- [ ] Add /api/context/build endpoint
- [ ] Add /api/context/stats endpoint
- [ ] Run tests → all pass

# Phase 5: Frontend
- [ ] Replace _buildSystemPrompt with API call to /api/context/build
- [ ] Add world building management page
- [ ] Add pacing control management page
- [ ] Add plot arcs management page
- [ ] Add revelation schedule management page
- [ ] Add token usage visualization to writing page
- [ ] Add init wizard page
- [ ] Update API client (api.js)
- [ ] Update navigation (index.html)
- [ ] Manual testing: generate chapter, verify context quality

# Phase 6: Incremental Updates + Integration
- [ ] Write `tests/test_incremental.py` — verify state updates after chapter save
- [ ] Implement auto-update: characters.current_status after chapter save
- [ ] Implement auto-update: foreshadowing status after chapter save
- [ ] Implement auto-update: vector index increment after chapter save
- [ ] Write `tests/test_e2e.py` — full workflow: init → generate → verify
- [ ] Integration test: init project, generate ch1, verify context quality
- [ ] Performance test: context/build < 3s
- [ ] Performance test: token savings > 40% vs v2

# Phase 7: Archive
- [ ] Update openspec/specs/current-architecture.md → v3
- [ ] Archive this change

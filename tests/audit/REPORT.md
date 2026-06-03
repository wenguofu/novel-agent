# Test Failure Audit Report
Generated: 2026-06-03T13:53:03.945499Z

## Totals
- PASS: 82
- FAILED: 22
- ERROR: 15

## Failures by File

### `tests/test_context_builder.py` (1)
- **FAILED** `tests/test_context_builder.py::TestContextStats::test_context_stats_structure` — 

### `tests/test_generate_context.py` (2)
- **FAILED** `tests/test_generate_context.py::TestGenerateChapterUsesV3Context::test_build_context_includes_pacing_when_exists` — 
- **FAILED** `tests/test_generate_context.py::TestGenerateChapterUsesV3Context::test_build_context_falls_back_gracefully` — 

### `tests/test_incremental.py` (5)
- **ERROR** `tests/test_incremental.py::TestCharacterStateUpdate::test_add_event_updates_status` — 
- **ERROR** `tests/test_incremental.py::TestCharacterStateUpdate::test_update_character_current_position` — 
- **ERROR** `tests/test_incremental.py::TestForeshadowingUpdate::test_resolve_foreshadowing` — 
- **ERROR** `tests/test_incremental.py::TestForeshadowingUpdate::test_unresolved_filter_works` — 
- **ERROR** `tests/test_incremental.py::TestChapterMetadata::test_update_chapter_pacing` — 

### `tests/test_init.py` (8)
- **ERROR** `tests/test_init.py::TestWorldBuildingInit::test_wb_init_creates_entries` — 
- **ERROR** `tests/test_init.py::TestWorldBuildingInit::test_wb_init_domains` — sqlit...
- **ERROR** `tests/test_init.py::TestPlotArcsInit::test_pa_init_creates_entries` — sq...
- **ERROR** `tests/test_init.py::TestPacingInit::test_pc_init_creates_entries` — sqli...
- **ERROR** `tests/test_init.py::TestPacingInit::test_pc_init_correct_pace_type` — sq...
- **ERROR** `tests/test_init.py::TestRevelationInit::test_rs_init_creates_entries` — ...
- **ERROR** `tests/test_init.py::TestFullInit::test_full_init_returns_summary` — sqli...
- **ERROR** `tests/test_init.py::TestFullInit::test_full_init_is_idempotent` — sqlite...

### `tests/test_memory_layer.py` (1)
- **FAILED** `tests/test_memory_layer.py::TestMemoryIntegration::test_fallback_state_context` — 

### `tests/test_reviews_schema.py` (2)
- **FAILED** `tests/test_reviews_schema.py::TestReviewsTableComplete::test_reviews_has_all_quality_columns` — 
- **FAILED** `tests/test_reviews_schema.py::TestReviewsTableComplete::test_quality_report_aggregate_queries_work` — 

### `tests/test_schema.py` (15)
- **FAILED** `tests/test_schema.py::TestNewTables::test_world_building_table_exists` — 
- **FAILED** `tests/test_schema.py::TestNewTables::test_world_building_columns` — Ass...
- **FAILED** `tests/test_schema.py::TestNewTables::test_plot_arcs_table_exists` — Ass...
- **FAILED** `tests/test_schema.py::TestNewTables::test_plot_arcs_columns` — Assertio...
- **FAILED** `tests/test_schema.py::TestNewTables::test_pacing_control_table_exists` — 
- **FAILED** `tests/test_schema.py::TestNewTables::test_pacing_control_columns` — Ass...
- **FAILED** `tests/test_schema.py::TestNewTables::test_revelation_schedule_table_exists` — 
- **FAILED** `tests/test_schema.py::TestNewTables::test_revelation_schedule_columns` — 
- **FAILED** `tests/test_schema.py::TestNewTables::test_characters_extended_columns` — 
- **FAILED** `tests/test_schema.py::TestNewTables::test_foreshadowing_extended_columns` — 
- **FAILED** `tests/test_schema.py::TestNewTables::test_chapters_extended_columns` — ...
- **FAILED** `tests/test_schema.py::TestCRUD::test_world_building_crud` — sqlite3.Ope...
- **FAILED** `tests/test_schema.py::TestCRUD::test_plot_arcs_crud` — sqlite3.Operatio...
- **FAILED** `tests/test_schema.py::TestCRUD::test_pacing_control_crud` — sqlite3.Ope...
- **FAILED** `tests/test_schema.py::TestCRUD::test_revelation_schedule_crud` — sqlite...

### `tests/test_sidebar.py` (2)
- **ERROR** `tests/test_sidebar.py::TestNovelContextAPI::test_list_novels_returns_data` — 
- **ERROR** `tests/test_sidebar.py::TestNovelContextAPI::test_genre_rules_requires_novel_id` — 

### `tests/test_token_truncation.py` (1)
- **FAILED** `tests/test_token_truncation.py::TestTokenTruncation::test_truncation_respects_budget_with_large_content` — 
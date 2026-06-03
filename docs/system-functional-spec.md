# Novel Agent — System Functional Spec

> Machine-generated + manual supplements. Source of truth: `portal/app.py` AST.
> Auto-generated: 2026-06-03T15:04:37Z. Inventory: 83 endpoints.
>
> Regenerate: `python3 scripts/inventory_endpoints.py && python3 scripts/render_spec.py`
> Verify: `python3 scripts/verify_spec.py` (5 checks).

---

## 1. Architecture Overview

Flask + React portal. Unified SQLite/MySQL DB. 12-layer system prompt. DeepSeek SSE.
See [README.md](../../README.md) for stack details and
[openspec/specs/context-builder.md](../../openspec/specs/context-builder.md) for
the layer architecture.

### 1.1 Inventory Coverage

This spec is data-driven: every endpoint section is auto-generated from an AST
scan of `portal/app.py`. The scanner detects:

- **Route + methods** (per `@app.route(...)` decorator)
- **Function name + line number**
- **Docstring (first line)**
- **Direct `repo.<method>()` calls** in the endpoint body
- **Direct `db.<method>()` / `session.<method>()` calls** in the endpoint body
- **Tables read** (inferred from repository method names via the
  `get_X` / `list_X` / `upsert_X` heuristic)

### 1.2 Known AST Limitations

The scanner only inspects the endpoint function body directly. It does NOT
follow:

- Calls inside helper methods of wrapper classes (e.g.
  `WizardHandler.step()` invoked from a regular function endpoint).
- Bare function calls to module-level imports (this codebase mostly uses
  `repo = get_repo(); repo.method()` instead, which is detected).
- Decorators that aren't `@app.route(...)` (e.g. `@app.get`, `@app.post`
  shortcut decorators — not used in this codebase).

For high-value endpoints not detected automatically, see the Manual Notes.

---

## 2. Data Model (83 tables)

See [`portal/models_orm.py`](../../portal/models_orm.py) for canonical
definitions. Brief grouping:

| Group | Tables |
|-------|--------|
| Project | `novels`, `project_meta`, `alias_names`, `style_presets` |
| Story structure | `story_volumes`, `volume_plans`, `chapter_outlines`, `outlines`, `chapters`, `reviews` |
| Domain | `characters`, `foreshadowing`, `world_building`, `plot_arcs`, `pacing_control`, `revelation_schedule`, `genre_rules` |
| Workflow | `story_tracking`, `stage_gates`, `danger_issues` |
| Config (separate DB on MySQL) | `banned_words`, `compliance_rules`, `style_presets` |

---

## 3. Repository Layer (102 methods)

Auto-extracted from `portal/repository.py`. Each method listed with its
parameter list, defaults, docstring, and inferred table name.

- `repo.add_alias_name(self, novel_name, category, alias_name, description, scope, first_chapter)` → reads/writes `alias_names` — 
- `repo.add_alias_registry(self, real_name, alias, category, notes)` → reads/writes `alias_registrys` — 
- `repo.add_banned_word(self, word, category, replacement, severity)` → reads/writes `banned_words` — 
- `repo.add_character(self, novel_name, name, role)` → reads/writes `characters` — Add a character, return id.
- `repo.add_character_event(self, novel_name, cid, description, event_type, vol, ch, chapter_ref, source)` → reads/writes `character_events` — 
- `repo.add_compliance_rule(self, rule_key, rule_value, description, category)` → reads/writes `compliance_rules` — 
- `repo.add_foreshadowing(self, novel_name, name, description, category, introduced_vol, introduced_ch, target_vol, target_ch, priority)` → reads/writes `foreshadowings` — 
- `repo.add_genre_rule(self, novel_name, rule_category, rule_content, is_required)` → reads/writes `genre_rules` — 
- `repo.add_pacing(self, novel_name, volume, chapter_start, chapter_end)` → reads/writes `pacings` — 
- `repo.add_plot_arc(self, novel_name, name, arc_type)` → reads/writes `plot_arcs` — 
- `repo.add_revelation(self, novel_name, name, info_type, reveal_volume, reveal_chapter, content, priority)` → reads/writes `revelations` — 
- `repo.add_story_volume(self, novel_name, vol_num)` → reads/writes `story_volumes` — 
- `repo.add_style_preset(self, name, description, prompt, is_active)` → reads/writes `style_presets` — 
- `repo.add_world_building(self, novel_name, domain, name, content, related_vol, related_ch, tags)` → reads/writes `world_buildings` — 
- `repo.clear_alias_names(self, novel_name)` → reads/writes `clear_alias_names` — 
- `repo.clear_genre_rules(self, novel_name)` → reads/writes `clear_genre_rules` — 
- `repo.clear_project_meta(self, novel_name)` → reads/writes `clear_project_metas` — 
- `repo.clear_story_volumes(self, novel_name)` → reads/writes `clear_story_volumes` — 
- `repo.clear_volume_plans(self, novel_name)` → reads/writes `clear_volume_plans` — 
- `repo.clear_world_building(self, novel_name)` → reads/writes `clear_world_buildings` — 
- `repo.delete_alias_registry(self, aid)` → reads/writes `alias_registrys` — 
- `repo.delete_banned_word(self, bid)` → reads/writes `banned_words` — 
- `repo.delete_character(self, cid)` → reads/writes `characters` — 
- `repo.delete_compliance_rule(self, rid)` → reads/writes `compliance_rules` — 
- `repo.delete_foreshadowing(self, fid)` → reads/writes `foreshadowings` — 
- `repo.delete_novel(self, novel_name)` → reads/writes `novels` — 
- `repo.delete_outline(self, novel_name, volume)` → reads/writes `outlines` — 
- `repo.delete_style_preset(self, sid)` → reads/writes `style_presets` — 
- `repo.get_chapter(self, novel_name, chapter_ref)` → reads/writes `chapters` — 
- `repo.get_chapter_by_num(self, novel_name, volume, chapter_num)` → reads/writes `chapters` — 
- `repo.get_chapter_content_hash(self, novel_name, chapter_ref)` → reads/writes `chapter_content_hashs` — 
- `repo.get_character(self, novel_name, cid)` → reads/writes `characters` — 
- `repo.get_config(self, key)` → reads/writes `configs` — 
- `repo.get_danger_issue(self, novel_name, volume, chapter_num)` → reads/writes `danger_issues` — 
- `repo.get_foreshadowing_for_volume(self, novel_name, volume)` → reads/writes `foreshadowing_for_volumes` — Get foreshadowing scoped to a specific volume.
- `repo.get_novel(self, novel_name)` → reads/writes `novels` — 
- `repo.get_novel_by_id(self, nid)` → reads/writes `novels` — 
- `repo.get_novel_stats(self, novel_name)` → reads/writes `novel_stats` — Get aggregate stats for a novel (word counts, review counts, etc).
- `repo.get_outline(self, novel_name, volume)` → reads/writes `outlines` — 
- `repo.get_pacing(self, novel_name, volume, chapter_num)` → reads/writes `pacings` — 
- `repo.get_plot_arcs_for_volume(self, novel_name, volume)` → reads/writes `plot_arcs_for_volumes` — Get active plot arcs spanning the current volume.
- `repo.get_previous_chapter(self, novel_name, volume, chapter_num)` → reads/writes `previous_chapters` — Get the immediately preceding chapter for continuity.
- `repo.get_project_meta(self, novel_name, key)` → reads/writes `project_metas` — 
- `repo.get_recent_chapters(self, novel_name, limit)` → reads/writes `recent_chapters` — 
- `repo.get_recent_character_events(self, novel_name, volume, max_chapters)` → reads/writes `recent_character_events` — Get character events from recent chapters for state tracking.
- `repo.get_revelations_for_volume(self, novel_name, volume)` → reads/writes `revelations_for_volumes` — 
- `repo.get_review(self, novel_name, chapter_ref)` → reads/writes `reviews` — 
- `repo.get_review_count(self, novel_name)` → reads/writes `review_counts` — 
- `repo.get_story_volume(self, novel_name, vol_num)` → reads/writes `story_volumes` — 
- `repo.get_style_preset_by_name(self, name)` → reads/writes `style_presets` — Look up a single style preset by name. Returns None if not found.
- `repo.get_total_usage(self)` → reads/writes `total_usages` — 
- `repo.get_unresolved_foreshadowing(self, novel_name, current_vol, current_ch)` → reads/writes `unresolved_foreshadowings` — Get unresolved foreshadowing that should be resolved soon.
- `repo.get_usage_breakdown(self, days)` → reads/writes `usage_breakdowns` — Get detailed usage breakdown by model and operation.
- `repo.get_usage_stats(self, days)` → reads/writes `usage_stats` — 
- `repo.get_volume_plan(self, novel_name, vol_num)` → reads/writes `volume_plans` — 
- `repo.get_world_building_for_volume(self, novel_name, volume, limit)` → reads/writes `world_building_for_volumes` — Get world building entries relevant to current volume.
- `repo.get_world_building_volume_plus_global(self, novel_name, volume, local_limit, global_limit)` → reads/writes `world_building_volume_plus_globals` — Get local-volume world building (vol-1..vol+1) PLUS a global sample.
- `repo.init_config_seed(self)` → reads/writes `init_config_seeds` — Seed config tables with default data (idempotent).
- `repo.list_alias_names(self, novel_name)` → reads/writes `alias_names` — 
- `repo.list_alias_registry(self)` → reads/writes `alias_registrys` — 
- `repo.list_banned_words(self)` → reads/writes `banned_words` — 
- `repo.list_chapters(self, novel_name, volume)` → reads/writes `chapters` — 
- `repo.list_character_events(self, cid, limit)` → reads/writes `character_events` — 
- `repo.list_characters(self, novel_name, role)` → reads/writes `characters` — 
- `repo.list_characters_active_in_volume(self, novel_name, volume)` → reads/writes `characters_active_in_volumes` — Characters whose current_vol is within ±1 of the given volume.
- `repo.list_compliance_rules(self)` → reads/writes `compliance_rules` — 
- `repo.list_foreshadowing(self, novel_name, status, volume, limit)` → reads/writes `foreshadowings` — 
- `repo.list_genre_rules(self, novel_name)` → reads/writes `genre_rules` — Return all genre_rules for a novel. Empty list if novel has none.
- `repo.list_novels(self)` → reads/writes `novels` — 
- `repo.list_outlines(self, novel_name)` → reads/writes `outlines` — 
- `repo.list_pending_foreshadowing(self, novel_name)` → reads/writes `pending_foreshadowings` — 
- `repo.list_plot_arcs(self, novel_name, status)` → reads/writes `plot_arcs` — 
- `repo.list_project_meta(self, novel_name)` → reads/writes `project_metas` — 
- `repo.list_recent_usage(self, limit)` → reads/writes `recent_usages` — 
- `repo.list_reviews(self, novel_name)` → reads/writes `reviews` — 
- `repo.list_story_volumes(self, novel_name)` → reads/writes `story_volumes` — 
- `repo.list_style_presets(self)` → reads/writes `style_presets` — 
- `repo.list_volume_plans(self, novel_name)` → reads/writes `volume_plans` — 
- `repo.list_world_building(self, novel_name, domain)` → reads/writes `world_buildings` — 
- `repo.load_all_config(self)` → reads/writes `load_all_configs` — Load all config entries as a dict (for get_active_deepseek_config).
- `repo.log_usage(self, model, operation, prompt_tokens, completion_tokens, novel, cost)` → reads/writes `log_usages` — 
- `repo.resolve_foreshadowing(self, fid, vol, ch, note)` → reads/writes `resolve_foreshadowings` — 
- `repo.search_all(self, query, novel_name, limit)` → reads/writes `searchs` — Search across chapters, outlines, reviews. Returns dict compatible with old content_db.search_all().
- `repo.search_chapters(self, novel_name, query, limit)` → reads/writes `search_chapters` — Full-text search on chapters using LIKE fallback (FTS5 no longer used).
- `repo.search_outlines(self, novel_name, query, limit)` → reads/writes `search_outlines` — 
- `repo.search_reviews(self, novel_name, query, limit)` → reads/writes `search_reviews` — 
- `repo.set_config(self, key, value)` → reads/writes `set_configs` — 
- `repo.update_alias_registry(self, aid)` → reads/writes `alias_registrys` — 
- `repo.update_banned_word(self, bid)` → reads/writes `banned_words` — 
- `repo.update_chapter_metadata(self, novel_name, volume, chapter_num)` → reads/writes `chapter_metadatas` — Update v3 chapter metadata (pace_type, emotional_beat, etc.)
- `repo.update_character(self, cid)` → reads/writes `characters` — Update character fields. Returns True if successful.
- `repo.update_compliance_rule(self, rid)` → reads/writes `compliance_rules` — 
- `repo.update_foreshadowing(self, fid)` → reads/writes `foreshadowings` — 
- `repo.update_style_preset(self, sid)` → reads/writes `style_presets` — 
- `repo.upsert_chapter(self, novel_name, chapter_ref)` → reads/writes `chapters` — 
- `repo.upsert_daily_stats(self, model, operation, prompt_tokens, completion_tokens, cost)` → reads/writes `daily_stats` — 
- `repo.upsert_danger_issue(self, novel_name, volume, chapter_num, content)` → reads/writes `danger_issues` — 
- `repo.upsert_novel(self, novel_name)` → reads/writes `novels` — 
- `repo.upsert_outline(self, novel_name, volume, content, word_count)` → reads/writes `outlines` — 
- `repo.upsert_project_meta(self, novel_name, key, value)` → reads/writes `project_metas` — 
- `repo.upsert_review(self, novel_name, chapter_ref)` → reads/writes `reviews` — 
- `repo.upsert_volume_plan(self, novel_name, vol_num)` → reads/writes `volume_plans` — 

---

## 4. Context Building (12 layers)

See [openspec/specs/context-builder.md](../../openspec/specs/context-builder.md).
The 12 layers and their token budgets are documented there.

---

## 5. API Endpoints (83)

### 5.0 api
#### Endpoint: GET /api/novels

- **Function**: `api_list_novels` (line 457)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `list_novels`- **DB calls**: none detected- **Tables read**: `novels`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>

- **Function**: `api_novel_detail` (line 468)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/file

- **Function**: `api_read_file` (line 487)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/file -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/chapters/<path:ch_ref>

- **Function**: `api_read_chapter` (line 499)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/chapters/<path:ch_ref> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/chapters/<path:ch_ref>/edit

- **Function**: `api_edit_chapter` (line 521)
- **Description**: Save edited chapter content
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/chapters/<path:ch_ref>/edit -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: DELETE /api/novels/<novel_name>/chapters/<path:ch_ref>

- **Function**: `api_delete_chapter` (line 561)
- **Description**: Delete a chapter with state rollback. Only the latest chapter can be deleted.
- **Repository calls**: `upsert_chapter`, `list_foreshadowing`, `list_characters`, `update_foreshadowing`, `update_character`- **DB calls**: none detected- **Tables read**: `chapters`, `foreshadowings`, `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: DELETE_/api/novels/<novel_name>/chapters/<path:ch_ref> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/reviews/<ch_ref>

- **Function**: `api_read_review` (line 787)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/reviews/<ch_ref> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/status

- **Function**: `api_novel_status` (line 797)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/status -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/gate-status

- **Function**: `api_gate_status` (line 805)
- **Description**: Return stage gate progress with auto-detection.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/gate-status -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/outline/<vol_ref>

- **Function**: `api_read_outline` (line 890)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/outline/<vol_ref> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/outline/<vol_ref>/edit

- **Function**: `api_edit_outline` (line 900)
- **Description**: Save edited outline
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/outline/<vol_ref>/edit -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/chapter-outlines/<vol_ref>

- **Function**: `api_get_chapter_outlines` (line 936)
- **Description**: Return all chapter outlines for a volume.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/chapter-outlines/<vol_ref> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/novels/<novel_name>/chapter-outlines/<vol_ref>/<int:ch_num>

- **Function**: `api_put_chapter_outline` (line 947)
- **Description**: Update a single chapter outline.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT_/api/novels/<novel_name>/chapter-outlines/<vol_ref>/<int:ch_num> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/danger-issue/<vol_ref>/<ch_num>

- **Function**: `api_read_danger_issue` (line 967)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/danger-issue/<vol_ref>/<ch_num> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/export

- **Function**: `api_export_novel` (line 1317)
- **Description**: Export all chapters of a novel in the requested format.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/export -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/ai/chat

- **Function**: `api_ai_chat` (line 1370)
- **Description**: Direct AI chat
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/ai/chat -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/ai/stream

- **Function**: `api_ai_stream` (line 1388)
- **Description**: SSE streaming AI chat (supports both Anthropic and OpenAI formats)
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/ai/stream -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/create

- **Function**: `api_create_novel` (line 1528)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/create -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/generate-chapter

- **Function**: `api_generate_chapter` (line 1668)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/generate-chapter -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/review-chapter

- **Function**: `api_review_chapter` (line 1736)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/review-chapter -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/optimize-chapter

- **Function**: `api_optimize_chapter` (line 1885)
- **Description**: One-click optimize: fix issues found during review
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/optimize-chapter -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/run-script

- **Function**: `api_run_script` (line 1945)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/run-script -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/file/write

- **Function**: `api_write_novel_file` (line 1959)
- **Description**: Write/update any file in a novel's directory
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/file/write -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/update-status

- **Function**: `api_update_status` (line 1976)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/update-status -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/config

- **Function**: `api_get_config` (line 1990)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/config -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/config/save

- **Function**: `api_save_config` (line 2011)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/config/save -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/config/test

- **Function**: `api_test_config` (line 2045)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/config/test -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/styles

- **Function**: `api_styles` (line 2244)
- **Description**: Return available writing styles from DB presets + distilled JSON fingerprints.
- **Repository calls**: `list_style_presets`- **DB calls**: none detected- **Tables read**: `style_presets`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/styles -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/wizard/step

- **Function**: `api_wizard_step` (line 2286)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/wizard/step -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/config-db/<table>

- **Function**: `api_config_list` (line 2458)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/config-db/<table> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/config-db/<table>

- **Function**: `api_config_add` (line 2477)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/config-db/<table> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/config-db/<table>/<int:row_id>

- **Function**: `api_config_manage` (line 2503)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/config-db/<table>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/content/quality-report/<novel_name>

- **Function**: `api_quality_report` (line 2538)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/content/quality-report/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/workflow/preflight/<novel_name>

- **Function**: `api_workflow_preflight` (line 2625)
- **Description**: Run all pre-generation enforcement scripts. Returns pass/fail for each.
- **Repository calls**: `get`- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/workflow/preflight/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/workflow/postflight/<novel_name>

- **Function**: `api_workflow_postflight` (line 2669)
- **Description**: Run all post-generation enforcement scripts.
- **Repository calls**: `get`- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/workflow/postflight/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/enforce-pipeline

- **Function**: `api_enforce_pipeline` (line 2716)
- **Description**: Run the complete enforcement pipeline for a chapter.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/enforce-pipeline -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/context/build

- **Function**: `api_context_build` (line 2835)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/context/build -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/context/stats/<novel_name>/<int:volume>/<int:chapter>

- **Function**: `api_context_stats` (line 2858)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/context/stats/<novel_name>/<int:volume>/<int:chapter> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/rag/query

- **Function**: `api_rag_query` (line 2870)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/rag/query -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/init/full/<novel_name>

- **Function**: `api_init_full` (line 2888)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/init/full/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/world-building/init

- **Function**: `api_init_world_building` (line 2898)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/world-building/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/plot-arcs/init

- **Function**: `api_init_plot_arcs` (line 2908)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/plot-arcs/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/pacing/init

- **Function**: `api_init_pacing` (line 2918)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/pacing/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/revelation/init

- **Function**: `api_init_revelation` (line 2928)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/revelation/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/genre_rules/<novel_name>

- **Function**: `api_genre_rules_list` (line 2940)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/genre_rules/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/story_volumes/<novel_name>

- **Function**: `api_story_volumes_list` (line 2954)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/story_volumes/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/volume_plans/<novel_name>

- **Function**: `api_volume_plans_list` (line 2968)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/volume_plans/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/alias_names/<novel_name>

- **Function**: `api_alias_names_list` (line 2982)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/alias_names/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/project_meta/<novel_name>

- **Function**: `api_project_meta_list` (line 2996)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/project_meta/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/characters/<novel_name>

- **Function**: `api_characters_list` (line 3012)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/characters/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/characters/<novel_name>/<int:cid>

- **Function**: `api_character_get` (line 3021)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/characters/<novel_name>/<int:cid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>

- **Function**: `api_character_add` (line 3033)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `add_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/characters/<novel_name>/<int:cid>

- **Function**: `api_character_manage` (line 3051)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `delete_character`, `update_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/characters/<novel_name>/<int:cid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>/<int:cid>/event

- **Function**: `api_character_event` (line 3072)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `add_character_event`- **DB calls**: none detected- **Tables read**: `character_events`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name>/<int:cid>/event -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>/init

- **Function**: `api_characters_init` (line 3087)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name>/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/foreshadowing/<novel_name>

- **Function**: `api_foreshadowing_list` (line 3099)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/foreshadowing/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/foreshadowing/<novel_name>/unresolved

- **Function**: `api_foreshadowing_unresolved` (line 3110)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_unresolved_foreshadowing`- **DB calls**: none detected- **Tables read**: `unresolved_foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/foreshadowing/<novel_name>/unresolved -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/foreshadowing/<novel_name>

- **Function**: `api_foreshadowing_add` (line 3121)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `add_foreshadowing`- **DB calls**: none detected- **Tables read**: `foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/foreshadowing/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/foreshadowing/<novel_name>/<int:fid>

- **Function**: `api_foreshadowing_manage` (line 3141)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `delete_foreshadowing`, `update_foreshadowing`- **DB calls**: none detected- **Tables read**: `foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/foreshadowing/<novel_name>/<int:fid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/foreshadowing/<novel_name>/resolve/<int:fid>

- **Function**: `api_foreshadowing_resolve` (line 3158)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `resolve_foreshadowing`- **DB calls**: none detected- **Tables read**: `resolve_foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/foreshadowing/<novel_name>/resolve/<int:fid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/foreshadowing/<novel_name>/init

- **Function**: `api_foreshadowing_init` (line 3169)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/foreshadowing/<novel_name>/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/world_building/<novel_name>

- **Function**: `api_world_building_list` (line 3181)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/world_building/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/world_building/<novel_name>

- **Function**: `api_world_building_add` (line 3204)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/world_building/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/world_building/<novel_name>/<int:row_id>

- **Function**: `api_world_building_manage` (line 3231)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/world_building/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/plot_arcs/<novel_name>

- **Function**: `api_plot_arcs_list` (line 3259)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/plot_arcs/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/plot_arcs/<novel_name>

- **Function**: `api_plot_arcs_add` (line 3282)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/plot_arcs/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/plot_arcs/<novel_name>/<int:row_id>

- **Function**: `api_plot_arcs_manage` (line 3316)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/plot_arcs/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/pacing_control/<novel_name>

- **Function**: `api_pacing_control_list` (line 3347)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/pacing_control/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/pacing_control/<novel_name>

- **Function**: `api_pacing_control_add` (line 3370)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/pacing_control/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/pacing_control/<novel_name>/<int:row_id>

- **Function**: `api_pacing_control_manage` (line 3401)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/pacing_control/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/revelation_schedule/<novel_name>

- **Function**: `api_revelation_schedule_list` (line 3429)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/revelation_schedule/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/revelation_schedule/<novel_name>

- **Function**: `api_revelation_schedule_add` (line 3452)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/revelation_schedule/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/revelation_schedule/<novel_name>/<int:row_id>

- **Function**: `api_revelation_schedule_manage` (line 3482)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/revelation_schedule/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/cleanup-bak

- **Function**: `api_cleanup_bak` (line 3511)
- **Description**: Delete all .bak backup files for a novel
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/cleanup-bak -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/content/search

- **Function**: `api_content_search` (line 3531)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `search_all`- **DB calls**: none detected- **Tables read**: `searchs`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/content/search -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/content/stats/<novel_name>

- **Function**: `api_content_stats` (line 3541)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_novel_stats`- **DB calls**: none detected- **Tables read**: `novel_stats`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/content/stats/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/content/sync

- **Function**: `api_content_sync` (line 3548)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/content/sync -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/templates

- **Function**: `api_list_templates` (line 3565)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/templates -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/usage/stats

- **Function**: `api_usage_stats` (line 3580)
- **Description**: Return token usage statistics.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/usage/stats -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>/<int:cid>/ai-profile

- **Function**: `api_ai_character_profile` (line 3678)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name>/<int:cid>/ai-profile -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

### 5.80 assets
#### Endpoint: GET /assets/<path:filename>

- **Function**: `serve_react_assets` (line 437)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/assets/<path:filename> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

### 5.81 
#### Endpoint: GET /

- **Function**: `index` (line 441)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/ -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /

- **Function**: `index` (line 452)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/ -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->


---

## Appendix A: Endpoint Index

| Method | Route | Function |
|--------|-------|----------|
| `GET` | `/api/novels` | `api_list_novels` |
| `GET` | `/api/novels/<novel_name>` | `api_novel_detail` |
| `GET` | `/api/novels/<novel_name>/file` | `api_read_file` |
| `GET` | `/api/novels/<novel_name>/chapters/<path:ch_ref>` | `api_read_chapter` |
| `POST` | `/api/novels/<novel_name>/chapters/<path:ch_ref>/edit` | `api_edit_chapter` |
| `DELETE` | `/api/novels/<novel_name>/chapters/<path:ch_ref>` | `api_delete_chapter` |
| `GET` | `/api/novels/<novel_name>/reviews/<ch_ref>` | `api_read_review` |
| `GET` | `/api/novels/<novel_name>/status` | `api_novel_status` |
| `GET` | `/api/novels/<novel_name>/gate-status` | `api_gate_status` |
| `GET` | `/api/novels/<novel_name>/outline/<vol_ref>` | `api_read_outline` |
| `POST` | `/api/novels/<novel_name>/outline/<vol_ref>/edit` | `api_edit_outline` |
| `GET` | `/api/novels/<novel_name>/chapter-outlines/<vol_ref>` | `api_get_chapter_outlines` |
| `PUT` | `/api/novels/<novel_name>/chapter-outlines/<vol_ref>/<int:ch_num>` | `api_put_chapter_outline` |
| `GET` | `/api/novels/<novel_name>/danger-issue/<vol_ref>/<ch_num>` | `api_read_danger_issue` |
| `GET` | `/api/novels/<novel_name>/export` | `api_export_novel` |
| `POST` | `/api/ai/chat` | `api_ai_chat` |
| `POST` | `/api/ai/stream` | `api_ai_stream` |
| `POST` | `/api/novels/create` | `api_create_novel` |
| `POST` | `/api/novels/<novel_name>/generate-chapter` | `api_generate_chapter` |
| `POST` | `/api/novels/<novel_name>/review-chapter` | `api_review_chapter` |
| `POST` | `/api/novels/<novel_name>/optimize-chapter` | `api_optimize_chapter` |
| `POST` | `/api/novels/<novel_name>/run-script` | `api_run_script` |
| `POST` | `/api/novels/<novel_name>/file/write` | `api_write_novel_file` |
| `POST` | `/api/novels/<novel_name>/update-status` | `api_update_status` |
| `GET` | `/api/config` | `api_get_config` |
| `POST` | `/api/config/save` | `api_save_config` |
| `POST` | `/api/config/test` | `api_test_config` |
| `GET` | `/api/styles` | `api_styles` |
| `POST` | `/api/wizard/step` | `api_wizard_step` |
| `GET` | `/api/config-db/<table>` | `api_config_list` |
| `POST` | `/api/config-db/<table>` | `api_config_add` |
| `PUT` | `/api/config-db/<table>/<int:row_id>` | `api_config_manage` |
| `GET` | `/api/content/quality-report/<novel_name>` | `api_quality_report` |
| `POST` | `/api/workflow/preflight/<novel_name>` | `api_workflow_preflight` |
| `POST` | `/api/workflow/postflight/<novel_name>` | `api_workflow_postflight` |
| `POST` | `/api/novels/<novel_name>/enforce-pipeline` | `api_enforce_pipeline` |
| `POST` | `/api/context/build` | `api_context_build` |
| `GET` | `/api/context/stats/<novel_name>/<int:volume>/<int:chapter>` | `api_context_stats` |
| `POST` | `/api/rag/query` | `api_rag_query` |
| `POST` | `/api/init/full/<novel_name>` | `api_init_full` |
| `POST` | `/api/novels/<novel_name>/world-building/init` | `api_init_world_building` |
| `POST` | `/api/novels/<novel_name>/plot-arcs/init` | `api_init_plot_arcs` |
| `POST` | `/api/novels/<novel_name>/pacing/init` | `api_init_pacing` |
| `POST` | `/api/novels/<novel_name>/revelation/init` | `api_init_revelation` |
| `GET` | `/api/genre_rules/<novel_name>` | `api_genre_rules_list` |
| `GET` | `/api/story_volumes/<novel_name>` | `api_story_volumes_list` |
| `GET` | `/api/volume_plans/<novel_name>` | `api_volume_plans_list` |
| `GET` | `/api/alias_names/<novel_name>` | `api_alias_names_list` |
| `GET` | `/api/project_meta/<novel_name>` | `api_project_meta_list` |
| `GET` | `/api/characters/<novel_name>` | `api_characters_list` |
| `GET` | `/api/characters/<novel_name>/<int:cid>` | `api_character_get` |
| `POST` | `/api/characters/<novel_name>` | `api_character_add` |
| `PUT` | `/api/characters/<novel_name>/<int:cid>` | `api_character_manage` |
| `POST` | `/api/characters/<novel_name>/<int:cid>/event` | `api_character_event` |
| `POST` | `/api/characters/<novel_name>/init` | `api_characters_init` |
| `GET` | `/api/foreshadowing/<novel_name>` | `api_foreshadowing_list` |
| `GET` | `/api/foreshadowing/<novel_name>/unresolved` | `api_foreshadowing_unresolved` |
| `POST` | `/api/foreshadowing/<novel_name>` | `api_foreshadowing_add` |
| `PUT` | `/api/foreshadowing/<novel_name>/<int:fid>` | `api_foreshadowing_manage` |
| `POST` | `/api/foreshadowing/<novel_name>/resolve/<int:fid>` | `api_foreshadowing_resolve` |
| `POST` | `/api/foreshadowing/<novel_name>/init` | `api_foreshadowing_init` |
| `GET` | `/api/world_building/<novel_name>` | `api_world_building_list` |
| `POST` | `/api/world_building/<novel_name>` | `api_world_building_add` |
| `PUT` | `/api/world_building/<novel_name>/<int:row_id>` | `api_world_building_manage` |
| `GET` | `/api/plot_arcs/<novel_name>` | `api_plot_arcs_list` |
| `POST` | `/api/plot_arcs/<novel_name>` | `api_plot_arcs_add` |
| `PUT` | `/api/plot_arcs/<novel_name>/<int:row_id>` | `api_plot_arcs_manage` |
| `GET` | `/api/pacing_control/<novel_name>` | `api_pacing_control_list` |
| `POST` | `/api/pacing_control/<novel_name>` | `api_pacing_control_add` |
| `PUT` | `/api/pacing_control/<novel_name>/<int:row_id>` | `api_pacing_control_manage` |
| `GET` | `/api/revelation_schedule/<novel_name>` | `api_revelation_schedule_list` |
| `POST` | `/api/revelation_schedule/<novel_name>` | `api_revelation_schedule_add` |
| `PUT` | `/api/revelation_schedule/<novel_name>/<int:row_id>` | `api_revelation_schedule_manage` |
| `POST` | `/api/novels/<novel_name>/cleanup-bak` | `api_cleanup_bak` |
| `GET` | `/api/content/search` | `api_content_search` |
| `GET` | `/api/content/stats/<novel_name>` | `api_content_stats` |
| `POST` | `/api/content/sync` | `api_content_sync` |
| `GET` | `/api/templates` | `api_list_templates` |
| `GET` | `/api/usage/stats` | `api_usage_stats` |
| `POST` | `/api/characters/<novel_name>/<int:cid>/ai-profile` | `api_ai_character_profile` |
| `GET` | `/assets/<path:filename>` | `serve_react_assets` |
| `GET` | `/` | `index` |
| `GET` | `/` | `index` |

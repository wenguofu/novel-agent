# Novel Agent — System Functional Spec

> Machine-generated + manual supplements. Source of truth: `portal/app.py` AST.
> Auto-generated: 2026-06-06T16:59:38Z. Inventory: 88 endpoints.
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

## 2. Data Model (88 tables)

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
- `repo.list_characters_active_in_volume(self, novel_name, volume)` → reads/writes `characters_active_in_volumes` — Characters active at or before the given volume (current_vol <= volume).
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

## 5. API Endpoints (88)

### 5.0 health
#### Endpoint: GET /health

- **Function**: `health_endpoint` (line 120)
- **Description**: Aggregate health snapshot: DB, response time, circuit breaker.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/health -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

### 5.1 
#### Endpoint: GET /

- **Function**: `index` (line 552)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/ -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

### 5.2 api
#### Endpoint: GET /api/novels

- **Function**: `api_list_novels` (line 559)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `list_novels`- **DB calls**: none detected- **Tables read**: `novels`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>

- **Function**: `api_novel_detail` (line 570)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/file

- **Function**: `api_read_file` (line 589)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/file -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/chapters/<path:ch_ref>

- **Function**: `api_read_chapter` (line 601)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/chapters/<path:ch_ref> -->
Read a chapter by ref. If `ch_ref` contains a slash (e.g. `vol-01/ch-001`) it's used verbatim; otherwise the manuscript tree is scanned across all `vol-*` dirs and the first match wins. Returns `{content, path, word_count}` or 404. The auto-scan path means callers can use bare `ch-001` and let the server resolve the volume.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/chapters/<path:ch_ref>/edit

- **Function**: `api_edit_chapter` (line 623)
- **Description**: Save edited chapter content
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/chapters/<path:ch_ref>/edit -->
Save edited chapter content from the React editor. Writes `manuscript/<ch_ref>.md`, then re-syncs content.db and calls `auto_update_after_save` to refresh derived state (chapter outline, story tracking). Rejects empty content with 400. Sync failures are logged but do not fail the request — the file write is the source of truth.
<!-- /MANUAL -->

#### Endpoint: DELETE /api/novels/<novel_name>/chapters/<path:ch_ref>

- **Function**: `api_delete_chapter` (line 663)
- **Description**: Delete a chapter with state rollback. Only the latest chapter can be deleted.
- **Repository calls**: `upsert_chapter`, `list_foreshadowing`, `list_characters`, `update_foreshadowing`, `update_character`- **DB calls**: none detected- **Tables read**: `chapters`, `foreshadowings`, `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: DELETE_/api/novels/<novel_name>/chapters/<path:ch_ref> -->
Delete a chapter with state rollback. Only the *latest* chapter (highest vol + ch_num across the whole manuscript tree) can be deleted — earlier chapters are protected to keep history monotonic. Returns 400 with the actual latest ref if the caller targets a non-latest chapter. The endpoint also rolls back related state in content.db (review row, chapter_outlines flag) so the slot can be re-generated cleanly.
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/reviews/<ch_ref>

- **Function**: `api_read_review` (line 889)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/reviews/<ch_ref> -->
Read a previously-generated review markdown. Tries `reviews/<ch_ref>-review.md` first, falls back to `reviews/<ch_ref>.md` for legacy files. Returns 404 if neither exists. Pure read — used by the review tab in the UI; reviews are produced by `/review-chapter`.
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/status

- **Function**: `api_novel_status` (line 899)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/status -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/gate-status

- **Function**: `api_gate_status` (line 907)
- **Description**: Return stage gate progress with auto-detection.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/gate-status -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/outline/<vol_ref>

- **Function**: `api_read_outline` (line 992)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/outline/<vol_ref> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/outline/<vol_ref>/edit

- **Function**: `api_edit_outline` (line 1002)
- **Description**: Save edited outline
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/outline/<vol_ref>/edit -->
Save edited volume outline. The body's `content` is written to `outline/<vol_ref>-chapters.yaml` (note: stored as YAML, not MD), then parsed and upserted into the `chapter_outlines` table one row per chapter. Each row carries title/function/core_events/foreshadowing/ending_hook/is_danger_scene/word_count. Sync failures are logged but do not fail the write — the YAML file remains the source of truth.
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/chapter-outlines/<vol_ref>

- **Function**: `api_get_chapter_outlines` (line 1038)
- **Description**: Return all chapter outlines for a volume.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/chapter-outlines/<vol_ref> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/novels/<novel_name>/chapter-outlines/<vol_ref>/<int:ch_num>

- **Function**: `api_put_chapter_outline` (line 1049)
- **Description**: Update a single chapter outline.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT_/api/novels/<novel_name>/chapter-outlines/<vol_ref>/<int:ch_num> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/danger-issue/<vol_ref>/<ch_num>

- **Function**: `api_read_danger_issue` (line 1069)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/danger-issue/<vol_ref>/<ch_num> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/export

- **Function**: `api_export_novel` (line 1419)
- **Description**: Export all chapters of a novel in the requested format.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/export -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/ai/chat

- **Function**: `api_ai_chat` (line 1472)
- **Description**: Direct AI chat
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/ai/chat -->
Non-streaming direct AI call — sends `messages` + `system` to the configured DeepSeek model and returns the full response in one shot. Used by internal callers that don't need streaming (most preflight/postflight chains call `deepseek_chat` directly; this endpoint is mainly for ad-hoc UI debugging). Token usage is logged via the shared `deepseek_chat` helper.
<!-- /MANUAL -->

#### Endpoint: POST /api/ai/stream

- **Function**: `api_ai_stream` (line 1490)
- **Description**: SSE streaming AI chat (supports both Anthropic and OpenAI formats)
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/ai/stream -->
SSE streaming wrapper around the active DeepSeek/Anthropic chat model. Accepts either OpenAI-style `messages` or a `{system, user}` pair (used by `useSSEStream` in the React UI for live token streaming). Auto-detects Anthropic vs OpenAI endpoint shape from the configured api_base, normalizes both into `{type: token|done|error}` SSE events, and logs token usage to the DB on completion.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/create

- **Function**: `api_create_novel` (line 1630)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/create -->
Create a new novel from a high-level prompt. Body collects `name`, `genre`, `protagonist`, `selling_point`, `word_goal`, `perspective`, `references` and asks DeepSeek to emit five base files (`project.md`, `genre_bible.md`, `world_bible.md`, `characters.md`, `alias_registry.md`) in a single `## FILE: ...` blocked response. The endpoint parses the blocks, writes each file under `novels/<name>/`, scaffolds the standard subdirs (manuscript, outline, reviews, state, volume_plan), and seeds `volume_plan.md` + `state/current_status.md` if the AI didn't. Returns 400 if `name` is missing or already exists.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/generate-chapter

- **Function**: `api_generate_chapter` (line 1770)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/generate-chapter -->
Primary chapter-writing endpoint. Builds the layered prompt via `context_builder`, calls DeepSeek non-streaming, writes the result to `manuscript/<volume>/ch-<NNN>.md`, and re-syncs the content DB. Required body fields: `chapter_num` (string or int); optional: `volume` (default `vol-01`), `style`, `instructions`, `temperature`, `max_tokens`. If the chapter file already exists, a 'continue/rewrite consistently' hint is appended to the system prompt — caller is responsible for backing up first if they want to keep the old draft.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/review-chapter

- **Function**: `api_review_chapter` (line 2148)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/review-chapter -->
AI editor pass over an existing chapter. Runs three scripts in parallel (`analyze_chapter`, `check_compliance`, `detect_forbidden_patterns`), then asks DeepSeek for a structured YAML review covering function/character/setting/pacing/danger/hook. Persists the review to `reviews/<ch_id>-review.md`, upserts the `reviews` table in content.db, and returns both the AI verdict and per-script pass/fail flags. Body requires `chapter_ref` (or `volume`+`chapter_num`); the ref is auto-normalized from `vol-01-ch-001` to `vol-01/ch-001`.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/optimize-chapter

- **Function**: `api_optimize_chapter` (line 2194)
- **Description**: One-click optimize: fix issues found during review
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/optimize-chapter -->
One-click chapter rewrite that consumes a prior review. Body needs `chapter_ref`, `review_text`, and `script_issues`; the endpoint prompts DeepSeek to fix the flagged problems without changing plot/scope. Before overwriting, the current chapter is copied to `manuscript/.bak/<ref>.revN.md` (last 5 revisions retained). Returns the new content but does NOT auto-save it — the UI calls `/chapters/<ref>/edit` to persist.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/run-script

- **Function**: `api_run_script` (line 2409)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/run-script -->
Run an arbitrary enforcement script (one of the allow-listed names in `agent-system/scripts/`) against a file inside the novel's directory. Body needs `script` (filename) and `filepath` (relative to the novel root). Returns the raw `{success, stdout, stderr, returncode}` from `run_script`. Used by the UI's per-chapter script panel and by ad-hoc diagnostics; the workflow endpoints below call the same scripts in fixed sequences.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/file/write

- **Function**: `api_write_novel_file` (line 2423)
- **Description**: Write/update any file in a novel's directory
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/file/write -->
Generic file-write inside a novel's directory. Body needs `path` (relative, no `..`) and non-empty `content`. The path is split on `/` and passed to `write_novel_file`, which creates parent dirs as needed. Used by the React UI to save any auxiliary file (characters, world_bible, alias_registry, etc.) without a dedicated endpoint per file type.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/update-status

- **Function**: `api_update_status` (line 2440)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/update-status -->
Overwrite `state/current_status.md` with the supplied `content`. No validation beyond a non-empty check; the UI's status editor is the primary caller. This is the manual counterpart to the post-chapter auto-update that runs after `/edit`; use it when the writer wants to record narrative state directly.
<!-- /MANUAL -->

#### Endpoint: GET /api/config

- **Function**: `api_get_config` (line 2454)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/config -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/config/save

- **Function**: `api_save_config` (line 2475)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/config/save -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/config/test

- **Function**: `api_test_config` (line 2509)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/config/test -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/styles

- **Function**: `api_styles` (line 2708)
- **Description**: Return available writing styles from DB presets + distilled JSON fingerprints.
- **Repository calls**: `list_style_presets`- **DB calls**: none detected- **Tables read**: `style_presets`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/styles -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/wizard/step

- **Function**: `api_wizard_step` (line 2752)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/wizard/step -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/config-db/<table>

- **Function**: `api_config_list` (line 2924)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/config-db/<table> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/config-db/<table>

- **Function**: `api_config_add` (line 2943)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/config-db/<table> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/config-db/<table>/<int:row_id>

- **Function**: `api_config_manage` (line 2969)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/config-db/<table>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/content/quality-report/<novel_name>

- **Function**: `api_quality_report` (line 3004)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/content/quality-report/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/dashboard/stats

- **Function**: `api_dashboard_stats` (line 3094)
- **Description**: Aggregate dashboard metrics across all novels.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/dashboard/stats -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/workflow/preflight/<novel_name>

- **Function**: `api_workflow_preflight` (line 3178)
- **Description**: Run all pre-generation enforcement scripts. Returns pass/fail for each.
- **Repository calls**: `get`- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/workflow/preflight/<novel_name> -->
Pre-generation gate. Runs five checks in sequence — stage_gate, outline existence, danger_issue presence, characters.md presence, RAG index status — and returns a `{name, ok, detail}` block for each. Body takes `volume` (default `vol-01`); the danger_issue check is informational and does not block when missing. `all_ok` reflects whether the chapter is safe to generate. Called by the UI's writing page before enabling the 'Generate' button.
<!-- /MANUAL -->

#### Endpoint: POST /api/workflow/postflight/<novel_name>

- **Function**: `api_workflow_postflight` (line 3223)
- **Description**: Run all post-generation enforcement scripts.
- **Repository calls**: `get`- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/workflow/postflight/<novel_name> -->
Post-generation gate. Runs five checks — review validation, continuity, rhythm, RAG re-index, stage-gate complete — for the just-written chapter (passed via `chapter_ref`). Unlike preflight, every check must pass for `all_ok=true`; the review-validation step depends on `/review-chapter` having already produced the review file. Side effect: re-indexes the RAG store, so this is *not* a read-only probe.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/enforce-pipeline

- **Function**: `api_enforce_pipeline` (line 3270)
- **Description**: Run the complete enforcement pipeline for a chapter.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/enforce-pipeline -->
Full Steps 0-10 enforcement chain — the scripted version of `workflow-new-chapter.md`. Runs stage_gate, RAG check, analyze/forbidden/compliance, review validation, continuity, rhythm, and stage-complete in one shot. Body: `volume`, `chapter_num`, optional `chapter_ref` (auto-derived from vol+num if absent). Returns a `pipeline` dict keyed by step number with `{name, ok, output}` per gate. Heavier than preflight+postflight combined; use for end-of-chapter validation runs.
<!-- /MANUAL -->

#### Endpoint: POST /api/context/build

- **Function**: `api_context_build` (line 3389)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/context/build -->
Builds the multi-layer system prompt for chapter writing via `context_builder.build_context`. Returns the assembled prompt plus per-layer token usage so the UI can show a context-health indicator. Read-only — no side effects. Called by both the React writing page and the `generate-chapter` workflow (in which case the prompt is consumed internally rather than returned). Token budget default 10000, configurable via the `max_tokens` request field.
<!-- /MANUAL -->

#### Endpoint: GET /api/context/stats/<novel_name>/<int:volume>/<int:chapter>

- **Function**: `api_context_stats` (line 3412)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/context/stats/<novel_name>/<int:volume>/<int:chapter> -->
Read-only diagnostic — returns per-layer token counts and source-file metadata for the context that *would* be built for the given chapter, without actually assembling the prompt. Used by the writing UI's pre-generation panel to show users what will be injected. Cheaper than `/api/context/build` because it skips the final concatenation.
<!-- /MANUAL -->

#### Endpoint: POST /api/rag/query

- **Function**: `api_rag_query` (line 3424)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/rag/query -->
Multi-category RAG retrieval over the novel's vector index. Body must include `novel` and `queries` (list of category-keyed query specs); optional `total_max_tokens` (default 10000) caps the combined retrieved context. Delegates to `rag_engine.query_categories`. Returns 400 if either required field is missing. Used internally by `context_builder` and exposed for UI inspection.
<!-- /MANUAL -->

#### Endpoint: POST /api/init/full/<novel_name>

- **Function**: `api_init_full` (line 3442)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/init/full/<novel_name> -->
One-shot domain-DB initializer — calls `content_db.init_all_from_files` to parse `world_bible.md`, plot arcs, pacing, and revelation markers from the novel's source files into the relational tables (world_building, plot_arcs, pacing, revelation). Idempotent: re-running re-syncs. Returns the raw dict from `init_all_from_files` including per-domain counts. Used after `/api/novels/create` or after manual edits to the source files.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/world-building/init

- **Function**: `api_init_world_building` (line 3452)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/world-building/init -->
Parses `world_bible.md` and upserts entries into the `world_building` table via `content_db.init_world_building_from_file`. Returns `{success, message, created}` where `created` is the row count touched. One of four domain-scoped variants of `/api/init/full` — use this when the writer only edited the world bible and doesn't need a full re-sync.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/plot-arcs/init

- **Function**: `api_init_plot_arcs` (line 3462)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/plot-arcs/init -->
Parses the plot-arcs source file and upserts into the `plot_arcs` table via `content_db.init_plot_arcs_from_file`. Same shape as the world-building variant: `{success, message, created}`. Trigger this after editing the long-line arc markdown so the writing context picks up the new arcs.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/pacing/init

- **Function**: `api_init_pacing` (line 3472)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/pacing/init -->
Re-derives pacing markers from the volume outlines (`outline/vol-NN-chapters.yaml`) into the `pacing` table via `content_db.init_pacing_from_outline`. Pacing rows feed the rhythm-check script and the context-builder's pacing layer. Idempotent; safe to call after every outline edit.
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/revelation/init

- **Function**: `api_init_revelation` (line 3482)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/revelation/init -->
Re-derives revelation/foreshadowing markers from the volume outlines into the `revelation` table via `content_db.init_revelation_from_outline`. Powers the foreshadowing-tracking layer of the writing context. Returns `{success, message, created}` with the row count.
<!-- /MANUAL -->

#### Endpoint: GET /api/genre_rules/<novel_name>

- **Function**: `api_genre_rules_list` (line 3494)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/genre_rules/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/story_volumes/<novel_name>

- **Function**: `api_story_volumes_list` (line 3508)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/story_volumes/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/volume_plans/<novel_name>

- **Function**: `api_volume_plans_list` (line 3522)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/volume_plans/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/alias_names/<novel_name>

- **Function**: `api_alias_names_list` (line 3536)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/alias_names/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/project_meta/<novel_name>

- **Function**: `api_project_meta_list` (line 3550)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/project_meta/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/characters/<novel_name>

- **Function**: `api_characters_list` (line 3566)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/characters/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/characters/<novel_name>/<int:cid>

- **Function**: `api_character_get` (line 3575)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/characters/<novel_name>/<int:cid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>

- **Function**: `api_character_add` (line 3587)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `add_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/characters/<novel_name>/<int:cid>

- **Function**: `api_character_manage` (line 3605)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `delete_character`, `update_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/characters/<novel_name>/<int:cid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>/<int:cid>/event

- **Function**: `api_character_event` (line 3626)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `add_character_event`- **DB calls**: none detected- **Tables read**: `character_events`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name>/<int:cid>/event -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>/init

- **Function**: `api_characters_init` (line 3641)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name>/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/foreshadowing/<novel_name>

- **Function**: `api_foreshadowing_list` (line 3653)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/foreshadowing/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/foreshadowing/<novel_name>/unresolved

- **Function**: `api_foreshadowing_unresolved` (line 3664)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_unresolved_foreshadowing`- **DB calls**: none detected- **Tables read**: `unresolved_foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/foreshadowing/<novel_name>/unresolved -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/foreshadowing/<novel_name>

- **Function**: `api_foreshadowing_add` (line 3675)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `add_foreshadowing`- **DB calls**: none detected- **Tables read**: `foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/foreshadowing/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/foreshadowing/<novel_name>/<int:fid>

- **Function**: `api_foreshadowing_manage` (line 3695)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `delete_foreshadowing`, `update_foreshadowing`- **DB calls**: none detected- **Tables read**: `foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/foreshadowing/<novel_name>/<int:fid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/foreshadowing/<novel_name>/resolve/<int:fid>

- **Function**: `api_foreshadowing_resolve` (line 3712)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `resolve_foreshadowing`- **DB calls**: none detected- **Tables read**: `resolve_foreshadowings`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/foreshadowing/<novel_name>/resolve/<int:fid> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/foreshadowing/<novel_name>/init

- **Function**: `api_foreshadowing_init` (line 3723)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/foreshadowing/<novel_name>/init -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/world_building/<novel_name>

- **Function**: `api_world_building_list` (line 3735)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/world_building/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/world_building/<novel_name>

- **Function**: `api_world_building_add` (line 3758)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/world_building/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/world_building/<novel_name>/<int:row_id>

- **Function**: `api_world_building_manage` (line 3785)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/world_building/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/plot_arcs/<novel_name>

- **Function**: `api_plot_arcs_list` (line 3813)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/plot_arcs/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/plot_arcs/<novel_name>

- **Function**: `api_plot_arcs_add` (line 3836)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/plot_arcs/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/plot_arcs/<novel_name>/<int:row_id>

- **Function**: `api_plot_arcs_manage` (line 3870)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/plot_arcs/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/pacing_control/<novel_name>

- **Function**: `api_pacing_control_list` (line 3901)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/pacing_control/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/pacing_control/<novel_name>

- **Function**: `api_pacing_control_add` (line 3924)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/pacing_control/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/pacing_control/<novel_name>/<int:row_id>

- **Function**: `api_pacing_control_manage` (line 3955)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/pacing_control/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/revelation_schedule/<novel_name>

- **Function**: `api_revelation_schedule_list` (line 3983)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/revelation_schedule/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/revelation_schedule/<novel_name>

- **Function**: `api_revelation_schedule_add` (line 4006)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/revelation_schedule/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: PUT /api/revelation_schedule/<novel_name>/<int:row_id>

- **Function**: `api_revelation_schedule_manage` (line 4036)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: PUT,DELETE_/api/revelation_schedule/<novel_name>/<int:row_id> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/cleanup-bak

- **Function**: `api_cleanup_bak` (line 4065)
- **Description**: Delete all .bak backup files for a novel
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/cleanup-bak -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/chapters/<path:ch_ref>/bak

- **Function**: `api_list_chapter_bak` (line 4145)
- **Description**: List .bak files for one chapter (newest first).
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/chapters/<path:ch_ref>/bak -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename>

- **Function**: `api_get_chapter_bak` (line 4178)
- **Description**: Return the content of a single .bak file.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename>/restore

- **Function**: `api_restore_chapter_bak` (line 4205)
- **Description**: Restore a .bak version as the current chapter.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename>/restore -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: DELETE /api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename>

- **Function**: `api_delete_chapter_bak` (line 4248)
- **Description**: Delete a single .bak file.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: DELETE_/api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/content/search

- **Function**: `api_content_search` (line 4275)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `search_all`- **DB calls**: none detected- **Tables read**: `searchs`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/content/search -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/content/stats/<novel_name>

- **Function**: `api_content_stats` (line 4285)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_novel_stats`- **DB calls**: none detected- **Tables read**: `novel_stats`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/content/stats/<novel_name> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/content/sync

- **Function**: `api_content_sync` (line 4292)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/content/sync -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/templates

- **Function**: `api_list_templates` (line 4309)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/templates -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: GET /api/usage/stats

- **Function**: `api_usage_stats` (line 4324)
- **Description**: Return token usage statistics.
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/api/usage/stats -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

#### Endpoint: POST /api/characters/<novel_name>/<int:cid>/ai-profile

- **Function**: `api_ai_character_profile` (line 4422)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: `get_character`- **DB calls**: none detected- **Tables read**: `characters`- **Side effects**: read-only (per AST scan)
<!-- MANUAL: POST_/api/characters/<novel_name>/<int:cid>/ai-profile -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->

### 5.87 assets
#### Endpoint: GET /assets/<path:filename>

- **Function**: `serve_react_assets` (line 537)
- **Description**: _No docstring yet — add one in `portal/app.py`._
- **Repository calls**: none detected- **DB calls**: none detected- **Tables read**: _inferred from repo calls (none detected)_- **Side effects**: read-only (per AST scan)
<!-- MANUAL: GET_/assets/<path:filename> -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->


---

## Appendix A: Endpoint Index

| Method | Route | Function |
|--------|-------|----------|
| `GET` | `/health` | `health_endpoint` |
| `GET` | `/` | `index` |
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
| `GET` | `/api/dashboard/stats` | `api_dashboard_stats` |
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
| `GET` | `/api/novels/<novel_name>/chapters/<path:ch_ref>/bak` | `api_list_chapter_bak` |
| `GET` | `/api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename>` | `api_get_chapter_bak` |
| `POST` | `/api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename>/restore` | `api_restore_chapter_bak` |
| `DELETE` | `/api/novels/<novel_name>/chapters/<path:ch_ref>/bak/<path:filename>` | `api_delete_chapter_bak` |
| `GET` | `/api/content/search` | `api_content_search` |
| `GET` | `/api/content/stats/<novel_name>` | `api_content_stats` |
| `POST` | `/api/content/sync` | `api_content_sync` |
| `GET` | `/api/templates` | `api_list_templates` |
| `GET` | `/api/usage/stats` | `api_usage_stats` |
| `POST` | `/api/characters/<novel_name>/<int:cid>/ai-profile` | `api_ai_character_profile` |
| `GET` | `/assets/<path:filename>` | `serve_react_assets` |

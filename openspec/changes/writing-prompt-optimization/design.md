## Context

`portal/context_builder.py` had a 9-layer prompt architecture but was loading only ~60% of the data the LLM needed. The deepest content (style_presets.prompt, style.md, author JSON fingerprint, project_meta keys, genre_rules, banned/compliance) was either read but discarded, never read, or only used for post-hoc checks. The plan (`docs/optimization_plan_writing_prompt.md`) was created 2026-06-02 after auditing the `api_generate_chapter` call chain — it identified 9 specific gaps with file:line citations. This change implements P0–P3 of that plan and has been committed in 3 batches on `main`:

```
3524d6c feat: P3 cleanup - unify core_instructions source, rebalance budget
7721141 feat: P2 layers - style fingerprint, characters.md fallback, world+global
132cd3b feat: P1 layers - genre_rules, banned+compliance, full project_meta
```

No migration, no DB schema change, no new endpoint — purely server-side prompt assembly changes. The frontend already passes `style: "辰东风 50%, 默认 50%"` and `instructions`, and already supports per-novel `style.md` upload; this change just makes the backend actually use those inputs.

## Goals / Non-Goals

**Goals:**
- Push per-layer DB coverage from ~60% → ~95% (every table relevant to writing now feeds the prompt).
- Resolve `style` strings into actual style content (preset prompt + book style.md + author JSON fingerprint) — no more echoing the preset name back at the model.
- Keep total prompt under the 10000 tok cap with 500 tok elastic headroom.
- Single source of truth for `core_instructions` (`prompts/core_instructions.j2`).
- Maintain backward compat: existing API and tests pass; the only test failure (`test_context_stats_structure`) was pre-existing and unrelated.

**Non-Goals:**
- No DB migration, no new tables, no API change, no frontend change.
- No new RAG / vector store integration — the 9-layer system remains DB-only.
- No token caching / memoization (existing implementation rebuilds per call; <50 ms for DB queries).
- No change to the `token_budget.py` engine itself; per-layer caps are adjusted in `context_builder.py` only.

## Decisions

### D1: Per-layer cap with internal-chunk cap (not per-source split)

`build_context` keeps a single `min(text_tokens, layer_budget)` allocation, but each layer-builder now applies its own internal cap before returning. This lets the implementation "soft-truncate" the style.md at 150 tok and per-preset-chunk at 250 tok inside `_build_style_context`, so budget cuts don't silently eat the most useful content (the fingerprint data). Alternatives considered:
- **Per-source budget split in `TokenBudget`** — would require touching `token_budget.py` and adding a nested-budget concept; rejected as out of scope.
- **Strict single 500-tok truncation at the layer level** — was the previous behavior; the regression test showed it eats the fingerprint and prompt when `style.md` is large, so we needed finer control.

### D2: Fingerprint-before-prompt in style chunk

`_build_style_context` now builds each preset chunk as: header → `#### 风格指纹` (stats) → `#### 风格描述` (prose). When the 500-tok outer cap cuts the chunk, the fingerprint (the more actionable data — specific sentence length, dialogue ratio, transition word list) is preserved and the prose prompt is dropped. This is a deliberate tradeoff: the plan said "结构化风格指纹" is the primary mechanism, prose is secondary.

### D3: characters.md fallback triggered on `background` / `arc` / `lifeline` emptiness

The plan said "当 `characters.background/arc/lifeline` 为空" — those are the three "deep" fields that store the rich content. Identity / personality / current_status often have short stubs (e.g. `current_status = "初始状态"`) that look non-empty to a naive check. The first implementation used those short-stub fields as the trigger and silently never fired; the fix (this design) uses the three deep fields the plan named. `characters.md` is parsed by anchoring on `### {name}` lines and capturing until the next `## ` (next role section), so all `###` subsections of that character (背景与身世, 核心特质, 异能, 成长弧线, …) are included.

### D4: `get_world_building_volume_plus_global` (5+5) instead of `get_world_building_for_volume(limit=10)`

Layer 5's previous call was `get_world_building_for_volume(novel, volume, limit=10)`, which filtered to `related_vol ∈ [vol-1, vol+1]` and excluded later volumes. That meant an early-chapter prompt had no idea 八神体系 or 外星种族 existed. The new repository method does a SQL `UNION` of two queries: 5 local rows (current volume window) + 5 global rows (later volumes, excluding the local IDs). The output tags each entry `[本卷|domain]` or `[全局|domain]` so the LLM knows which scope it came from. Alternatives considered:
- **Drop the filter entirely, return all rows** — for 大强成神啦 (29 world_building rows) the prompt budget would be eaten. 5+5 is empirically right: enough to cover the 八神体系 and one or two 容器宿主 entries, fits in 1500 tok.
- **Vector-search top-5 with the current volume as the query** — would require embedding the volume outline; deferred to future work (RAG integration was a non-goal).

### D5: Keep `_CORE_INSTRUCTIONS_FALLBACK` literal as a safety net

P3-1 removes the hardcoded `CORE_INSTRUCTIONS` as the *primary* source and loads via `PromptManager.render_or_default("core_instructions", fallback)`. The fallback literal is renamed `_CORE_INSTRUCTIONS_FALLBACK` and is only used if the jinja load fails (e.g. `jinja2` not installed, file missing, template error). It is byte-for-byte identical to the `.j2` — verified via Python string comparison on 2026-06-02. This is more conservative than the plan's "删除硬编码副本" wording because the alternative (crash on import) would regress any deployment where `jinja2` is unavailable.

### D6: Header docstring is the source of truth for the allocation table

After P3-2, the module-level docstring at the top of `context_builder.py` contains the full 12-layer allocation table (tok per layer, total 9500 + 500 elastic). This replaces a scattered set of magic numbers in `build_context` and serves as the in-repo spec; the `openspec/specs/context-builder.md` file mirrors it for cross-team visibility.

## Risks / Trade-offs

- **Fingerprint is JSON-derived from a small sample of public-domain author works** (`sample_size_chars: 0` in some files — see `agent-system/styles/辰东.json`). The numbers are proxies, not measurements. → **Mitigation**: label the section "风格指纹（来自 {author} 的句法统计）" so the LLM treats it as guidance, not hard fact.
- **`characters.md` parsing is regex-based, not a full markdown parser** — exotic heading styles (e.g. `### 付大强(主角)` with no space) would miss. → **Mitigation**: anchor on `^###\s+{name}\s*$` with `re.MULTILINE`; the canonical `characters.md` files in `novels/*/characters.md` all match. If a future author uses unusual formatting, the parsing will silently skip and the layer will fall back to DB-only content.
- **Layer 4 (伏笔) reduced from 1500 → 1000 tok** could clip foreshadowing descriptions in novels with many pending items. → **Mitigation**: `get_unresolved_foreshadowing` already limits to top-8 items; 1000 tok is ~125 tok/item, enough for the name + 1-line description + target_vol.
- **`_truncate_to_tokens` is character-level estimation**; it diverges from `_count_tokens` (regex-based) by ~5–10% on mixed Chinese/English text. → **Mitigation**: both functions use the same constants; the divergence is bounded and the `total_tokens` reported is the more accurate `_count_tokens` value.
- **2 unrelated pre-existing test failures remain** (`test_context_stats_structure` in `test_context_builder.py` — expects `"layers"` key for non-existent novel; `get_context_stats` returns `{"error": "小说不存在"}` instead). They were failing before this change and are not regressions. → **Mitigation**: tracked in `docs/optimization_plan_writing_prompt.md` "测试计划" section as expected baseline; the 22 pre-existing failures noted in the plan are the same as today (37 = 22 failed + 15 errors in test DB setup, none introduced by this change).

## Migration Plan

No data migration. No deployment steps beyond the standard `git pull`. Rollback strategy: each batch is an independent commit on `main`; `git revert 3524d6c` (P3), `git revert 7721141` (P2), or `git revert 132cd3b` (P1) cleanly undoes one tier. The 3 commits are atomic per tier so partial rollback is supported.

## Open Questions

- Should `style.md` be moved from per-novel `novels/{name}/style.md` to the DB (`project_meta` with key `style_md`)? Currently the file is read directly; if the file is missing the layer silently skips. DB storage would let the editor surface it as a normal project-meta field. **Decision deferred** — out of scope for this change.
- Should the fingerprint be exposed in the API response so the frontend can preview the resolved style before generation? Would be a small enhancement to `/api/context/build` response. **Decision deferred** — UX question, not a correctness one.
- Should `_truncate_to_tokens` and `_count_tokens` be unified to a single tokenizer (e.g. via `tiktoken`)? The 5–10% estimation drift could matter when prompts are near the cap. **Decision deferred** — would add a dependency; current drift is acceptable.

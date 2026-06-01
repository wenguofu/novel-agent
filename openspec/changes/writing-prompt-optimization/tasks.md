## 1. P1 — Add 2 new layers + load project_meta (must-have, batch 1)

- [x] 1.1 Implement `_build_genre_rules_context(novel_name)` reading `repo.list_genre_rules()` and grouping by `rule_category`. Required rules marked 🔴, optional 🟡. Insert as Layer 2.5 with 500-tok budget.
- [x] 1.2 Implement `_build_banned_compliance_context()` reading `repo.list_compliance_rules()` and `repo.list_banned_words()`. Group banned by `category` with `→` arrow for replacements. Insert as Layer 8.5 with 200-tok budget.
- [x] 1.3 Update `_build_project_meta` to also call `repo.list_project_meta()` and inject all 14 keys under `## 核心设定（来自 project_meta — 必须严格遵守）`. Raise Layer 1 budget from 300 → 500 tok.
- [x] 1.4 Commit batch 1 as `feat: P1 layers - genre_rules, banned+compliance, full project_meta`. Run `pytest tests/test_context_builder.py -q` and verify the 1 pre-existing failure is unchanged.

## 2. P2 — Augment style + characters + world layers (batch 2)

- [x] 2.1 Implement `_load_style_fingerprint(author_name)` reading `agent-system/styles/{name}.json` (strip trailing `风`). Extract sentence_length_mean, dialogue_ratio, vocabulary_richness, transition_density, top 5 transitions, top 3 openers, style_notes. Add `import json` to module top (was missing — caused silent except → empty fingerprint).
- [x] 2.2 Update `_build_style_context` to inject fingerprint BEFORE prose prompt in each chunk. Cap each chunk at 250 tok internally. Cap `style.md` at 150 tok internally (was 600). Reorder chunk to: header → `#### 风格指纹` → `#### 风格描述`.
- [x] 2.3 Implement `_load_character_from_md(novel_name, name)` parsing `novels/{name}/characters.md` for `### {name}` heading, capturing content until next `## `. Update `_build_character_context` to fall back to this when DB `background` AND `arc` AND `lifeline` are all empty. Cap fallback at 400 tok per character.
- [x] 2.4 Add `repo.get_world_building_volume_plus_global(novel, volume, local_limit, global_limit)` returning 5 local + 5 global rows. Update `_build_world_context` to use it; tag entries `[本卷|domain]` / `[全局|domain]`.
- [x] 2.5 Commit batch 2 as `feat: P2 layers - style fingerprint, characters.md fallback, world+global`. Verify all 10 plan items via the inspection script in `docs/optimization_plan_writing_prompt.md`.

## 3. P3 — Cleanup: unify core_instructions + rebalance budget (batch 3)

- [x] 3.1 Replace `CORE_INSTRUCTIONS` constant with `_get_core_instructions()` that loads `prompts/core_instructions.j2` via `PromptManager.render_or_default("core_instructions", _CORE_INSTRUCTIONS_FALLBACK)`. Keep the literal renamed to `_CORE_INSTRUCTIONS_FALLBACK` for graceful degradation.
- [x] 3.2 Update `build_context` Layer 0 to call `_get_core_instructions()` instead of the constant.
- [x] 3.3 Lower Layer 4 (伏笔) budget from 1500 → 1000 tok per the new allocation table. Update module-level docstring with the full 12-layer / 9500-tok table.
- [x] 3.4 Commit batch 3 as `feat: P3 cleanup - unify core_instructions source, rebalance budget`. Run `pytest tests/test_context_builder.py -q` and confirm only the pre-existing `test_context_stats_structure` failure.

## 4. OpenSpec documentation

- [x] 4.1 Create change `openspec/changes/writing-prompt-optimization/` via `openspec new change "writing-prompt-optimization"`.
- [x] 4.2 Write `proposal.md` covering Why / What Changes / 4 new capabilities / 1 modified capability / Impact.
- [x] 4.3 Write `design.md` with Context / 6 Decisions (D1 internal-chunk cap, D2 fingerprint-before-prompt, D3 deep-field trigger, D4 5+5 world, D5 fallback safety net, D6 header docstring as source of truth) / 5 Risks / Migration / 3 Open Questions.
- [x] 4.4 Write 4 ADDED spec files (`author-style-fingerprints`, `compliance-and-banned-injection`, `characters-md-fallback`, `cross-volume-world-context`) and 1 MODIFIED spec file (`context-builder`) with full requirement blocks per the schema template.
- [x] 4.5 Write `tasks.md` with 3 commit-grouped sections (P1/P2/P3) and a 4th OpenSpec section. All checkboxes marked `[x]` because the work is already complete.
- [x] 4.6 Update `openspec/specs/context-builder.md` to mirror the new 12-layer architecture (was: 9-layer with hardcoded CORE_INSTRUCTIONS).
- [x] 4.7 Update `openspec/README.md` to list the new spec status.

## 5. README + verification

- [ ] 5.1 Update root `README.md` to document the 12-layer architecture and the optimization pass.
- [ ] 5.2 Run `pytest tests/test_context_builder.py -q` for regression check.
- [ ] 5.3 Run `pytest tests/ -q` for full functional verification. Confirm the 22 failed + 15 errors baseline is unchanged (no new failures).
- [ ] 5.4 Run the plan's manual prompt inspection script against 大强成神啦 vol-01 ch-001 and verify all 10 plan items show ✓.

## 6. Optional: archive the change

- [ ] 6.1 (After steps 1-5 are verified) Run `opsx:archive` to move the change into `openspec/changes/archive/2026-06-02-writing-prompt-optimization/` with the 3 spec deltas merged into the corresponding base specs. **Defer until all 5 sections above are signed off.**

## Why

`context_builder.build_context` was assembling 9 layers but loading only a fraction of the data the LLM actually needs. The "style" layer (Layer 9) was just echoing the preset name back at the model — none of the `style_presets.prompt` content, the book-specific `style.md`, or the statistical `agent-system/styles/*.json` fingerprint was reaching the prompt. `project_meta` (the 14 core-setting keys — 八位古神, 叛神系统, 乐园, …) was unread. `genre_rules`, `banned_words`, and `compliance_rules` were checked post-hoc, never told to the LLM. Characters had stubs in the DB and no fallback to `characters.md`. World building was filtered to one volume and lost cross-volume lore like the 八神体系 that the model needs to foreshadow properly. As a result the LLM was writing chapters with a small, lossy slice of the project state — explaining why style was generic, characters under-detailed, and the world felt thin.

## What Changes

- **Add 2 new layers** (Layer 2.5 genre rules, Layer 8.5 banned + compliance) and **load 2 new resources** (full project_meta, style JSON fingerprint) — push per-layer DB coverage from ~60% to ~95%.
- **Add `characters.md` fallback** for Layer 3 when the DB row's deep fields (`background` / `arc` / `lifeline`) are empty, so the LLM gets rich 背景与身世 / 核心特质 / 成长弧线 content rather than identity stubs.
- **Drop the single-volume filter on Layer 5** — return 5 local + 5 later-volume world-building entries (tagged `[本卷|…]` / `[全局|…]`) so cross-volume lore isn't dropped in early chapters.
- **Resolve preset names to actual content** — Layer 9 parses "辰东风 50%, 默认 50%" into the `style_presets.prompt` body plus the `agent-system/styles/{author}.json` fingerprint (句长 / 对话比 / 转折词 / 句首 / 风格摘要), then reorders so the fingerprint comes first in the chunk (budget cuts preserve the most actionable data).
- **Unify `core_instructions` source** — remove the hardcoded Python string; load from `prompts/core_instructions.j2` via `PromptManager.render_or_default` with the literal kept only as a safety-net fallback.
- **Rebalance token budget** to the new 12-layer allocation table (total 9500 tok, 500 elastic): Layer 1 300→500, add Layer 2.5 500, Layer 4 1500→1000, add Layer 8.5 200.

## Capabilities

### New Capabilities

- `author-style-fingerprints`: Load statistical fingerprint JSON (`agent-system/styles/{author}.json` — sentence length, dialogue ratio, vocabulary richness, top 5 transitions, top 3 openers, style notes) into the style layer so the LLM gets quantitative style guidance, not just prose descriptions.
- `compliance-and-banned-injection`: Push `banned_words` and `compliance_rules` (config DB) into the system prompt as a pre-generation constraint layer (was previously only checked post-hoc).
- `characters-md-fallback`: Parse `novels/{name}/characters.md` sections by character name and fall back to them when the DB row's `background` / `arc` / `lifeline` are all empty.
- `cross-volume-world-context`: World-building layer now returns local-volume entries (5) plus a global sample of later-volume entries (5) so cross-volume lore (e.g. 八神体系) is available in early chapters.

### Modified Capabilities

- `context-builder`: Layer count 9 → 12. Layer 1 reads all `project_meta` keys (not just novel row 3 fields). Layer 9 resolves preset names to `style_presets.prompt` + `style.md` + JSON fingerprint. Per-layer token budgets change to the new allocation table. Core instructions loaded from `prompts/core_instructions.j2` (single source of truth).

## Impact

- `portal/context_builder.py` — 3-layer additions, 4 layer-builder changes, token budget rebalance, jinja2 wiring (+~430 lines, 1 file).
- `portal/repository.py` — new `get_world_building_volume_plus_global` method (replaces `get_world_building_for_volume(limit=10)` call in Layer 5).
- `prompts/core_instructions.j2` — already in place; promoted from secondary copy to sole source.
- `tests/test_context_builder.py` — no changes; existing tests pass (1 pre-existing failure unrelated).
- No DB schema migration. No new API endpoint. No frontend change. All changes are server-side prompt assembly.

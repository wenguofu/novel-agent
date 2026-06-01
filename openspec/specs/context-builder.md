# context-builder

> **Architecture version: 12-layer (2026-06-02)**
> Updated by [writing-prompt-optimization change](../changes/writing-prompt-optimization/). Replaces the v3 9-layer design.

## Purpose

Server-side 12-layer system prompt assembly engine. Replaces the v2 client-side `_buildSystemPrompt` with DB-driven on-demand context loading. After the 2026-06-02 optimization pass, every layer pulls from the DB / files at near-full coverage (~95%) so the LLM has all the project state needed to write a chapter that follows the setting, style, and rules.

## Architecture

```
context_builder.py
  ├── _get_core_instructions() → "core_instructions" via PromptManager.render_or_default
  │      (loaded from prompts/core_instructions.j2; _CORE_INSTRUCTIONS_FALLBACK is the
  │       safety-net literal used only when jinja load fails)
  │
  ├── build_context(params) → {system_prompt, layers, total_tokens}
  │   ┌─ Layer 0  核心指令          (500 tok) — jinja2 template
  │   ├─ Layer 1  项目元信息        (500 tok) — novels row + project_meta 14 keys
  │   ├─ Layer 2  章节上下文        (800 tok) — outline + danger_issue + prev chapter
  │   ├─ Layer 2.5 类型规则         (500 tok) — 24 rules grouped by category (NEW)
  │   ├─ Layer 3  角色上下文       (2000 tok) — DB + characters.md fallback
  │   ├─ Layer 4  伏笔待办         (1000 tok) — DB filter by target_vol
  │   ├─ Layer 5  世界观           (1500 tok) — local 5 + global 5 (P2-3)
  │   ├─ Layer 6  节奏情感          (500 tok) — DB filter by vol/ch
  │   ├─ Layer 7  信息释放          (500 tok) — DB filter by reveal_vol
  │   ├─ Layer 8  剧情弧线         (1000 tok) — DB filter by vol range
  │   ├─ Layer 8.5 禁用词与合规     (200 tok) — from config DB (NEW)
  │   └─ Layer 9  写作风格          (500 tok) — style_presets + style.md + JSON fingerprint
  │
  └── get_context_stats(novel, vol, ch) → {layers: [{name, available}]}
```

**Total allocated: 9500 tok, with 500 tok elastic headroom (cap 10000).**

## Layer Details

| # | Name | Source | Builder | Notes |
|---|------|--------|---------|-------|
| 0 | 核心指令 | `prompts/core_instructions.j2` | `_get_core_instructions()` | Loaded via `PromptManager.render_or_default`; falls back to `_CORE_INSTRUCTIONS_FALLBACK` literal on jinja error |
| 1 | 项目元信息 | `novels` + `project_meta` | `_build_project_meta` | 3 lines from novel row + 14 `- **key**：value` lines from project_meta |
| 2 | 章节上下文 | `outlines` + `danger_issues` + `chapters` | `_build_chapter_context` | Regex-match the chapter section in the volume outline; pull `danger_issue` content; pull last 2000 chars of prev chapter for continuity |
| 2.5 | 类型规则 | `genre_rules` | `_build_genre_rules_context` | NEW. Grouped by `rule_category`. Required 🔴 / optional 🟡 |
| 3 | 角色上下文 | `characters` (+ `characters.md`) | `_build_character_context` | Top 5 by `current_vol`. Falls back to `characters.md` (parsed by `### {name}` heading) when DB `background`+`arc`+`lifeline` are all empty. Capped at 400 tok per character |
| 4 | 伏笔待办 | `foreshadowing` | `_build_foreshadowing_context` | Top 8 unresolved items filtered by `current_vol`. Reduced from 1500 → 1000 tok (P3-2) |
| 5 | 世界观 | `world_building` | `_build_world_context` | 5 local (`related_vol ∈ [vol-1, vol+1]`) + 5 global (later vol) entries. Tagged `[本卷\|domain]` / `[全局\|domain]` |
| 6 | 节奏情感 | `pacing_control` | `_build_pacing_context` | Per chapter, with `pace_type`, `intensity`, `emotion_target`, `word_budget_min/max` |
| 7 | 信息释放 | `revelation_schedule` | `_build_revelation_context` | Filtered by `reveal_vol` |
| 8 | 剧情弧线 | `plot_arcs` | `_build_plot_arc_context` | Filtered by vol range |
| 8.5 | 禁用词与合规 | `banned_words` + `compliance_rules` (config DB) | `_build_banned_compliance_context` | NEW. Compliance rules listed first, then banned words grouped by `category` with `→` arrows for replacements |
| 9 | 写作风格 | `style_presets` + `style.md` + `agent-system/styles/*.json` | `_build_style_context` | Parses "name 50%, name 50%" → resolves via `get_style_preset_by_name`. Loads `style.md` from `novels/{name}/`. Loads JSON fingerprint (`_load_style_fingerprint`) per author. Chunk format: header → 风格指纹 (stats) → 风格描述 (prose). `style.md` capped at 150 tok; each preset chunk capped at 250 tok |

## API

```
POST /api/context/build
  Request: {novel, volume, chapter_num, style, instructions, max_tokens}
  Response: {success, system_prompt, layers: [{name, content, tokens_used}], total_tokens}

GET /api/context/stats/<novel>/<vol>/<ch>
  Response: {success, layers: [{name, available}], novel, volume, chapter}
```

The `layers` array always has exactly 12 entries (in P3-2 allocation order). Empty layers (e.g. `pacing_control` table empty for this chapter) return `tokens_used: 0` and an empty `content` — they are NOT omitted from the array.

## Token Budget

- Uses `token_budget.py` TokenBudget class.
- Max total: 10000 (configurable via `max_tokens` param).
- Per-layer budgets: see allocation table above.
- Within each layer, builder may apply an internal sub-cap (e.g. style chunks 250 tok, characters.md fallback 400 tok) so budget cuts don't silently eat the most useful data.
- `total_tokens` reported in the response is `_count_tokens`-based (regex word count, Chinese 1.5 / English 1.3). The actual token count sent to DeepSeek may differ by ~5–10% on mixed Chinese/English text.

## Dependencies

- `content_db.py` — most DB reads (genre_rules, banned_words, project_meta, characters, foreshadowing, pacing, revelations, plot_arcs)
- `repository.py` — content_db wrapper, plus `get_world_building_volume_plus_global`, `list_project_meta`, `list_genre_rules`, `list_banned_words`, `list_compliance_rules`, `get_style_preset_by_name`
- `prompt_manager.py` — loads `prompts/core_instructions.j2` with cache
- `token_budget.py` — budget enforcement
- `novels/{name}/style.md` — book-specific style guide (optional)
- `novels/{name}/characters.md` — character section fallback (optional)
- `agent-system/styles/{author}.json` — author fingerprint (optional, by name)
- No RAG / chromadb integration. Pure DB + filesystem reads.

## Known Issues

- Pacing/revelation layers return 0 tokens if their tables have no data (expected — UI populates these on chapter setup).
- Token estimator is approximate; actual DeepSeek token count may differ ~5–10%.
- `_load_character_from_md` is regex-based (anchors on `^###\s+{name}\s*$`); exotic heading styles would miss silently.
- `agent-system/styles/*.json` has `sample_size_chars: 0` for some authors — fingerprint numbers are proxy guidance, not measurements; the LLM is told to treat them as guidance via the "风格指纹" label.
- No memoization; rebuilds context on every call (<50 ms for DB queries).
- Pre-existing test failure: `test_context_stats_structure` expects `"layers"` key for non-existent novels but `get_context_stats` returns `{"error": "小说不存在"}`. Unchanged by this optimization.

## Change History

| Date | Change | Summary |
|------|--------|---------|
| 2026-06-02 | [writing-prompt-optimization](../changes/writing-prompt-optimization/) | 9 → 12 layers. Added Layer 2.5 (genre rules), Layer 8.5 (banned + compliance), style JSON fingerprint, characters.md fallback, cross-volume world context. P3-2 rebalanced budget to 9500 tok allocated. P3-1 unified core_instructions to jinja2 template. |
| 2026-05-25 | [novel-agent-v3](../changes/archive/2026-05-25-novel-agent-v3/) | Original 9-layer design. |

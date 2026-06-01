## MODIFIED Requirements

### Requirement: Build context assembles a 12-layer system prompt

The system SHALL assemble a system prompt consisting of exactly 12 layers in the order: 0 核心指令, 1 项目元信息, 2 章节上下文, 2.5 类型规则, 3 角色上下文, 4 伏笔待办, 5 世界观, 6 节奏情感, 7 信息释放, 8 剧情弧线, 8.5 禁用词与合规, 9 写作风格. (Was: 9 layers, no 2.5 / 8.5.)

The system SHALL return `{system_prompt, layers, total_tokens}` where `layers` is a list of 12 `{name, content, tokens_used}` objects and `total_tokens` is the total of all layer `tokens_used` values.

#### Scenario: 12 layers in build_context response
- **WHEN** `build_context({name, volume, chapter_num, style, instructions, max_tokens: 10000})` is called for any novel
- **THEN** the response `layers` list contains exactly 12 entries, in the order specified above, with `tokens_used` summing to ≤ `max_tokens`

### Requirement: Per-layer token budget (P3-2 allocation table)

The system SHALL allocate token budgets to each layer as follows (total 9500 + 500 elastic):
- Layer 0 核心指令: 500
- Layer 1 项目元信息: 500
- Layer 2 章节上下文: 800
- Layer 2.5 类型规则: 500
- Layer 3 角色上下文: 2000
- Layer 4 伏笔待办: 1000 (was 1500)
- Layer 5 世界观: 1500
- Layer 6 节奏情感: 500
- Layer 7 信息释放: 500
- Layer 8 剧情弧线: 1000
- Layer 8.5 禁用词与合规: 200
- Layer 9 写作风格: 500

#### Scenario: Per-layer cap applied
- **WHEN** a layer's text exceeds its allocated budget
- **THEN** the layer's `content` is truncated to `min(text_tokens, budget)` via `_truncate_to_tokens`

### Requirement: Layer 1 loads all project_meta keys

The system SHALL query `repository.list_project_meta(novel_name)` and inject every (meta_key, meta_value) row as `- **{meta_key}**：{meta_value}` in Layer 1, after the novel-row block (书名 / 类型 / 目标篇幅).

#### Scenario: Novel with 14 project_meta keys
- **WHEN** 大强成神啦 has 14 project_meta rows (乐园, 八位古神, 叛神·系统, …)
- **THEN** Layer 1 contains the novel-row block (3 lines) + 14 `- **key**：value` lines under `## 核心设定（来自 project_meta — 必须严格遵守）`

#### Scenario: Novel with zero project_meta keys
- **WHEN** the novel has no project_meta rows
- **THEN** the 核心设定 section is omitted; Layer 1 still contains the novel-row block

### Requirement: Layer 9 resolves preset names to actual content

The system SHALL parse the `style` string (e.g. "辰东风 50%, 默认 50%") by splitting on comma, regex-matching each token as `^(.+?)\s+(\d+)\s*%$` (with name-only fallback to 100% weight), and resolving each name via `repository.get_style_preset_by_name(name)`.

The system SHALL inject the resolved `preset['prompt']` content into Layer 9. Names not found in the DB SHALL still appear in the output as `### {name}（权重 N%，未在 DB 中找到）` so the LLM is at least aware of the requested style.

#### Scenario: Style with two presets both found
- **WHEN** `style = "辰东风 50%, 默认 50%"` and both presets exist in `style_presets`
- **THEN** Layer 9 contains two `### {name}（权重 50%）` sections, each with the preset's `prompt` content

#### Scenario: Style with unknown preset
- **WHEN** `style = "某不存在风 100%"` and the preset is not in the DB
- **THEN** Layer 9 contains `### 某不存在风（权重 100%，未在 DB 中找到）` (no `prompt` content; the unknown marker is preserved)

### Requirement: core_instructions loaded from Jinja2 template

The system SHALL load Layer 0 (核心指令) from `prompts/core_instructions.j2` via `PromptManager.render_or_default("core_instructions", _CORE_INSTRUCTIONS_FALLBACK)`. The `_CORE_INSTRUCTIONS_FALLBACK` Python literal SHALL be kept as a safety net (used only when the jinja load fails) and SHALL be byte-for-byte identical to the `.j2` content.

#### Scenario: jinja2 available and template loads
- **WHEN** `jinja2` is installed and `prompts/core_instructions.j2` exists
- **THEN** Layer 0 content is the rendered `.j2` text (not the Python literal)

#### Scenario: jinja2 missing or template error
- **WHEN** `jinja2` is not installed or the `.j2` file fails to render
- **THEN** Layer 0 content falls back to the `_CORE_INSTRUCTIONS_FALLBACK` literal (no exception is raised; build_context still returns a valid result)

## REMOVED Requirements

### Requirement: Hardcoded CORE_INSTRUCTIONS as primary source
**Reason**: Promoted `prompts/core_instructions.j2` to single source of truth for layer 0 content. The Python literal was kept (renamed to `_CORE_INSTRUCTIONS_FALLBACK`) for graceful degradation only.
**Migration**: Edit `prompts/core_instructions.j2` to change the core instructions. The Python literal will not auto-sync; if the literal is out of sync with the `.j2`, a `diff` check at PR time catches the drift.

### Requirement: Layer 5 single-volume filter (limit=10)
**Reason**: Replaced by `get_world_building_volume_plus_global(local_limit=5, global_limit=5)` which adds cross-volume context. The previous `get_world_building_for_volume(novel, volume, limit=10)` call was dropping later-volume lore.
**Migration**: Callers should use `get_world_building_volume_plus_global(novel, volume, local_limit, global_limit)`. The old method is still available for callers that need strict single-volume behavior.

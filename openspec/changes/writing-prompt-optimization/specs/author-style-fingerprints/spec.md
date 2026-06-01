## ADDED Requirements

### Requirement: Load statistical style fingerprint from agent-system/styles/*.json

The system SHALL load `agent-system/styles/{author}.json` for each style preset name parsed from the frontend `style` string, where `{author}` is the preset name with trailing `风` stripped (so "辰东风" → "辰东.json", "番茄风" → "番茄.json").

The system SHALL extract the following fields and inject them into the style layer ahead of the prose preset prompt: `sentence_length_mean`, `dialogue_ratio`, `vocabulary_richness`, `transition_density`, top 5 entries from `transitions` (sorted by count), top 3 entries from `sentence_openers`, and `style_notes`.

#### Scenario: Known author with JSON fingerprint
- **WHEN** `style = "辰东风 50%"` is passed and `agent-system/styles/辰东.json` exists
- **THEN** Layer 9 content includes lines for 平均句长、对话占比、词汇丰富度、转折词密度、常用转折词 (top 5), 常用句首 (top 3), 风格摘要 — in that order — before the `style_presets.prompt` prose

#### Scenario: Unknown author with no JSON file
- **WHEN** `style = "辰东风 50%, 默认 50%"` is passed and `agent-system/styles/默认.json` does not exist
- **THEN** the "默认" chunk contains only the preset header and prose prompt (no fingerprint section); no error is raised

#### Scenario: JSON file exists but missing fields
- **WHEN** the JSON has `sentence_length_mean` and `style_notes` but no `transitions`
- **THEN** the fingerprint section includes 平均句长 and 风格摘要, and silently omits 转折词 rather than failing

### Requirement: Reorder style chunk so fingerprint precedes prose

The system SHALL structure each preset chunk as: `### {name}（权重 N%）` header, then `#### 风格指纹` section (stats), then `#### 风格描述` section (prose prompt). When the 500-tok Layer 9 budget truncates a chunk, the fingerprint section SHALL be preserved preferentially over the prose section.

#### Scenario: style.md + 2 chunks exceeds 500-tok budget
- **WHEN** `style.md` content is 150 tok and two preset chunks each contain 250 tok of content
- **THEN** each chunk is internally truncated to 250 tok before the outer layer cap is applied, so the fingerprint (positioned earlier in the chunk) is preserved when the layer-level 500-tok cap is applied

### Requirement: Cap internal style chunk size

The system SHALL apply a per-chunk token cap of 250 to each preset chunk inside `_build_style_context`, before the outer layer-level truncation.

#### Scenario: Single chunk exceeds 250 tok
- **WHEN** a preset chunk's combined header + fingerprint + prose exceeds 250 tok
- **THEN** `_truncate_to_tokens(chunk, 250)` is applied, preserving the first 250 tok (which includes the fingerprint and possibly truncates the prose tail)

### Requirement: Cap internal style.md size

The system SHALL apply a token cap of 150 to `style.md` content inside `_build_style_context` so that the book-specific style guide does not consume the entire 500-tok Layer 9 budget.

#### Scenario: Large style.md file
- **WHEN** `novels/{name}/style.md` is 2200 chars (~3000 tok)
- **THEN** only the first 150 tok are included in the layer, allowing the rest of the budget for style_presets chunks

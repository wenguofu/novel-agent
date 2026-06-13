# context-builder — delta

## ADDED Requirements

### Requirement: 12+1 layered context assembly

The context builder MUST assemble system prompts in a fixed layer order, with a default `max_tokens` ceiling of 500_000 (raised from 10_000), and MUST include Layer 1.5 `当前状态` between Layer 1 and Layer 2.

#### Scenario: default max_tokens is 500,000
- WHEN `build_context(params)` is called without a `max_tokens` kwarg
- THEN the returned `result["max_tokens"]` MUST equal 500_000

#### Scenario: 13 layers in fixed order
- WHEN `build_context(params)` is called for a novel with all data sources populated
- THEN `result["layers"]` MUST contain exactly 13 entries in the order: 核心指令, 项目元信息, 当前状态, 章节上下文, 类型规则, 角色上下文, 伏笔待办, 世界观, 节奏情感, 信息释放, 剧情弧线, 禁用词与合规, 写作风格

#### Scenario: current_status layer is omitted when file missing
- GIVEN `novels/{name}/state/current_status.md` does not exist
- WHEN `build_context(params)` is called
- THEN the `当前状态` layer MUST be omitted from `result["layers"]` and no error MUST be raised

#### Scenario: current_status layer is included when file present
- GIVEN `novels/{name}/state/current_status.md` exists with at least 50 chars of content
- WHEN `build_context(params)` is called
- THEN the `当前状态` layer MUST appear in `result["layers"]` and its `tokens_used` MUST be > 0

### Requirement: Layer 0 core instructions clamped to 500 tokens

The core-instructions layer (Layer 0) MUST be allocated with a hard cap of 500 tokens, regardless of the source template's rendered length.

#### Scenario: oversized j2 is clipped
- GIVEN `core_instructions.j2` is temporarily inflated to 5000 estimated tokens
- WHEN `build_context(params)` is called
- THEN the `核心指令` layer's `tokens_used` MUST be ≤ 500

### Requirement: Footer is rendered from chapter_context_footer.j2

The chapter context footer (volume / chapter / style / instructions) MUST be rendered via `PromptManager.render("chapter_context_footer", ...)` rather than from a hardcoded inline string.

#### Scenario: rendered prompt ends with the volume/chapter marker
- WHEN `build_context({"name": "X", "volume": 2, "chapter_num": 7, ...})` is called
- THEN the returned `system_prompt` MUST contain the substring "第2卷 第7章"

#### Scenario: footer style and instructions are interpolated
- WHEN `build_context({..., "style": "辰东风 80%", "instructions": "加快节奏"})` is called
- THEN the rendered `system_prompt` MUST contain "风格：辰东风 80%" and "用户指示：加快节奏"

### Requirement: Robust chapter outline locator

`_build_chapter_context` MUST locate the current chapter's outline section via an ordered list of patterns (4-digit, 3-digit, bare digit, Chinese numeral). On full miss it MUST log a warning and return an empty outline section — NOT fall through to `content[:1500]`.

#### Scenario: Chinese-numeral heading is recognized
- GIVEN the outline contains `### 第一百二十三章 标题`
- WHEN `_build_chapter_context` is called for chapter 123
- THEN the returned outline section MUST start at the `第一百二十三章` heading

#### Scenario: chapter locator miss returns empty
- GIVEN the outline contains NO occurrence of `第123章`, `第0123章`, `第000123章`, or `第一百二十三章`
- WHEN `_build_chapter_context` is called for chapter 123
- THEN the outline section MUST be `""` and a warning MUST be logged

### Requirement: Boundary-aware danger_issue trimming

The danger_issue slice MUST be trimmed to a sentence boundary (。/！/？/\n\n) at most 1200 characters, not a hard character slice.

#### Scenario: long danger_issue is trimmed at sentence boundary
- GIVEN a `danger_issue.content` of 1500 chars ending mid-sentence at char 1200 but with a `。` at char 1180
- WHEN `_build_chapter_context` is called
- THEN the returned `本章危机/关卡` section MUST end at or before char 1181 (just after the `。`)

### Requirement: Layer 0 mentions delivery block schema

The rendered `core_instructions` MUST contain the word `delivery` and the six field names `chapter_file`, `word_count`, `style_applied`, `new_settings_introduced`, `character_state_changes`, `foreshadowing_changes`.

#### Scenario: core contains delivery keywords
- WHEN `_get_core_instructions()` is called
- THEN the returned text MUST contain all of: `delivery`, `chapter_file`, `word_count`, `style_applied`, `new_settings_introduced`, `character_state_changes`, `foreshadowing_changes`

### Requirement: max_binary_contrasts is 2 everywhere

The constant `max_binary_contrasts` MUST equal 2 in BOTH `prompts/core_instructions.j2` (rendered text) and `agent-system/scripts/agent_executor.py` `content_heuristics`.

#### Scenario: constants agree
- WHEN the two sources are read
- THEN the j2-rendered "不超过N次" regex group MUST match `2`, and `agent_executor._AGENT_SCHEMAS["正文写作"]["content_heuristics"]["max_binary_contrasts"]` MUST equal `2`

## ADDED Requirements

### Requirement: Inject compliance rules into Layer 8.5

The system SHALL include all `compliance_rules` rows from the config DB in a new "禁用词与合规" layer (Layer 8.5) positioned between the plot arcs layer (Layer 8) and the style layer (Layer 9). Each rule SHALL be rendered as `- [{category}] {rule_key}: {rule_value}` and the rule description SHALL be appended in parentheses when it differs from the rule value.

#### Scenario: Config DB has compliance rules
- **WHEN** `config.db` has rows for `world_name=蓝星`, `naming_rule=所有地名...必须使用虚构名称`, `bypass_rule=不得使用谐音...`, `writing_style=...`
- **THEN** Layer 8.5 contains 4 lines, one per rule, each prefixed with its `[category]` and including the rule key, value, and description

#### Scenario: Empty compliance rules table
- **WHEN** `config.db` has zero `compliance_rules` rows
- **THEN** the "合规规则" subsection is omitted from Layer 8.5; the layer still renders the section header but with no rules listed

### Requirement: Inject banned words into Layer 8.5

The system SHALL include all `banned_words` rows from the config DB in Layer 8.5, grouped by `category`, with each group rendered as `- [{category}] {word1}→{repl1}、{word2}→{repl2}、…`. Words without a `replacement` SHALL be rendered as just the word.

#### Scenario: Banned words with replacements
- **WHEN** config DB has rows like `("中国", "国家", "夏国", "error")` and `("美国", "国家", "鹰国", "error")`
- **THEN** Layer 8.5 contains `- [国家] 中国→夏国、美国→鹰国`

#### Scenario: Banned words without replacements
- **WHEN** config DB has a row with empty `replacement` field
- **THEN** the word is rendered as just the word (no `→` arrow)

### Requirement: Layer 8.5 budget is 200 tokens

The system SHALL allocate a 200-tok budget to Layer 8.5 (禁用词与合规). When the rendered content exceeds 200 tok, the system SHALL truncate the layer to fit.

#### Scenario: Many banned words exceed 200 tok
- **WHEN** config DB has 100 banned words and 4 compliance rules totaling 350 tok
- **THEN** Layer 8.5 is truncated to 200 tok via `_truncate_to_tokens`, prioritizing earlier content (compliance rules render first, then banned words)

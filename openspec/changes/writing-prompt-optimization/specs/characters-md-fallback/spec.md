## ADDED Requirements

### Requirement: Fall back to characters.md when DB deep fields are empty

For each character included in Layer 3 (角色上下文), the system SHALL check whether the DB row's `background`, `arc`, and `lifeline` fields are all empty (whitespace-only treated as empty). When all three are empty, the system SHALL parse `novels/{name}/characters.md` for the character's section and inject it as `#### 📜 档案补充（来自 characters.md）` below the DB-derived stub.

#### Scenario: Character with all three deep fields empty
- **WHEN** the characters row for 付大强 has `background=""`, `arc=""`, `lifeline=""`
- **THEN** Layer 3 includes the DB-derived `### 付大强 (主角)` block AND a `#### 📜 档案补充（来自 characters.md）` block containing the parsed 付大强 section

#### Scenario: Character with at least one deep field populated
- **WHEN** the characters row for any character has any non-empty value in `background`, `arc`, or `lifeline`
- **THEN** the `characters.md` fallback is NOT triggered for that character (the DB content is considered sufficient)

#### Scenario: Identity/personality/current_status short stubs do not trigger fallback
- **WHEN** a character has `identity="刚毕业..."` (non-empty but short) but `background=""`, `arc=""`, `lifeline=""`
- **THEN** the fallback IS triggered (deep fields take precedence over the trigger check, identity/personality/status are not part of the trigger)

### Requirement: Parse characters.md by H3 heading

The system SHALL find the `### {character_name}` line in `novels/{name}/characters.md` (anchored on `^###\s+{name}\s*$` with `re.MULTILINE`) and capture content from the end of that line to the start of the next `## ` (H2) heading. All `###` subsections of that character (e.g. 背景与身世, 核心特质, 异能, 成长弧线) SHALL be included.

#### Scenario: Standard characters.md structure
- **WHEN** `novels/大强成神啦/characters.md` has `### 付大强` at line 7 followed by subsections 背景与身世 / 核心特质 / 系统宿主身份 / 异能：秩序 / 修真传承 / 成长弧线 / 付大强 vs 叛神系统的对抗历程, then `## 女主` at line 84
- **THEN** the fallback section for 付大强 contains all subsections between line 7 and line 84, including the table 字段/内容

#### Scenario: Character not found in characters.md
- **WHEN** the characters row for a character is loaded but no `### {name}` heading exists in `novels/{name}/characters.md`
- **THEN** the fallback is silently skipped; Layer 3 still contains the DB-derived `### {name}` block but no 档案补充

#### Scenario: characters.md file does not exist
- **WHEN** `novels/{name}/characters.md` does not exist on disk
- **THEN** all fallback lookups for that novel return empty string; no error is raised

### Requirement: Cap characters.md fallback to 400 tokens per character

When the parsed section exceeds 400 tok, the system SHALL truncate via `_truncate_to_tokens` so that a single verbose character does not consume the entire 2000-tok Layer 3 budget.

#### Scenario: Parsed section exceeds 400 tok
- **WHEN** the 付大强 section in characters.md is 2000 chars (~2700 tok)
- **THEN** the injected 档案补充 is truncated to 400 tok, preserving the first 400 tok (header table + early 背景与身世 paragraphs)

# Tasks — writing-prompt-v2-optimization

## 1. Unify footer source

- [x] 1.1 Delete inline footer literal in `context_builder.py:199-202`; replace with `pm.render("chapter_context_footer", {...})`
- [x] 1.2 Verify `chapter_context_footer.j2` is unchanged; its `ChapterFooterVars` schema stays in `prompt_manager._SCHEMA_MAP`
- [x] 1.3 Test: `test_footer_uses_jinja2_template` (asserts the rendered prompt ends with `第{vol}卷 第{num}章`)
- [x] 1.4 Test: `test_footer_includes_style_and_instructions`

## 2. Inject `current_status.md`

- [x] 2.1 Add `_build_current_status_context(novel_name)` in `context_builder.py` — reads `novels/{name}/state/current_status.md`, returns up to 1000 tok
- [x] 2.2 Wire as Layer 1.5 in `build_context` between `项目元信息` and `章节上下文`
- [x] 2.3 Skip silently if file is missing (no error, no empty layer)
- [x] 2.4 Update `agent-system/team/agent-writing.md` frontmatter so `prerequisites` matches reality (add `state/current_status.md` if previously absent — verify before changing)
- [x] 2.5 Test: `test_current_status_included` (file present → layer present)
- [x] 2.6 Test: `test_current_status_missing_is_silent` (file absent → no crash, no empty layer)

## 3. Robust chapter locator

- [x] 3.1 Define `LOCATOR_PATTERNS` ordered list in `context_builder.py` (4-digit, 3-digit, bare, Chinese numeral)
- [x] 3.2 Add `_chinese_numeral_pattern(num)` helper (handles 1–9999)
- [x] 3.3 Replace single regex in `_build_chapter_context` with a loop over the patterns
- [x] 3.4 On full miss: log a warning, return `""` for that section (no fallthrough to `content[:1500]`)
- [x] 3.5 Test: `test_chapter_locator_chinese_numeral` (outline with `第一百二十三章` is sliced correctly)
- [x] 3.6 Test: `test_chapter_locator_miss_returns_empty_not_fallthrough`

## 4. Clamp Layer 0 to 500 tok

- [x] 4.1 In `build_context`, change `budget.allocate("核心指令", core_tokens)` → `budget.allocate("核心指令", min(core_tokens, 500))`
- [x] 4.2 Test: `test_core_instructions_clamped_to_500` (inflated j2 content of 5000 tok is clipped to ≤500 tok in the layer)

## 5. Inject existing-chapter payload

- [x] 5.1 In `api_generate_chapter_v2` (around `app.py:1852-1864`), branch on `chapter_exists`:
  - [x] 5.1.1 Read the existing chapter file
  - [x] 5.1.2 Prepend a `## 上一版本正文` block (capped at 4000 tok) to the system prompt
  - [x] 5.1.3 Keep the existing `⚠️ 该章节已存在，请基于已有内容续写或重写` hint
- [x] 5.2 Test: `test_existing_chapter_payload_injected` (mocked `chapter_exists` → prompt contains "上一版本正文" block)

## 6. Reconcile `max_binary_contrasts`

- [x] 6.1 In `core_instructions.j2`, change "全文不超过1次" → "全文不超过2次"
- [x] 6.2 Confirm `agent_executor.py`'s `content_heuristics.max_binary_contrasts: 2` is unchanged (it is the canonical constant)
- [x] 6.3 Test: `test_binary_contrasts_constants_agree` (parse j2 + parse Python dict, assert both == 2)

## 7. Add delivery-block instruction

- [x] 7.1 Append to `core_instructions.j2` a "## 输出格式" section with the `delivery` YAML schema (see design.md §Delivery-block instruction)
- [x] 7.2 Test: `test_core_instructions_has_delivery_block` (rendered core contains `delivery` + the six field names: `chapter_file`, `word_count`, `style_applied`, `new_settings_introduced`, `character_state_changes`, `foreshadowing_changes`)

## 8. Lift internal sub-caps

- [x] 8.1 `style.md` cap 150 → 2000 tok
- [x] 8.2 Per-preset chunk cap 250 → 1500 tok
- [x] 8.3 `characters.md` per-character cap 400 → 2000 tok
- [x] 8.4 Per-layer cap increases per design.md table
- [x] 8.5 No test needed (additive; covered by regression on existing test_context_builder.py)

## 9. Lift default `max_tokens` to 500_000

- [x] 9.1 `build_context` default `max_tokens` param 10000 → 500000
- [x] 9.2 `/api/context/build` docstring updated
- [x] 9.3 Test: `test_default_max_tokens_is_500_000` (call without kwarg, assert `result["max_tokens"] == 500_000`)

## 10. boundary-aware danger_issue trim

- [x] 10.1 Add `_trim_to_sentence(text, max_chars)` helper in `context_builder.py`
- [x] 10.2 Replace `danger.get('content', '')[:800]` with `_trim_to_sentence(danger.get('content', ''), 1200)`
- [x] 10.3 Test: `test_danger_issue_trimmed_at_sentence_boundary`

## 11. Verify

- [x] 11.1 Run `pytest -q tests/` (full suite) — all green
- [x] 11.2 Run `openspec validate writing-prompt-v2-optimization --strict` — all green
- [x] 11.3 Run `git status` — no stray files
- [x] 11.4 Self-audit: invoke verification-before-completion skill

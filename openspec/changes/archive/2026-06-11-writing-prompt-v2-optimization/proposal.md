## Why

After the 2026-06-02 `writing-prompt-optimization` pass added 3 layers and resolved style/genre into the prompt, a code review surfaced 7 correctness/contract issues that the previous pass did not fix:

1. **Dead template** — `prompts/chapter_context_footer.j2` is registered in `prompt_manager._SCHEMA_MAP` but never rendered; the footer in `context_builder.py:199-202` is hardcoded inline.
2. **Prerequisite drift** — `agent-system/team/agent-writing.md` declares `current_status.md` as a required input, but `context_builder` does not load it. Continuity rides entirely on the previous chapter's last 2000 chars.
3. **Brittle chapter locator** — Layer 2's regex only matches 3-/4-digit-padded or bare numbers. Falls through to `content[:1500]` on miss, returning an unrelated outline section.
4. **Core-instruction has no upper cap** — Layer 0 allocates the full j2 length with no clamp. Future edits push other layers off-budget.
5. **No chapter-exists payload** — `app.py` appends a "已存在" hint, but the prompt contains zero of the existing chapter's content. LLM has no way to "续写".
6. **Schema-mismatch on `max_binary_contrasts`** — `core_instructions.j2` says "不超过1次" but `agent_executor.py`'s `content_heuristics.max_binary_contrasts` is `2`.
7. **No delivery-block instruction** — `agent-writing.md` defines an output_schema for the delivery block, but `core_instructions.j2` does not tell the LLM to emit one.

The user has confirmed the model can accept **up to 500k tokens** of system prompt, so the 10000-tok cap that forces aggressive truncation is no longer binding. We can lift internal sub-caps, add the layers the previous pass could not afford (`current_status.md`, existing-chapter payload), and keep `TokenBudget` as a 500k-ceiling guard rail rather than the primary design constraint.

## What Changes

### 1. Unify footer source
- Delete the inline footer literal at `context_builder.py:199-202` and call `pm.render("chapter_context_footer", {...})` instead.
- Add a focused unit test that asserts the rendered footer contains `第{vol}卷 第{num}章`.

### 2. Inject `current_status.md`
- New builder `_build_current_status_context` (Layer 1.5 between meta and chapter context) that reads `novels/{name}/state/current_status.md` and caps at 1000 tok.
- Skip silently if file is missing (it's optional).
- Update `STAGE_AGENTS`/agent-writing frontmatter so the prerequisite claim matches reality.

### 3. Robust chapter locator
- Replace the single regex in `_build_chapter_context` with a list of patterns tried in order: 4-digit / 3-digit / bare / Chinese numeral (`第一百二十三章`).
- On full miss, log a warning and return `""` for that section — never silently fall through to `content[:1500]`.
- Cap `danger_issue` slice at nearest `。` / `\n\n` boundary below 1200 chars instead of hard `[:800]`.

### 4. Clamp Layer 0 to 500 tok
- Wrap `_get_core_instructions()` allocation with `min(core_tokens, 500)` so future j2 edits cannot blow the budget.
- Also raise the default `max_tokens` from 10000 to 500000 in `build_context`'s default and the API docstring.

### 5. Inject existing-chapter payload (when applicable)
- `app.py:1843` already detects `chapter_exists`; thread the existing content (capped at 4000 tok) into the system prompt as a "上一版本正文" block ahead of the chapter context.
- When chapter does NOT exist, no extra block.

### 6. Reconcile `max_binary_contrasts`
- Set `core_instructions.j2` to "全文不超过2次" (matching `agent_executor.content_heuristics.max_binary_contrasts: 2`).
- Add a test that asserts the constant in both places agrees.

### 7. Add delivery-block instruction
- Append to `core_instructions.j2` a "**输出格式**" section telling the LLM to emit, after the chapter body, a fenced YAML block labelled `delivery` with `chapter_file`, `word_count`, `style_applied`, `new_settings_introduced`, `character_state_changes`, `foreshadowing_changes`.
- Add a unit test that asserts the rendered core contains the `delivery` keyword and the six field names.

### 8. Lift internal sub-caps (style / characters / etc.)
- `style.md` cap 150 → 2000 tok; per-preset chunk cap 250 → 1500 tok.
- `characters.md` per-character cap 400 → 2000 tok.
- All other layer caps raised in proportion; the global `TokenBudget(max_tokens=500_000)` becomes the real ceiling.

## Capabilities

### Modified Capabilities
- `context-builder`: Layer count 12 → 13 (new Layer 1.5 `current_status`). Layer 2 chapter locator rewritten. Layer 0 clamped. Layer 9 sub-caps lifted. Default `max_tokens` 10000 → 500000. Internal `_truncate_to_tokens` left in place as a guard rail but the input sizes are sized so truncation is rare in practice.
- `agent-writing`: `prerequisites` (frontmatter + hardcoded schema) updated to match what the prompt actually loads.

### Removed
- The hardcoded footer literal in `context_builder.py:199-202` (replaced by j2 render).

## Impact

- `portal/context_builder.py` — 1 new builder, 4 builder changes, footer refactor, default cap change (~120 lines delta).
- `portal/prompts/core_instructions.j2` — `max_binary_contrasts` 1→2, add `delivery` block instruction (~15 lines).
- `portal/app.py:1852-1864` — thread existing chapter content into prompt when present (~10 lines).
- `agent-system/team/agent-writing.md` — frontmatter `prerequisites` updated.
- `agent-system/scripts/agent_executor.py` — `max_binary_contrasts: 2` (no change, just to confirm the constant is the canonical one).
- `tests/test_context_builder.py` + new `tests/unit/test_writing_prompt_v2.py` — ~10 new test cases covering the 7 fixes.
- No DB migration. No new API endpoint. No frontend change.

## Out of Scope

- Replacing `_count_tokens` with a real tokenizer (still regex-based heuristic; the budget is now large enough that 10% error is harmless).
- RAG/chromadb integration (already absent in the spec; not part of this change).
- The `chapter-exists` hint wording is unchanged — we now provide the actual content the LLM needs to act on it.

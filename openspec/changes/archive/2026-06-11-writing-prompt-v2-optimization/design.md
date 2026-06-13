# Design — writing-prompt-v2-optimization

## Layer table (post-change)

| # | Name | Per-layer cap | Source | Notes |
|---|------|---------------|--------|-------|
| 0 | 核心指令 | 500 tok (clamped) | `prompts/core_instructions.j2` | New `min(core_tokens, 500)` clamp. Mentions `delivery` block & `max_binary_contrasts: 2`. |
| 1 | 项目元信息 | 1000 tok | `novels` row + `project_meta` | Cap raised 500→1000. |
| 1.5 | 当前状态 | 1000 tok (NEW) | `state/current_status.md` | Optional, skip if missing. |
| 2 | 章节上下文 | 2000 tok | outline + danger_issue + prev chapter | Robust locator (see §Robust chapter locator). danger_issue sliced to nearest sentence boundary ≤1200 chars. |
| 2.5 | 类型规则 | 1500 tok | `genre_rules` | Cap raised 500→1500. |
| 3 | 角色上下文 | 4000 tok | `characters` + `characters.md` fallback | Per-character md fallback cap 400→2000 tok. |
| 4 | 伏笔待办 | 2000 tok | `foreshadowing` | Cap raised 1000→2000. |
| 5 | 世界观 | 3000 tok | `world_building` 5+5 | Cap raised 1500→3000. |
| 6 | 节奏情感 | 1000 tok | `pacing` | Cap raised 500→1000. |
| 7 | 信息释放 | 1500 tok | `revelations` | Cap raised 500→1500. |
| 8 | 剧情弧线 | 2000 tok | `plot_arcs` | Cap raised 1000→2000. |
| 8.5 | 禁用词与合规 | 500 tok | `banned_words` + `compliance_rules` | Cap raised 200→500. |
| 9 | 写作风格 | 3000 tok | `style.md` (2000) + per-preset chunks (1500) | Internal sub-caps lifted. |

**Total allocated: ~20_500 tok, ceiling 500_000 tok.** The budget is now a guard rail, not a binding constraint.

## Robust chapter locator

Replace the single regex with an ordered list of patterns tried in `re.search`. Each pattern is anchored to a chapter heading; we slice from the match start to the next `第\s*\d+\s*章` or `\n## ` boundary.

```python
LOCATOR_PATTERNS = [
    r"第\s*0*{num:04d}\s*章",   # 4-digit padded, e.g. 第0023章
    r"第\s*0*{num:03d}\s*章",   # 3-digit padded
    r"第\s*{num}\s*章",         # bare number
    _chinese_numeral_pattern(num),  # e.g. 第一百二十三章
]
```

If every pattern misses, log a warning (`logging.warning("[context_builder] chapter {vol}-{num} locator miss")`) and return `""` for the outline section. The other layers (danger_issue, prev chapter) still load.

The Chinese-numeral helper converts an int ≤ 9999 to its 长字符串 form (`一百二十三`, `二千零五`) and regexes `第{form}章`.

## danger_issue boundary-aware slice

```python
def _trim_to_sentence(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # back up to last 。 or \n\n
    for sep in ("\n\n", "。", "！", "？"):
        idx = cut.rfind(sep)
        if idx > max_chars * 0.5:
            return cut[:idx + len(sep)]
    return cut
```

## Footer via PromptManager

```python
footer = pm.render_or_default(
    "chapter_context_footer",
    default="",  # safety net only
    variables={"volume": volume, "chapter_num": chapter_num,
               "style": style, "instructions": instructions},
)
if footer:
    prompt_parts.append(footer)
```

`chapter_context_footer.j2` keeps its current text; we just stop ignoring it.

## Existing-chapter payload (app.py)

`api_generate_chapter_v2` already computes `chapter_exists`. New branch:

```python
if chapter_exists:
    with open(ch_file_path, "r", encoding="utf-8") as f:
        existing = f.read()
    existing_block = _truncate_to_tokens(existing, 4000)
    ctx["system_prompt"] = (
        "## 上一版本正文（仅供续写/重写参考，不要原样复制）\n"
        + existing_block + "\n\n" + ctx["system_prompt"]
    )
    ctx["system_prompt"] += "\n\n⚠️ 该章节已存在，请基于已有内容续写或重写。"
```

`context_builder` itself stays pure (no filesystem reads outside `novels/{name}/state/` and `novels/{name}/style.md` / `characters.md`); the existing-chapter payload is wired at the call site in `app.py` because it depends on the user-facing "generate" flow rather than the generic `build_context`.

## Delivery-block instruction in core_instructions.j2

Append to the j2 (right after the existing bullet list):

```markdown
## 输出格式
请输出两部分：
1. **章节正文** — 以 `# 第X章 标题` 开头的纯小说文本
2. **delivery 块** — 正文结束后，输出如下 YAML 围栏块（脚本会解析）：

```yaml
delivery:
  chapter_file: manuscript/vol-{vol}/ch-{ch:04d}.md
  word_count: <整数>
  style_applied: <已应用的风格>
  new_settings_introduced:
    - name: <设定名>
      category: <物品|地点|规则>
  character_state_changes:
    - name: <人物名>
      change: <变化描述>
  foreshadowing_changes:
    added: [<伏笔>]
    triggered: [<伏笔>]
```
```

This brings the prompt in line with `agent-writing.md`'s `output_schema`.

## Token cap lift

`build_context` default `max_tokens` param: 10000 → 500000. The API endpoint accepts the override; the default change is reflected in the docstring + the `/api/context/build` handler.

`token_budget.TokenBudget(max_tokens=500_000)` is constructed internally; `allocate()` is unchanged. With per-layer caps summing to ~20.5k and the elastic headroom, the LLM sees a real prompt ~20k–50k tok depending on the novel's data density.

## Test strategy

| Test | Asserts |
|---|---|
| `test_footer_uses_jinja2_template` | Rendered prompt ends with `第{vol}卷 第{num}章` from `chapter_context_footer.j2`. |
| `test_footer_includes_style_and_instructions` | When `style` and `instructions` are non-empty, both appear in the footer. |
| `test_current_status_included` | When `state/current_status.md` exists, a "当前状态" layer appears in output. |
| `test_current_status_missing_is_silent` | When `state/current_status.md` is absent, no empty layer, no error. |
| `test_chapter_locator_chinese_numeral` | Outline with `第一百二十三章` heading is sliced correctly. |
| `test_chapter_locator_miss_returns_empty_not_fallthrough` | Outline without the target chapter returns `""` and logs a warning. |
| `test_core_instructions_clamped_to_500` | Inflated j2 content (e.g. 5000 tok) is clipped to ≤500 tok in the layer. |
| `test_binary_contrasts_constants_agree` | `core_instructions.j2` and `agent_executor.content_heuristics.max_binary_contrasts` are both `2`. |
| `test_core_instructions_has_delivery_block` | Rendered core contains the string `delivery` and the six required field names. |
| `test_danger_issue_trimmed_at_sentence_boundary` | A 1500-char danger_issue is trimmed to ≤1200 chars ending on a `。` / `\n\n`. |
| `test_default_max_tokens_is_500_000` | `build_context({...})` with no `max_tokens` kwarg uses 500_000 internally. |
| `test_existing_chapter_payload_injected` | When the chapter file exists, `api_generate_chapter_v2` includes "上一版本正文" in the system prompt. |

All tests will be in a new file `tests/unit/test_writing_prompt_v2.py` so the diff is isolated to the v2 change.

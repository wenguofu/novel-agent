"""
Context Builder — Server-side 9-layer system prompt assembly.
Replaces the client-side _buildSystemPrompt with DB-driven on-demand loading.

Architecture (P3-2 allocation table, total 9500 tok, 500 elastic):
  Layer 0:    Core Instructions        (500 tok) — from prompts/core_instructions.j2
  Layer 1:    Project Meta             (500 tok) — novel row + project_meta 14 keys
  Layer 2:    Chapter Context          (800 tok) — outline + danger_issue + prev
  Layer 2.5:  Genre Rules              (500 tok) — 24 rules grouped by category (NEW)
  Layer 3:    Characters              (2000 tok) — DB + characters.md fallback
  Layer 4:    Foreshadowing           (1000 tok) — DB filter by target_vol
  Layer 5:    World Building          (1500 tok) — local 5 + global 5 (P2-3)
  Layer 6:    Pacing/Emotion           (500 tok) — DB filter by vol/ch
  Layer 7:    Revelation               (500 tok) — DB filter by reveal_vol
  Layer 8:    Plot Arcs               (1000 tok) — DB filter by vol range
  Layer 8.5:  Banned + Compliance      (200 tok) — from config DB (NEW)
  Layer 9:    Style                    (500 tok) — style_presets + style.md + JSON
  Total max: 10000 tokens
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))
from token_budget import TokenBudget
import content_db as db


# ═══════════════════════════════════════════════════════════════════════
# Layer Definitions
# ═══════════════════════════════════════════════════════════════════════

# Fallback copy of the Jinja2 template (portal/prompts/core_instructions.j2)
# — used only if PromptManager fails to load the .j2. Keep in sync if the
# .j2 changes.
_CORE_INSTRUCTIONS_FALLBACK = """你是一个专业的长篇网文写作Agent。你的任务是**严格按照项目设定和大纲**写出高质量的小说章节。

## ⚠️ 脚本强制约束（必须遵守）
- 每章不少于2500字，不使用真实地名人名
- **禁止**"不是...而是..."二元对照句式（全文不超过1次）
- **禁止**连续简单判断句超过2句
- **禁止**"XX说：+ 对话"的生硬格式，改用动作+对话自然衔接
- **禁止**大段内心独白式的解释说明（show, don't tell）
- 段落至少2-3句，对话占比30-50%，关键情节用场景呈现
- **必须严格遵循大纲/卷纲/危机要求**
- 人物行为必须符合人物档案，遵守类型规则和世界观设定
- **伏笔管理（脚本强制）**：如果系统提示有待填坑伏笔，必须在本章推进或解释
- 必须有明确的章节功能和悬念/钩子结尾
- 请输出完整的章节正文，以"# 章节标题"开头。
"""


def _get_core_instructions() -> str:
    """Single source of truth: load from Jinja2 template, fall back to literal.

    The hardcoded Python copy was removed in P3-1 — prompts/core_instructions.j2
    is now the only author-editable location.
    """
    from prompt_manager import get_prompt_manager
    pm = get_prompt_manager()
    return pm.render_or_default("core_instructions", _CORE_INSTRUCTIONS_FALLBACK)


def _count_tokens(text):
    """Rough token estimation"""
    import re
    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    en = len(re.findall(r'[a-zA-Z]+', text))
    return int(cn * 1.5 + en * 1.3)


def _truncate_to_tokens(text, max_tokens):
    """Truncate text to fit within max_tokens budget using character-level counting.
    Fixes BUG-04: replaces naive content[:allocated * 2] for Chinese accuracy."""
    if not text:
        return ""
    result = []
    token_count = 0
    for ch in text:
        ch_tokens = 1.5 if '\u4e00' <= ch <= '\u9fff' else 1.3 if ch.isalpha() else 0.5
        if token_count + ch_tokens > max_tokens:
            break
        result.append(ch)
        token_count += ch_tokens
    return ''.join(result)


def build_context(params):
    """
    Build layered context for chapter generation.

    Args:
        params: dict with keys:
            name (str): novel name
            volume (int): current volume number
            chapter_num (int): current chapter number
            style (str): writing style preference
            instructions (str): user instructions
            max_tokens (int): total token cap (default 10000)

    Returns:
        {system_prompt, layers: [{name, content, tokens_used}], total_tokens}
    """
    novel_name = params.get("name", "")
    volume = params.get("volume", 1)
    if isinstance(volume, str):
        if volume.startswith("vol-"):
            volume = int(volume.split("-")[1])
        else:
            volume = int(volume)
    chapter_num = int(params.get("chapter_num", 1))
    style = params.get("style", "")
    instructions = params.get("instructions", "")
    max_tokens = int(params.get("max_tokens", 10000))

    budget = TokenBudget(max_tokens=max_tokens)
    layers = []

    # LAYER 0: Core Instructions (always included) — loaded from Jinja2
    core_text = _get_core_instructions()
    core_tokens = _count_tokens(core_text)
    budget.allocate("核心指令", core_tokens)
    layers.append({"name": "核心指令", "content": core_text, "tokens_used": core_tokens})

    # LAYER 1: Project Meta (novel row + full project_meta 14 keys)
    meta_text = _build_project_meta(novel_name)
    meta_tokens = _count_tokens(meta_text)
    allocated = budget.allocate("项目元信息", min(meta_tokens, 500))
    layers.append({"name": "项目元信息", "content": _truncate_to_tokens(meta_text, allocated), "tokens_used": allocated})

    # LAYER 2: Chapter Context (outline + danger + prev)
    ch_ctx = _build_chapter_context(novel_name, volume, chapter_num)
    ch_ctx_tokens = _count_tokens(ch_ctx)
    allocated = budget.allocate("章节上下文", min(ch_ctx_tokens, 800))
    layers.append({"name": "章节上下文", "content": _truncate_to_tokens(ch_ctx, allocated), "tokens_used": allocated})

    # LAYER 3: Characters (RAG top-3)
    char_text = _build_character_context(novel_name, volume, chapter_num)
    char_tokens = _count_tokens(char_text)
    allocated = budget.allocate("角色上下文", min(char_tokens, 2000))
    layers.append({"name": "角色上下文", "content": _truncate_to_tokens(char_text, allocated), "tokens_used": allocated})

    # LAYER 3.5: Genre Rules (type-level constraints — must-haves, pacing, reader expectations)
    gr_text = _build_genre_rules_context(novel_name)
    gr_tokens = _count_tokens(gr_text)
    allocated = budget.allocate("类型规则", min(gr_tokens, 500))
    layers.append({"name": "类型规则", "content": _truncate_to_tokens(gr_text, allocated), "tokens_used": allocated})

    # LAYER 4: Foreshadowing (DB query)
    fs_text = _build_foreshadowing_context(novel_name, volume)
    fs_tokens = _count_tokens(fs_text)
    allocated = budget.allocate("伏笔待办", min(fs_tokens, 1000))
    layers.append({"name": "伏笔待办", "content": _truncate_to_tokens(fs_text, allocated), "tokens_used": allocated})

    # LAYER 5: World Building (RAG top-5)
    wb_text = _build_world_context(novel_name, volume, chapter_num)
    wb_tokens = _count_tokens(wb_text)
    allocated = budget.allocate("世界观", min(wb_tokens, 1500))
    layers.append({"name": "世界观", "content": _truncate_to_tokens(wb_text, allocated), "tokens_used": allocated})

    # LAYER 6: Pacing/Emotion
    pace_text = _build_pacing_context(novel_name, volume, chapter_num)
    pace_tokens = _count_tokens(pace_text)
    allocated = budget.allocate("节奏情感", min(pace_tokens, 500))
    layers.append({"name": "节奏情感", "content": _truncate_to_tokens(pace_text, allocated), "tokens_used": allocated})

    # LAYER 7: Revelation
    rev_text = _build_revelation_context(novel_name, volume)
    rev_tokens = _count_tokens(rev_text)
    allocated = budget.allocate("信息释放", min(rev_tokens, 500))
    layers.append({"name": "信息释放", "content": _truncate_to_tokens(rev_text, allocated), "tokens_used": allocated})

    # LAYER 8: Plot Arcs
    arc_text = _build_plot_arc_context(novel_name, volume)
    arc_tokens = _count_tokens(arc_text)
    allocated = budget.allocate("剧情弧线", min(arc_tokens, 1000))
    layers.append({"name": "剧情弧线", "content": _truncate_to_tokens(arc_text, allocated), "tokens_used": allocated})

    # LAYER 8.5: Banned Words + Compliance Rules (hard constraints from config DB)
    bw_text = _build_banned_compliance_context()
    bw_tokens = _count_tokens(bw_text)
    allocated = budget.allocate("禁用词与合规", min(bw_tokens, 200))
    layers.append({"name": "禁用词与合规", "content": _truncate_to_tokens(bw_text, allocated), "tokens_used": allocated})

    # LAYER 9: Style + Instructions
    style_text = _build_style_context(style, instructions, novel_name)
    style_tokens = _count_tokens(style_text)
    allocated = budget.allocate("写作风格", min(style_tokens, 500))
    layers.append({"name": "写作风格", "content": _truncate_to_tokens(style_text, allocated), "tokens_used": allocated})

    # Assemble system prompt
    prompt_parts = []
    for layer in layers:
        if layer["content"].strip():
            prompt_parts.append(layer["content"])

    # Add volume/chapter footer
    footer = f"\n当前卷：第{volume}卷 第{chapter_num}章\n"
    if style: footer += f"风格：{style}\n"
    if instructions: footer += f"用户指示：{instructions}\n"
    prompt_parts.append(footer)

    system_prompt = "\n\n".join(prompt_parts)
    actual_total = _count_tokens(system_prompt)

    return {
        "system_prompt": system_prompt,
        "layers": layers,
        "total_tokens": actual_total,
        "max_tokens": budget.max_tokens,
    }


# ═══════════════════════════════════════════════════════════════════════
# Layer Builders
# ═══════════════════════════════════════════════════════════════════════

def _build_project_meta(novel_name):
    """Extract project metadata via repository.

    Loads BOTH the novel row (title/genre/word_goal) and the full project_meta
    table (14 keys — 八位古神, 叛神系统, 乐园, etc. for 大强成神啦). The DB
    rows are the authoritative core-setting source.
    """
    from repository import get_repo
    repo = get_repo()
    novel = repo.get_novel(novel_name)
    if not novel:
        return ""

    parts = ["## 项目信息"]
    parts.append(f"- 书名：{novel.get('title') or novel_name}")
    parts.append(f"- 类型：{novel.get('genre') or '未设置'}")
    parts.append(f"- 目标篇幅：{novel.get('word_goal') or '未设置'}")

    # ── Append all project_meta key/value pairs (core setting) ──
    meta_rows = repo.list_project_meta(novel_name) or []
    if meta_rows:
        parts.append("\n## 核心设定（来自 project_meta — 必须严格遵守）")
        for row in meta_rows:
            key = (row.get("meta_key") or "").strip()
            val = (row.get("meta_value") or "").strip()
            if not key or not val:
                continue
            parts.append(f"- **{key}**：{val}")
    return "\n".join(parts)

def _build_chapter_context(novel_name, volume, chapter_num):
    """Get outline section + danger issue + previous chapter ending via repository"""
    from repository import get_repo
    repo = get_repo()
    parts = []
    vol_str = f"vol-{volume:02d}"

    # Outline section
    outline = repo.get_outline(novel_name, vol_str)
    if outline:
        content = outline.get("content", "")
        ch_padded_3 = str(chapter_num).zfill(3)
        ch_padded_4 = str(chapter_num).zfill(4)
        import re
        pattern = re.compile(f'第\\s*({ch_padded_3}|{ch_padded_4}|{chapter_num})\\s*章')
        m = pattern.search(content)
        if m:
            start = m.start()
            next_ch = re.search(r'第\s*\d+\s*章', content[start+10:])
            end = start + 10 + next_ch.start() if next_ch else min(start + 1500, len(content))
            parts.append(f"## 卷纲要求\n{content[start:end]}")
        else:
            parts.append(f"## 本卷大纲\n{content[:1500]}")

    # Danger issue
    danger = repo.get_danger_issue(novel_name, vol_str, chapter_num)
    if danger:
        parts.append(f"## 本章危机/关卡\n{danger.get('content', '')[:800]}")

    # Previous chapter ending (for continuity)
    if chapter_num > 1:
        prev_ch = repo.get_chapter_by_num(novel_name, vol_str, chapter_num - 1)
        if prev_ch:
            parts.append(f"## 上一章结尾（衔接）\n{prev_ch.get('content', '')[-2000:]}")

    return "\n\n".join(parts)


def _load_character_from_md(novel_name, character_name):
    """Extract a character's section from novels/{name}/characters.md.

    Finds `### {character_name}` heading and returns content until the next
    `## ` (H2) heading — including all `###` subsections like 背景与身世,
    核心特质, 成长弧线. Returns "" if not found.
    """
    md_path = os.path.join(
        os.path.dirname(__file__), "..", "novels", novel_name, "characters.md"
    )
    if not os.path.exists(md_path):
        return ""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return ""

    import re as _re
    # Match heading: "### {name}" on its own line
    pattern = _re.compile(rf"^###\s+{_re.escape(character_name)}\s*$", _re.MULTILINE)
    m = pattern.search(content)
    if not m:
        return ""
    start = m.end()
    # End at next H2 (## xxx) — this is where the next role section starts
    next_h2 = _re.search(r"^##\s+", content[start:], _re.MULTILINE)
    end = start + next_h2.start() if next_h2 else len(content)
    return content[start:end].strip()


def _build_character_context(novel_name, volume, chapter_num):
    """Get relevant character info from DB (characters appearing in this volume).

    DB columns (identity/personality/current_status/emotional_state) are often
    short stubs — when background / personality / current_status is empty,
    fall back to novels/{name}/characters.md for the rich section.
    """
    chars = db.get_characters(novel_name)
    if not chars:
        return ""

    # Filter: protagonist + characters active in current volume
    relevant = [c for c in chars if c["role"] in ("主角", "女主") or c["current_vol"] >= volume - 1]
    if len(relevant) > 5:
        relevant = relevant[:5]

    parts = ["## 角色档案"]
    for c in relevant:
        info = f"### {c['name']} ({c['role']})"
        if c.get("identity"): info += f"\n- 身份：{c['identity'][:200]}"
        if c.get("personality"): info += f"\n- 性格：{c['personality'][:200]}"
        if c.get("current_status"): info += f"\n- 当前状态：{c['current_status'][:200]}"
        if c.get("emotional_state"): info += f"\n- 情感：{c['emotional_state'][:200]}"
        parts.append(info)

        # ── Fallback to characters.md when key DB fields are sparse ──
        # The DB's "rich" fields (background/arc/lifeline) are often empty
        # stubs — the MD file is the only source of truth for deep character
        # setting (成长弧线, 背景与身世, 核心特质). Trigger on those three.
        deep_fields_empty = not any([
            (c.get("background") or "").strip(),
            (c.get("arc") or "").strip(),
            (c.get("lifeline") or "").strip(),
        ])
        if deep_fields_empty:
            md_section = _load_character_from_md(novel_name, c["name"])
            if md_section:
                # Trim to fit per-character budget (~400 tokens)
                trimmed = _truncate_to_tokens(md_section, 400)
                parts.append(f"#### 📜 档案补充（来自 characters.md）\n{trimmed}")
    return "\n\n".join(parts)


def _build_genre_rules_context(novel_name):
    """Get genre rules grouped by category via repository.

    Loads 24 type-level rules (must-haves, pacing, reader expectations) from
    `genre_rules` table. Required rules are marked with 🔴, optional with 🟡,
    grouped by `rule_category` so the LLM can quickly scan the type contract.
    """
    from repository import get_repo
    rules = get_repo().list_genre_rules(novel_name)
    if not rules:
        return ""

    # Group by rule_category, preserving input order
    by_category = {}
    for r in rules:
        cat = (r.get("rule_category") or "通用").strip() or "通用"
        by_category.setdefault(cat, []).append(r)

    parts = ["## 类型规则（genre_rules — 必须遵守）"]
    for cat, items in by_category.items():
        parts.append(f"### {cat}")
        for r in items:
            mark = "🔴" if r.get("is_required") else "🟡"
            content = (r.get("rule_content") or "").strip()
            if content:
                parts.append(f"- {mark} {content}")
    return "\n".join(parts)


def _build_foreshadowing_context(novel_name, volume):
    """Get pending foreshadowing items relevant to this volume"""
    items = db.get_unresolved_foreshadowing(novel_name, current_vol=volume)
    if not items:
        return ""

    parts = ["## ⚠️ 待填坑伏笔（脚本强制，本章如涉及必须处理）"]
    for f in items[:8]:
        priority_mark = "🔴" if f.get("priority") == "high" else "🟡"
        parts.append(f"- {priority_mark} **{f['name']}** ({f.get('category','')})")
        if f.get("description"): parts.append(f"  {f['description'][:200]}")
        if f.get("target_vol"):
            parts.append(f"  目标填坑：第{f['target_vol']}卷" + (f"第{f.get('target_ch','?')}章" if f.get("target_ch") else ""))
    return "\n".join(parts)


def _build_world_context(novel_name, volume, chapter_num):
    """Active world-building entries — current-volume (5) + later-volume sample (5).

    The later-volume sample ensures cross-volume lore (e.g. 八神体系, 外星
    种族) is not dropped from the prompt just because the current chapter is
    in an early volume. Without this, the LLM can't foreshadow properly.
    """
    from repository import get_repo
    rows = get_repo().get_world_building_volume_plus_global(
        novel_name, volume, local_limit=5, global_limit=5
    )
    if not rows:
        return ""
    parts = ["## 世界观要点（当前卷 5 条 + 全局设定 5 条）"]
    for r in rows:
        # Mark later-volume entries so the LLM knows they're cross-volume
        rv = r.get("related_vol", 0)
        scope = "全局" if (rv and rv > volume + 1) else "本卷"
        parts.append(f"- [{scope}|{r.get('domain', '')}] {r.get('name', '')}: {r.get('content', '')[:200]}")
    return "\n".join(parts)

def _build_pacing_context(novel_name, volume, chapter_num):
    """Pacing control info for current chapter via repository"""
    from repository import get_repo
    row = get_repo().get_pacing(novel_name, volume, chapter_num)
    if not row:
        return ""
    parts = [f"## 节奏控制\n- 类型：{row.get('pace_type', '')}\n- 强度：{row.get('intensity', 5)}/10"]
    if row.get('emotion_target'):
        parts.append(f"- 情感目标：{row['emotion_target']}")
    parts.append(f"- 字数预算：{row.get('word_budget_min', 2500)}–{row.get('word_budget_max', 3500)}")
    if row.get('notes'):
        parts.append(f"- 备注：{row['notes'][:200]}")
    return "\n".join(parts)

def _build_revelation_context(novel_name, volume):
    """Revelation schedule for current volume via repository"""
    from repository import get_repo
    rows = get_repo().get_revelations_for_volume(novel_name, volume)
    if not rows:
        return ""
    parts = ["## 信息释放排期"]
    for r in rows:
        parts.append(f"- [第{r.get('reveal_chapter', 0)}章][{r.get('info_type', '')}] {r.get('name', '')}: {r.get('content', '')[:150]}")
    return "\n".join(parts)

def _build_plot_arc_context(novel_name, volume):
    """Active plot arcs for current volume via repository"""
    from repository import get_repo
    rows = get_repo().get_plot_arcs_for_volume(novel_name, volume)
    if not rows:
        return ""
    parts = ["## 剧情线"]
    for r in rows:
        parts.append(f"- [{r.get('type', '')}] {r.get('name', '')}: {r.get('summary', '')[:200]}")
    return "\n".join(parts)

def _build_banned_compliance_context():
    """Get banned words + compliance rules from config DB via repository.

    These are hard constraints (config-level, not per-novel) — global banned
    vocabulary plus regulatory rules. LLM is told to avoid these patterns
    proactively rather than relying on post-hoc checks.
    """
    from repository import get_repo
    repo = get_repo()
    parts = ["## 禁用词与合规规则（必须遵守）"]

    # ── Compliance rules (highest priority — these are absolute) ──
    compliance = repo.list_compliance_rules() or []
    if compliance:
        parts.append("### 合规规则")
        for r in compliance:
            key = (r.get("rule_key") or "").strip()
            val = (r.get("rule_value") or "").strip()
            desc = (r.get("description") or "").strip()
            cat = (r.get("category") or "").strip()
            head = f"- [{cat}] {key}" if cat else f"- {key}"
            if val:
                head += f": {val}"
            if desc and desc != val:
                head += f"（{desc}）"
            parts.append(head)

    # ── Banned words (group by category, keep compact) ──
    banned = repo.list_banned_words() or []
    if banned:
        by_cat = {}
        for b in banned:
            cat = (b.get("category") or "通用").strip() or "通用"
            by_cat.setdefault(cat, []).append(b)
        parts.append("### 禁用词")
        for cat, items in by_cat.items():
            words = []
            for b in items:
                word = (b.get("word") or "").strip()
                repl = (b.get("replacement") or "").strip()
                if not word:
                    continue
                if repl:
                    words.append(f"{word}→{repl}")
                else:
                    words.append(word)
            if words:
                parts.append(f"- [{cat}] {'、'.join(words)}")

    return "\n".join(parts)


def _load_style_fingerprint(author_name):
    """Load statistical fingerprint JSON for an author.

    Looks for `agent-system/styles/{name}.json` — strips trailing 风 so
    "辰东风" → "辰东.json", "番茄风" → "番茄.json". Returns a compact
    multi-line string with the most actionable stats, or "" if not found.
    """
    # Normalize: "辰东风" → "辰东", "番茄风" → "番茄"
    clean = author_name.rstrip("风").rstrip("风")
    base_dir = os.path.join(os.path.dirname(__file__), "..", "agent-system", "styles")
    fp_path = os.path.join(base_dir, f"{clean}.json")
    if not os.path.exists(fp_path):
        return ""
    try:
        with open(fp_path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
    except Exception:
        return ""

    lines = []
    slm = data.get("sentence_length_mean")
    if isinstance(slm, (int, float)):
        lines.append(f"- 平均句长：{slm} 字")
    dr = data.get("dialogue_ratio")
    if isinstance(dr, (int, float)):
        lines.append(f"- 对话占比：{dr:.0%}")
    vr = data.get("vocabulary_richness")
    if isinstance(vr, (int, float)):
        lines.append(f"- 词汇丰富度：{vr:.2f}")
    td = data.get("transition_density")
    if isinstance(td, (int, float)):
        lines.append(f"- 转折词密度：{td}")
    # Top 5 transitions
    trans = data.get("transitions") or {}
    if isinstance(trans, dict) and trans:
        top = sorted(trans.items(), key=lambda kv: kv[1], reverse=True)[:5]
        top_str = "、".join(f"{w}({n})" for w, n in top)
        lines.append(f"- 常用转折词：{top_str}")
    # Top 3 openers
    openers = data.get("sentence_openers") or []
    if isinstance(openers, list) and openers:
        top3 = openers[:3]
        top3_str = "、".join(
            f"\"{o.get('opener','')}\"({o.get('frequency', 0):.0%})"
            for o in top3 if isinstance(o, dict)
        )
        if top3_str:
            lines.append(f"- 常用句首：{top3_str}")
    notes = data.get("style_notes")
    if notes:
        lines.append(f"- 风格摘要：{notes}")
    if not lines:
        return ""
    return "\n".join(lines)


def _build_style_context(style, instructions, novel_name):
    """Build style guidance.

    Resolves the frontend style string (e.g. "辰东风 50%, 默认 50%") into the
    actual style_presets.prompt content from the DB. Augments with statistical
    fingerprints from agent-system/styles/*.json. Falls back to a novel-
    specific style.md if present.
    """
    import json as _json
    from repository import get_repo
    parts = []

    # ── 1. Novel-specific style.md (highest priority) ──
    # If novels/{name}/style.md exists, use it as the authoritative style guide.
    style_md_path = os.path.join(
        os.path.dirname(__file__), "..", "novels", novel_name, "style.md"
    )
    style_md_text = ""
    if os.path.exists(style_md_path):
        try:
            with open(style_md_path, "r", encoding="utf-8") as f:
                style_md_text = f.read()
        except Exception:
            pass

    if style_md_text:
        # Cap at 150 so style_presets (prompt + fingerprint) has room within
        # the 500-token Layer 9 budget. style.md is verbose (5KB); the LLM
        # only needs the salient style summary here.
        trimmed = _truncate_to_tokens(style_md_text, 150)
        parts.append(f"## 本书专属风格（来自 style.md）\n{trimmed}")

    # ── 2. Resolve preset names → prompt content + fingerprint ──
    # Frontend sends: "辰东风 50%, 默认 50%"
    # We split by comma, look each name up in style_presets, and assemble
    # the actual descriptions rather than just echoing the name. Augment
    # with the statistical fingerprint from agent-system/styles/*.json.
    if style:
        repo = get_repo()
        style_chunks = []
        for token in style.split(","):
            token = token.strip()
            if not token:
                continue
            # Parse "name 50%" or just "name"
            import re as _re
            m = _re.match(r"^(.+?)\s+(\d+)\s*%$", token)
            if m:
                name, weight = m.group(1).strip(), int(m.group(2))
            else:
                name, weight = token.strip(), 100
            preset = repo.get_style_preset_by_name(name)
            prompt_block = ""
            if preset and preset.get("prompt"):
                prompt_block = preset['prompt']
            elif preset:
                prompt_block = "（无 prompt 内容）"
            else:
                # Unknown name — keep it visible so the LLM at least knows.
                prompt_block = "（未在 DB 中找到）"

            # Try to load the statistical fingerprint for this author.
            fingerprint = _load_style_fingerprint(name)

            # Fingerprint (statistical) is more actionable than the prompt's
            # prose — put it first so budget cuts from the end preserve it.
            if fingerprint:
                chunk = (
                    f"### {name}（权重 {weight}%）\n"
                    f"#### 风格指纹（来自 {name} 的句法统计）\n"
                    f"{fingerprint}\n\n"
                    f"#### 风格描述（来自 style_presets）\n"
                    f"{prompt_block}"
                )
            else:
                chunk = f"### {name}（权重 {weight}%）\n{prompt_block}"
            # Cap each chunk at 250 tok so 2 chunks + style.md fit in 500.
            chunk = _truncate_to_tokens(chunk, 250)
            style_chunks.append(chunk)

        if style_chunks:
            parts.append("## 写作风格预设（来自 style_presets）\n" + "\n\n".join(style_chunks))

    if instructions:
        parts.append(f"## 用户指示\n{instructions}")
    return "\n\n".join(parts)


def get_context_stats(novel_name: str, volume: int, chapter_num: int) -> dict:
    """Get stats about available context for a chapter via repository.

    Always returns a `{"layers": [...]}` structure (list of {name, available}
    dicts) so callers can rely on the shape regardless of whether the novel
    exists. Layers for a nonexistent novel are reported as `available=False`.
    """
    from repository import get_repo
    repo = get_repo()
    novel = repo.get_novel(novel_name)

    # Layer definitions — keep in sync with the builders in build_context().
    layer_names = [
        "core_instructions",
        "project_meta",
        "chapter_context",
        "characters",
        "genre_rules",
        "foreshadowing",
        "world_building",
        "pacing",
        "revelation",
        "plot_arcs",
        "banned_compliance",
        "style",
    ]

    if not novel:
        # Novel does not exist — every layer is unavailable, but we still
        # return the same shape so the API consumer doesn't have to branch.
        return {
            "novel": novel_name,
            "volume": volume,
            "chapter_num": chapter_num,
            "novel_exists": False,
            "layers": [{"name": n, "available": False} for n in layer_names],
        }

    nid = novel['id']
    vol_str = f"vol-{volume:02d}"

    # Probe each layer to decide `available`. Use lightweight DB checks.
    has_outline = bool(repo.get_outline(novel_name, vol_str))
    has_chapter_ctx = has_outline or bool(repo.get_danger_issue(novel_name, vol_str, chapter_num))
    has_pacing = bool(repo.get_pacing(novel_name, volume, chapter_num))

    layers = [
        {"name": "core_instructions", "available": True},  # always loaded from Jinja2
        {"name": "project_meta", "available": True},       # novel row exists
        {"name": "chapter_context", "available": has_chapter_ctx},
        {"name": "characters", "available": bool(repo.list_characters(novel_name))},
        {"name": "genre_rules", "available": bool(repo.list_genre_rules(novel_name))},
        {"name": "foreshadowing", "available": bool(repo.get_unresolved_foreshadowing(novel_name, volume, chapter_num))},
        {"name": "world_building", "available": bool(repo.list_world_building(novel_name))},
        {"name": "pacing", "available": has_pacing},
        {"name": "revelation", "available": bool(repo.get_revelations_for_volume(novel_name, volume))},
        {"name": "plot_arcs", "available": bool(repo.list_plot_arcs(novel_name))},
        {"name": "banned_compliance", "available": True},   # always loaded from config DB
        {"name": "style", "available": True},               # style guidance always present
    ]

    vol_chapters = len([c for c in repo.list_chapters(novel_name) if c.get('volume') == vol_str])
    return {
        "novel": novel_name,
        "volume": volume,
        "chapter_num": chapter_num,
        "novel_exists": True,
        "total_chapters": novel.get('total_chapters', 0),
        "volume_chapters": vol_chapters,
        "characters": sum(1 for l in layers if l["name"] == "characters") and len(repo.list_characters(novel_name)),
        "unresolved_foreshadowing": len(repo.get_unresolved_foreshadowing(novel_name, volume, chapter_num)),
        "world_building": len(repo.list_world_building(novel_name)),
        "plot_arcs": len(repo.list_plot_arcs(novel_name)),
        "pacing": 1 if has_pacing else 0,
        "revelations": len(repo.get_revelations_for_volume(novel_name, volume)),
        "layers": layers,
    }


def _build_fallback_state_context(novel_name: str, volume: int, chapter_num: int) -> str:
    """Build a minimal state-context string for fallback / nonexistent novels.

    Returns an empty string when the novel does not exist in the DB (caller
    can safely concatenate the result). When the novel exists, returns a
    compact one-liner identifying the volume/chapter so downstream prompts
    can still anchor to the right position.
    """
    if not novel_name:
        return ""
    try:
        from repository import get_repo
        novel = get_repo().get_novel(novel_name)
    except Exception:
        return ""
    if not novel:
        return ""
    return f"[state-context] novel={novel_name} vol={volume} ch={chapter_num}"
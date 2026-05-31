"""
Volume-Scoped Context Builder — fixed version of context_builder.py

Key fixes over the original:
1. Layer 3 (Characters): Only shows characters active in current volume, strips future arcs/endings
2. Layer 4 (Foreshadowing): 3-tier system (due_now/overdue/recent) scoped by volume
3. Layer 5 (World Building): Cap at 5 entries (was 10), tighter volume scoping
4. Layer 10 (State Evolution): Only recent changes, no full character profiles
5. All layers have volume-aware filtering with hard token caps

Import in context_builder.py by adding at the top:
    from context_builder_v2 import build_context_volume_scoped
Then use build_context_volume_scoped instead of build_context.
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(__file__))
from token_budget import TokenBudget
from token_utils import count_tokens, truncate_to_tokens
from prompt_manager import get_prompt_manager
from repository import get_repo

# Cache for built contexts
_CONTEXT_CACHE_V2 = {}
_CONTEXT_CACHE_V2_TTL = 60
_CONTEXT_CACHE_V2_MAX = 100
_CONTEXT_CACHE_V2_LOCK = threading.Lock()


def _get_core_instructions() -> str:
    """Load core instructions from Jinja2 template."""
    pm = get_prompt_manager()
    default = """你是一个专业的长篇网文写作Agent。你的任务是**严格按照项目设定和大纲**写出高质量的小说章节。

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
    return pm.render_or_default("core_instructions", default)


def build_context_volume_scoped(params):
    """Build volume-scoped context for chapter generation.

    All layers now filter by current volume — no future spoilers, no irrelevant data.
    """
    novel_name = params.get("name", "")
    volume = params.get("volume", 1)
    if isinstance(volume, str):
        volume = int(volume.split("-")[1]) if volume.startswith("vol-") else int(volume)
    chapter_num = int(params.get("chapter_num", 1))
    style = params.get("style", "")
    instructions = params.get("instructions", "")
    max_tokens = int(params.get("max_tokens", 12000))

    # Cache check
    cache_key = f"{novel_name}|{volume}|{chapter_num}|{style}|{instructions}|v2"
    now = time.time()
    with _CONTEXT_CACHE_V2_LOCK:
        if cache_key in _CONTEXT_CACHE_V2:
            cached_time, cached_result = _CONTEXT_CACHE_V2[cache_key]
            if now - cached_time < _CONTEXT_CACHE_V2_TTL:
                return cached_result

    repo = get_repo()
    budget = TokenBudget(max_tokens=max_tokens)
    layers = []

    # LAYER 0: Core Instructions
    core_text = _get_core_instructions()
    core_tokens = count_tokens(core_text)
    budget.allocate("核心指令", core_tokens)
    layers.append({"name": "核心指令", "content": core_text, "tokens_used": core_tokens})

    # LAYER 1: Project Meta
    meta_text = _build_project_meta_v2(repo, novel_name)
    meta_tokens = count_tokens(meta_text)
    allocated = budget.allocate("项目元信息", min(meta_tokens, 300))
    layers.append({"name": "项目元信息", "content": truncate_to_tokens(meta_text, allocated), "tokens_used": allocated})

    # LAYER 2: Chapter Context (outline + danger + prev)
    ch_ctx = _build_chapter_context_v2(repo, novel_name, volume, chapter_num)
    ch_ctx_tokens = count_tokens(ch_ctx)
    allocated = budget.allocate("章节上下文", min(ch_ctx_tokens, 800))
    layers.append({"name": "章节上下文", "content": truncate_to_tokens(ch_ctx, allocated), "tokens_used": allocated})

    # LAYER 3: Characters — VOLUME SCOPED (major fix)
    char_text = _build_character_context_v2(repo, novel_name, volume)
    char_tokens = count_tokens(char_text)
    allocated = budget.allocate("角色上下文", min(char_tokens, 1500))
    layers.append({"name": "角色上下文", "content": truncate_to_tokens(char_text, allocated), "tokens_used": allocated})

    # LAYER 4: Foreshadowing — 3-TIER VOLUME SCOPED (major fix)
    fs_text = _build_foreshadowing_context_v2(repo, novel_name, volume)
    fs_tokens = count_tokens(fs_text)
    allocated = budget.allocate("伏笔待办", min(fs_tokens, 1000))
    layers.append({"name": "伏笔待办", "content": truncate_to_tokens(fs_text, allocated), "tokens_used": allocated})

    # LAYER 5: World Building — capped at 5
    wb_text = _build_world_context_v2(repo, novel_name, volume)
    wb_tokens = count_tokens(wb_text)
    allocated = budget.allocate("世界观", min(wb_tokens, 1000))
    layers.append({"name": "世界观", "content": truncate_to_tokens(wb_text, allocated), "tokens_used": allocated})

    # LAYER 6: Pacing
    pace_text = _build_pacing_context_v2(repo, novel_name, volume, chapter_num)
    pace_tokens = count_tokens(pace_text)
    allocated = budget.allocate("节奏情感", min(pace_tokens, 500))
    layers.append({"name": "节奏情感", "content": truncate_to_tokens(pace_text, allocated), "tokens_used": allocated})

    # LAYER 7: Revelation — per volume
    rev_text = _build_revelation_context_v2(repo, novel_name, volume)
    rev_tokens = count_tokens(rev_text)
    allocated = budget.allocate("信息释放", min(rev_tokens, 500))
    layers.append({"name": "信息释放", "content": truncate_to_tokens(rev_text, allocated), "tokens_used": allocated})

    # LAYER 8: Plot Arcs — volume-range filtered
    arc_text = _build_plot_arc_context_v2(repo, novel_name, volume)
    arc_tokens = count_tokens(arc_text)
    allocated = budget.allocate("剧情弧线", min(arc_tokens, 800))
    layers.append({"name": "剧情弧线", "content": truncate_to_tokens(arc_text, allocated), "tokens_used": allocated})

    # LAYER 9: RAG Memory (best-effort)
    mem_text = _build_memory_context_v2(repo, novel_name, volume, chapter_num)
    mem_tokens = count_tokens(mem_text)
    allocated = budget.allocate("RAG记忆检索", min(mem_tokens, 2000))
    layers.append({"name": "RAG记忆检索", "content": truncate_to_tokens(mem_text, allocated), "tokens_used": allocated})

    # LAYER 10: State Evolution — VOLUME SCOPED (major fix)
    state_text = _build_state_context_v2(repo, novel_name, volume)
    state_tokens = count_tokens(state_text)
    allocated = budget.allocate("状态演化", min(state_tokens, 1000))
    layers.append({"name": "状态演化", "content": truncate_to_tokens(state_text, allocated), "tokens_used": allocated})

    # LAYER 11: Style
    style_text = _build_style_context_simple(style, instructions, novel_name)
    style_tokens = count_tokens(style_text)
    allocated = budget.allocate("写作风格", min(style_tokens, 500))
    layers.append({"name": "写作风格", "content": truncate_to_tokens(style_text, allocated), "tokens_used": allocated})

    # Assemble
    prompt_parts = [l["content"] for l in layers if l["content"].strip()]
    pm = get_prompt_manager()
    footer = pm.render("chapter_context_footer", {"volume": volume, "chapter_num": chapter_num,
                                                    "style": style, "instructions": instructions})
    if not footer:
        footer = f"\n当前卷：第{volume}卷 第{chapter_num}章\n"
        if style:
            footer += f"风格：{style}\n"
        if instructions:
            footer += f"用户指示：{instructions}\n"
    prompt_parts.append(footer)

    system_prompt = "\n\n".join(prompt_parts)
    actual_total = count_tokens(system_prompt)

    result = {
        "system_prompt": system_prompt,
        "layers": layers,
        "total_tokens": actual_total,
        "max_tokens": budget.max_tokens,
    }

    with _CONTEXT_CACHE_V2_LOCK:
        _CONTEXT_CACHE_V2[cache_key] = (now, result)
        if len(_CONTEXT_CACHE_V2) > _CONTEXT_CACHE_V2_MAX:
            oldest = min(_CONTEXT_CACHE_V2, key=lambda k: _CONTEXT_CACHE_V2[k][0])
            del _CONTEXT_CACHE_V2[oldest]

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Layer Builders (volume-scoped)
# ═══════════════════════════════════════════════════════════════════════════

def _build_project_meta_v2(repo, novel_name):
    """Extract project metadata."""
    novel = repo.get_novel(novel_name)
    if not novel:
        return ""
    return f"""## 项目信息
- 书名：{novel.get('title') or novel_name}
- 类型：{novel.get('genre') or '未设置'}
- 目标篇幅：{novel.get('word_goal') or '未设置'}"""


def _build_chapter_context_v2(repo, novel_name, volume, chapter_num):
    """Get outline section + danger issue + previous chapter ending."""
    parts = []

    # Try YAML outline first
    outline_text = _read_outline_yaml_v2(novel_name, volume, chapter_num)
    if outline_text:
        parts.append(outline_text)
    else:
        # Fallback: markdown outline
        vol_str = f"vol-{volume:02d}"
        outline = repo.get_outline(novel_name, vol_str)
        if outline:
            import re as _re
            content = outline.get("content", "")
            ch_padded = str(chapter_num).zfill(3)
            pattern = _re.compile(f'第\\s*({ch_padded}|{str(chapter_num).zfill(4)}|{chapter_num})\\s*章')
            m = pattern.search(content)
            if m:
                start = m.start()
                next_ch = _re.search(r'第\s*\d+\s*章', content[start+10:])
                end = start + 10 + next_ch.start() if next_ch else min(start + 1500, len(content))
                parts.append(f"## 卷纲要求\n{content[start:end]}")
            else:
                parts.append(f"## 本卷大纲\n{content[:1500]}")

    # Danger issue
    vol_str = f"vol-{volume:02d}"
    danger = repo.get_danger_issue(novel_name, vol_str, chapter_num)
    if danger:
        parts.append(f"## 本章危机/关卡\n{danger['content'][:800]}")

    # Previous chapter ending
    if chapter_num > 1:
        prev = repo.get_chapter_by_num(novel_name, vol_str, chapter_num - 1)
        if prev:
            parts.append(f"## 上一章结尾（衔接）\n{prev['content'][-2000:]}")

    return "\n\n".join(parts)


def _read_outline_yaml_v2(novel_name, volume, chapter_num):
    """Read YAML-format outline (same as original)."""
    import os as _os
    novel_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                               "novels", novel_name)
    yaml_content = None
    for ext in ('.yaml', '.yml'):
        yaml_path = _os.path.join(novel_dir, "outline", f"vol-{volume:02d}-chapters{ext}")
        if _os.path.exists(yaml_path):
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    yaml_content = f.read()
                break
            except (IOError, UnicodeDecodeError):
                continue

    if not yaml_content:
        return ""

    try:
        import yaml
        data = yaml.safe_load(yaml_content)
    except Exception:
        try:
            import json as _json
            data = _json.loads(yaml_content)
        except Exception:
            return ""

    if not data or not isinstance(data, dict):
        return ""

    chapters = data.get('chapters', [])
    ch_data = None
    for ch in chapters:
        if ch.get('number') == chapter_num:
            ch_data = ch
            break

    if not ch_data:
        lines = [f"## 第{volume}卷大纲"]
        if data.get('volume_name'):
            lines.append(f"卷名：{data['volume_name']}")
        return "\n".join(lines)

    lines = [f"## 第{volume}卷第{chapter_num}章 写作指令"]
    if data.get('volume_name'):
        lines.append(f"本卷：{data['volume_name']}")
    if ch_data.get('title'):
        lines.append(f"### 章名：{ch_data['title']}")
    function = ch_data.get('function', [])
    if isinstance(function, str):
        function = [function]
    if function:
        lines.append("### 本章功能（必须实现）")
        for f in function:
            lines.append(f"- {f}")
    if ch_data.get('core_events'):
        lines.append("### 核心事件（必须包含）")
        events = ch_data['core_events']
        if isinstance(events, list):
            for e in events:
                lines.append(f"- {e}")
        else:
            lines.append(f"- {events}")
    if ch_data.get('foreshadowing'):
        fs = ch_data['foreshadowing']
        if isinstance(fs, list):
            lines.append("### 本章需推进的伏笔")
            for f in fs:
                lines.append(f"- {f}")
        else:
            lines.append(f"### 本章需推进的伏笔\n- {fs}")
    if ch_data.get('ending_hook'):
        lines.append(f"### 结尾牵引\n{ch_data['ending_hook']}")
    if data.get('rhythm_rules'):
        rr = data['rhythm_rules']
        danger_chs = rr.get('danger_scenes', [])
        crisis_chs = rr.get('major_crises', [])
        if chapter_num in danger_chs:
            lines.append("\n⚠️ 本章为**高压章节**——必须写出可见危机、临界心理、主角被牵入过程")
        if chapter_num in crisis_chs:
            lines.append("\n🔴 本章为**重大危机章**——需要完整的危机爆发→应对→结果闭环")
    if ch_data.get('style_hint'):
        lines.append(f"\n风格提示：{ch_data['style_hint']}")

    return "\n".join(lines)


def _build_character_context_v2(repo, novel_name, volume):
    """VOLUME-SCOPED: Only active characters, no future arcs/endings.

    Key fix: Strips 'ending', 'arc', 'lifeline' fields.
    Only shows characters whose current_vol is within ±1 of current volume.
    Protagonist always included but with CURRENT state only.
    """
    chars = repo.list_characters_active_in_volume(novel_name, volume)
    if not chars:
        return ""

    parts = ["## 角色档案（当前卷活跃角色）"]
    count = 0
    for c in chars:
        if count >= 5:
            break
        info = f"### {c['name']} ({c.get('role', '?')})"

        # Only include fields relevant to CURRENT state — NEVER future arcs
        if c.get("identity") and c.get("current_vol", 0) <= volume:
            info += f"\n- 身份：{c['identity'][:200]}"
        if c.get("personality"):
            info += f"\n- 性格：{c['personality'][:150]}"
        if c.get("current_status"):
            info += f"\n- 当前状态：{c['current_status'][:200]}"
        if c.get("emotional_state"):
            info += f"\n- 当前情感：{c['emotional_state'][:100]}"
        if c.get("current_vol") and c.get("current_ch"):
            info += f"\n- 最新位置：第{c['current_vol']}卷第{c['current_ch']}章"

        # NEVER include: ending, arc (full growth arc), lifeline
        # These are future spoilers that should not leak into the writing prompt

        parts.append(info)
        count += 1

    return "\n\n".join(parts)


def _build_foreshadowing_context_v2(repo, novel_name, volume):
    """3-TIER VOLUME-SCOPED foreshadowing.

    Tier 1: Due NOW (target_vol == current_vol) — MUST handle
    Tier 2: OVERDUE (target_vol < current_vol, unresolved) — should advance
    Tier 3: Recent introductions (introduced_vol >= current_vol - 2) — be aware

    Total items capped at 5 (was 8 unlimited).
    """
    data = repo.get_foreshadowing_for_volume(novel_name, volume)

    if not data["due_now"] and not data["overdue"] and not data["recent"]:
        return ""

    parts = []

    if data["due_now"]:
        parts.append("## 🔴 伏笔必须解决（本章目标卷=当前卷）")
        for f in data["due_now"]:
            parts.append(f"- **{f['name']}** ({f.get('category', '剧情')})")
            if f.get("description"):
                parts.append(f"  {f['description'][:200]}")
            if f.get("target_ch"):
                parts.append(f"  目标：第{f['target_vol']}卷第{f['target_ch']}章")

    if data["overdue"]:
        parts.append("## ⚠️ 伏笔逾期未填坑（应在之前卷解决）")
        for f in data["overdue"][:3]:
            parts.append(f"- **{f['name']}** (原定第{f.get('target_vol', '?')}卷)")
            if f.get("description"):
                parts.append(f"  {f['description'][:150]}")

    if data["recent"]:
        parts.append("## 🟡 近期埋入伏笔（保持意识）")
        for f in data["recent"][:2]:
            parts.append(f"- **{f['name']}** (第{f.get('introduced_vol', '?')}卷埋入)")

    return "\n".join(parts)


def _build_world_context_v2(repo, novel_name, volume):
    """Volume-scoped world building, capped at 5 entries."""
    entries = repo.get_world_building_for_volume(novel_name, volume, limit=5)
    if not entries:
        return ""

    parts = ["## 世界观参考（当前卷相关）"]
    for e in entries:
        parts.append(f"- **[{e['domain']}] {e['name']}**：{e['content'][:250]}")
    return "\n".join(parts)


def _build_pacing_context_v2(repo, novel_name, volume, chapter_num):
    """Get pacing guidance for this chapter."""
    row = repo.get_pacing(novel_name, volume, chapter_num)
    if not row:
        return ""
    return f"""## 节奏/情感指引
- 本章节奏：{row['pace_type']}
- 强度：{row['intensity']}/10
- 情感目标：{row.get('emotion_target') or '未设定'}
- 字数范围：{row.get('word_budget_min', 2500)}-{row.get('word_budget_max', 3500)}字"""


def _build_revelation_context_v2(repo, novel_name, volume):
    """Info to reveal in this volume."""
    rows = repo.get_revelations_for_volume(novel_name, volume)
    if not rows:
        return ""
    parts = ["## 信息释放约束（本章可透露以下信息）"]
    for r in rows:
        parts.append(f"- [{r['info_type']}] {r['name']}：{r['content'][:200]}")
    return "\n".join(parts)


def _build_plot_arc_context_v2(repo, novel_name, volume):
    """Active plot arcs for this volume."""
    rows = repo.get_plot_arcs_for_volume(novel_name, volume)
    if not rows:
        return ""
    parts = ["## 当前剧情弧线"]
    for r in rows:
        parts.append(f"- **[{r['type']}] {r['name']}**：{r['summary'][:300]}")
    return "\n".join(parts)


def _build_memory_context_v2(repo, novel_name, volume, chapter_num):
    """RAG memory — best-effort, volume-scoped."""
    try:
        from memory_layer import retrieve_memory
        chars = repo.list_characters(novel_name)
        char_names = [c.get("name", "") for c in chars if c.get("name")] if chars else ["主角"]

        mem_ctx = retrieve_memory(
            novel_name=novel_name, volume=volume, chapter_num=chapter_num,
            character_names=char_names, outline_section="",
            total_token_budget=2000,
        )
        return mem_ctx.context_text if mem_ctx else ""
    except Exception:
        return ""


def _build_state_context_v2(repo, novel_name, volume):
    """VOLUME-SCOPED state evolution: only recent character events, no full profiles."""
    events = repo.get_recent_character_events(novel_name, volume, max_chapters=15)
    if not events:
        # Fallback: recent chapters summary
        recent = repo.get_recent_chapters(novel_name, limit=10)
        if not recent:
            return ""

        parts = ["## 📊 近期状态摘要"]
        parts.append("\n### 近期章节")
        for r in recent:
            parts.append(f"  - {r['chapter_ref']}: {r.get('title', r['chapter_ref'])} ({r.get('word_count', 0)}字)")

        # Characters with current position info only
        chars = repo.list_characters(novel_name)
        active = [c for c in chars if c.get("current_vol", 0) >= max(1, volume - 2) and c.get("current_vol", 0) <= volume]
        if active:
            parts.append("\n### 角色当前位置")
            for c in active[:5]:
                parts.append(f"  - **{c['name']}** ({c.get('role', '?')}): "
                           f"第{c.get('current_vol', '?')}卷第{c.get('current_ch', '?')}章 "
                           f"— {c.get('current_status', '')[:80]}")
        return "\n".join(parts)

    # Event-based summary
    parts = ["## 📊 角色状态变化（近期）"]
    for ev in events:
        parts.append(f"  - 第{ev['vol']}卷第{ev['ch']}章: [{ev['event_type']}] {ev['description'][:120]}")
    return "\n".join(parts)


def _build_style_context_simple(style, instructions, novel_name):
    """Simplified style context (no file reads for style fingerprints here)."""
    parts = []
    if style:
        parts.append(f"写作风格：{style}")
    if instructions:
        parts.append(f"用户指示：{instructions}")
    return "\n".join(parts)

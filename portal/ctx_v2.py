"""
Volume-Scoped Context Builder — drop-in replacement for context_builder.build_context.

Key fixes:
1. Layer 3 (Characters): Only characters active in current volume, strips future arcs/endings
2. Layer 4 (Foreshadowing): 3-tier system (due_now/overdue/recent) scoped by volume
3. Layer 5 (World Building): Cap at 5 entries (was 10), tighter volume scoping
4. Layer 10 (State Evolution): Only recent chapter events, no full character profiles

Usage: In run_v2.py, this replaces context_builder.build_context.
"""

import os, sys, time, threading, re as _re

sys.path.insert(0, os.path.dirname(__file__))
from token_budget import TokenBudget
from token_utils import count_tokens, truncate_to_tokens
from prompt_manager import get_prompt_manager
from repository import get_repo

_CONTEXT_CACHE_V2 = {}
_CONTEXT_CACHE_V2_TTL = 60
_CONTEXT_CACHE_V2_MAX = 100
_CONTEXT_CACHE_V2_LOCK = threading.Lock()


def _core_instructions():
    pm = get_prompt_manager()
    return pm.render_or_default("core_instructions",
        "你是一个专业的长篇网文写作Agent。请严格按照项目设定和大纲写出高质量的小说章节。\n\n"
        "## 脚本强制约束\n- 每章不少于2500字\n- 禁止\"不是...而是...\"二元对照句式\n"
        "- 禁止连续简单判断句超过2句\n- 必须严格遵循大纲/卷纲/危机要求\n"
        "- 伏笔管理：如果系统提示有待填坑伏笔，必须在本章推进或解释\n"
        "- 必须有明确的章节功能和悬念/钩子结尾\n"
        "- 请输出完整的章节正文，以\"# 章节标题\"开头。\n")


def build_context(params):
    """Volume-scoped context builder — replaces context_builder.build_context."""
    novel_name = params.get("name", "")
    volume = params.get("volume", 1)
    if isinstance(volume, str):
        volume = int(volume.split("-")[1]) if volume.startswith("vol-") else int(volume)
    chapter_num = int(params.get("chapter_num", 1))
    style = params.get("style", "")
    instructions = params.get("instructions", "")
    max_tokens = int(params.get("max_tokens", 12000))

    cache_key = f"{novel_name}|{volume}|{chapter_num}|{style}|{instructions}|v2"
    now = time.time()
    with _CONTEXT_CACHE_V2_LOCK:
        if cache_key in _CONTEXT_CACHE_V2:
            ct, cr = _CONTEXT_CACHE_V2[cache_key]
            if now - ct < _CONTEXT_CACHE_V2_TTL:
                return cr

    repo = get_repo()
    budget = TokenBudget(max_tokens=max_tokens)
    layers = []

    # L0: Core
    core = _core_instructions()
    layers.append({"name": "核心指令", "content": core, "tokens_used": budget.allocate("核心指令", count_tokens(core))})

    # L1: Project meta
    novel = repo.get_novel(novel_name)
    meta = f"## 项目信息\n- 书名：{novel.get('title', novel_name)}\n- 类型：{novel.get('genre', '未设置')}\n- 目标篇幅：{novel.get('word_goal', '未设置')}" if novel else ""
    layers.append({"name": "项目元信息", "content": truncate_to_tokens(meta, 300), "tokens_used": budget.allocate("项目元信息", min(count_tokens(meta), 300))})

    # L2: Chapter context (outline + danger + prev chapter)
    ch_ctx = _chapter_ctx(novel_name, volume, chapter_num, repo)
    layers.append({"name": "章节上下文", "content": truncate_to_tokens(ch_ctx, 800), "tokens_used": budget.allocate("章节上下文", min(count_tokens(ch_ctx), 800))})

    # L3: Characters — VOLUME SCOPED
    chars = _char_ctx(repo, novel_name, volume)
    layers.append({"name": "角色上下文", "content": truncate_to_tokens(chars, 1500), "tokens_used": budget.allocate("角色上下文", min(count_tokens(chars), 1500))})

    # L4: Foreshadowing — 3-TIER VOLUME SCOPED
    fs = _fs_ctx(repo, novel_name, volume)
    layers.append({"name": "伏笔待办", "content": truncate_to_tokens(fs, 1000), "tokens_used": budget.allocate("伏笔待办", min(count_tokens(fs), 1000))})

    # L5: World building — capped at 5
    wb = _wb_ctx(repo, novel_name, volume)
    layers.append({"name": "世界观", "content": truncate_to_tokens(wb, 1000), "tokens_used": budget.allocate("世界观", min(count_tokens(wb), 1000))})

    # L6: Pacing
    pace = _pace_ctx(repo, novel_name, volume, chapter_num)
    layers.append({"name": "节奏情感", "content": truncate_to_tokens(pace, 500), "tokens_used": budget.allocate("节奏情感", min(count_tokens(pace), 500))})

    # L7: Revelation
    rev = _rev_ctx(repo, novel_name, volume)
    layers.append({"name": "信息释放", "content": truncate_to_tokens(rev, 500), "tokens_used": budget.allocate("信息释放", min(count_tokens(rev), 500))})

    # L8: Plot arcs — volume-range filtered
    arc = _arc_ctx(repo, novel_name, volume)
    layers.append({"name": "剧情弧线", "content": truncate_to_tokens(arc, 800), "tokens_used": budget.allocate("剧情弧线", min(count_tokens(arc), 800))})

    # L9: RAG memory (best-effort)
    mem = _mem_ctx(repo, novel_name, volume, chapter_num)
    layers.append({"name": "RAG记忆检索", "content": truncate_to_tokens(mem, 2000), "tokens_used": budget.allocate("RAG记忆检索", min(count_tokens(mem), 2000))})

    # L10: State evolution — VOLUME SCOPED
    state = _state_ctx(repo, novel_name, volume)
    layers.append({"name": "状态演化", "content": truncate_to_tokens(state, 1000), "tokens_used": budget.allocate("状态演化", min(count_tokens(state), 1000))})

    # L11: Style
    sty = ""
    if style:
        sty += f"写作风格：{style}\n"
    if instructions:
        sty += f"用户指示：{instructions}"
    layers.append({"name": "写作风格", "content": truncate_to_tokens(sty, 500), "tokens_used": budget.allocate("写作风格", min(count_tokens(sty), 500))})

    # Assemble
    prompt_parts = [l["content"] for l in layers if l["content"].strip()]
    pm = get_prompt_manager()
    footer = pm.render("chapter_context_footer", {"volume": volume, "chapter_num": chapter_num,
                                                    "style": style, "instructions": instructions})
    if not footer:
        footer = f"\n当前卷：第{volume}卷 第{chapter_num}章\n"
        if style: footer += f"风格：{style}\n"
        if instructions: footer += f"用户指示：{instructions}\n"
    prompt_parts.append(footer)

    system_prompt = "\n\n".join(prompt_parts)
    actual_total = count_tokens(system_prompt)

    result = {"system_prompt": system_prompt, "layers": layers,
              "total_tokens": actual_total, "max_tokens": budget.max_tokens}

    with _CONTEXT_CACHE_V2_LOCK:
        _CONTEXT_CACHE_V2[cache_key] = (now, result)
        if len(_CONTEXT_CACHE_V2) > _CONTEXT_CACHE_V2_MAX:
            oldest = min(_CONTEXT_CACHE_V2, key=lambda k: _CONTEXT_CACHE_V2[k][0])
            del _CONTEXT_CACHE_V2[oldest]
    return result


# ── Layer Builders ─────────────────────────────────────────────────────

def _chapter_ctx(novel_name, volume, chapter_num, repo):
    parts = []
    vol_str = f"vol-{volume:02d}"

    # Try YAML outline
    outline_text = _yaml_outline(novel_name, volume, chapter_num)
    if outline_text:
        parts.append(outline_text)
    else:
        outline = repo.get_outline(novel_name, vol_str)
        if outline:
            content = outline.get("content", "")
            ch_p = str(chapter_num).zfill(3)
            m = _re.search(f'第\\s*({ch_p}|{str(chapter_num).zfill(4)}|{chapter_num})\\s*章', content)
            if m:
                s = m.start()
                nxt = _re.search(r'第\s*\d+\s*章', content[s+10:])
                e = s + 10 + nxt.start() if nxt else min(s + 1500, len(content))
                parts.append(f"## 卷纲要求\n{content[s:e]}")
            else:
                parts.append(f"## 本卷大纲\n{content[:1500]}")

    danger = repo.get_danger_issue(novel_name, vol_str, chapter_num)
    if danger:
        parts.append(f"## 本章危机/关卡\n{danger['content'][:800]}")

    if chapter_num > 1:
        prev = repo.get_chapter_by_num(novel_name, vol_str, chapter_num - 1)
        if prev:
            parts.append(f"## 上一章结尾（衔接）\n{prev['content'][-2000:]}")

    return "\n\n".join(parts)


def _yaml_outline(novel_name, volume, chapter_num):
    novel_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "novels", novel_name)
    yc = None
    for ext in ('.yaml', '.yml'):
        yp = os.path.join(novel_dir, "outline", f"vol-{volume:02d}-chapters{ext}")
        if os.path.exists(yp):
            try:
                with open(yp, 'r', encoding='utf-8') as f:
                    yc = f.read()
                break
            except Exception:
                continue
    if not yc:
        return ""
    try:
        import yaml
        data = yaml.safe_load(yc)
    except Exception:
        try:
            import json as _j
            data = _j.loads(yc)
        except Exception:
            return ""
    if not data or not isinstance(data, dict):
        return ""

    chapters = data.get('chapters', [])
    ch_data = None
    for ch in chapters:
        if ch.get('number') == chapter_num:
            ch_data = ch; break

    if not ch_data:
        lines = [f"## 第{volume}卷大纲"]
        if data.get('volume_name'): lines.append(f"卷名：{data['volume_name']}")
        return "\n".join(lines)

    lines = [f"## 第{volume}卷第{chapter_num}章 写作指令"]
    if data.get('volume_name'): lines.append(f"本卷：{data['volume_name']}")
    if ch_data.get('title'): lines.append(f"### 章名：{ch_data['title']}")
    func = ch_data.get('function', [])
    if isinstance(func, str): func = [func]
    if func:
        lines.append("### 本章功能（必须实现）")
        for f in func: lines.append(f"- {f}")
    if ch_data.get('core_events'):
        lines.append("### 核心事件（必须包含）")
        evts = ch_data['core_events']
        if isinstance(evts, list):
            for e in evts: lines.append(f"- {e}")
        else:
            lines.append(f"- {evts}")
    if ch_data.get('foreshadowing'):
        fs = ch_data['foreshadowing']
        if isinstance(fs, list):
            lines.append("### 本章需推进的伏笔")
            for f in fs: lines.append(f"- {f}")
        else:
            lines.append(f"### 本章需推进的伏笔\n- {fs}")
    if ch_data.get('ending_hook'): lines.append(f"### 结尾牵引\n{ch_data['ending_hook']}")
    if data.get('rhythm_rules'):
        rr = data['rhythm_rules']
        if chapter_num in rr.get('danger_scenes', []):
            lines.append("\n⚠️ 本章为**高压章节**——必须写出可见危机、临界心理、主角被牵入过程")
        if chapter_num in rr.get('major_crises', []):
            lines.append("\n🔴 本章为**重大危机章**——需要完整的危机爆发→应对→结果闭环")
    if ch_data.get('style_hint'): lines.append(f"\n风格提示：{ch_data['style_hint']}")
    return "\n".join(lines)


def _char_ctx(repo, novel_name, volume):
    """VOLUME-SCOPED: Only active chars, never include future arcs/endings."""
    chars = repo.list_characters_active_in_volume(novel_name, volume)
    if not chars:
        return ""
    parts = ["## 角色档案（当前卷活跃角色）"]
    for i, c in enumerate(chars):
        if i >= 5: break
        info = f"### {c['name']} ({c.get('role', '?')})"
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
        # NEVER include: ending, arc, lifeline (future spoilers)
        parts.append(info)
    return "\n\n".join(parts)


def _fs_ctx(repo, novel_name, volume):
    """3-TIER foreshadowing: due_now / overdue / recent."""
    data = repo.get_foreshadowing_for_volume(novel_name, volume)
    if not data["due_now"] and not data["overdue"] and not data["recent"]:
        return ""
    parts = []
    if data["due_now"]:
        parts.append("## 🔴 伏笔必须解决（本章目标卷=当前卷）")
        for f in data["due_now"]:
            parts.append(f"- **{f['name']}** ({f.get('category', '剧情')})")
            if f.get("description"): parts.append(f"  {f['description'][:200]}")
    if data["overdue"]:
        parts.append("## ⚠️ 伏笔逾期未填坑")
        for f in data["overdue"][:3]:
            parts.append(f"- **{f['name']}** (原定第{f.get('target_vol', '?')}卷)")
            if f.get("description"): parts.append(f"  {f['description'][:150]}")
    if data["recent"]:
        parts.append("## 🟡 近期埋入伏笔（保持意识）")
        for f in data["recent"][:2]:
            parts.append(f"- **{f['name']}** (第{f.get('introduced_vol', '?')}卷埋入)")
    return "\n".join(parts)


def _wb_ctx(repo, novel_name, volume):
    entries = repo.get_world_building_for_volume(novel_name, volume, limit=5)
    if not entries: return ""
    parts = ["## 世界观参考（当前卷相关）"]
    for e in entries:
        parts.append(f"- **[{e['domain']}] {e['name']}**：{e['content'][:250]}")
    return "\n".join(parts)


def _pace_ctx(repo, novel_name, volume, chapter_num):
    row = repo.get_pacing(novel_name, volume, chapter_num)
    if not row: return ""
    return (f"## 节奏/情感指引\n- 本章节奏：{row['pace_type']}\n"
            f"- 强度：{row['intensity']}/10\n- 情感目标：{row.get('emotion_target') or '未设定'}\n"
            f"- 字数范围：{row.get('word_budget_min', 2500)}-{row.get('word_budget_max', 3500)}字")


def _rev_ctx(repo, novel_name, volume):
    rows = repo.get_revelations_for_volume(novel_name, volume)
    if not rows: return ""
    parts = ["## 信息释放约束（本章可透露以下信息）"]
    for r in rows:
        parts.append(f"- [{r['info_type']}] {r['name']}：{r['content'][:200]}")
    return "\n".join(parts)


def _arc_ctx(repo, novel_name, volume):
    rows = repo.get_plot_arcs_for_volume(novel_name, volume)
    if not rows: return ""
    parts = ["## 当前剧情弧线"]
    for r in rows:
        parts.append(f"- **[{r['type']}] {r['name']}**：{r['summary'][:300]}")
    return "\n".join(parts)


def _mem_ctx(repo, novel_name, volume, chapter_num):
    try:
        from memory_layer import retrieve_memory
        chars = repo.list_characters(novel_name)
        names = [c.get("name", "") for c in chars if c.get("name")] if chars else ["主角"]
        mc = retrieve_memory(novel_name=novel_name, volume=volume, chapter_num=chapter_num,
                             character_names=names, outline_section="", total_token_budget=2000)
        return mc.context_text if mc else ""
    except Exception:
        return ""


def _state_ctx(repo, novel_name, volume):
    """VOLUME-SCOPED: Only recent events, no full character profiles."""
    events = repo.get_recent_character_events(novel_name, volume, max_chapters=15)
    if events:
        parts = ["## 📊 角色状态变化（近期）"]
        for ev in events:
            parts.append(f"  - 第{ev['vol']}卷第{ev['ch']}章: [{ev['event_type']}] {ev['description'][:120]}")
        return "\n".join(parts)

    # Fallback: recent chapter summaries
    recent = repo.get_recent_chapters(novel_name, limit=10)
    if not recent:
        return ""
    parts = ["## 📊 近期状态摘要"]
    parts.append("\n### 近期章节")
    for r in recent:
        parts.append(f"  - {r['chapter_ref']}: {r.get('title', r['chapter_ref'])} ({r.get('word_count', 0)}字)")

    chars = repo.list_characters(novel_name)
    active = [c for c in chars if c.get("current_vol", 0) >= max(1, volume - 2)
              and c.get("current_vol", 0) <= volume]
    if active:
        parts.append("\n### 角色当前位置")
        for c in active[:5]:
            parts.append(f"  - **{c['name']}** ({c.get('role', '?')}): "
                       f"第{c.get('current_vol', '?')}卷第{c.get('current_ch', '?')}章 "
                       f"— {c.get('current_status', '')[:80]}")
    return "\n".join(parts)

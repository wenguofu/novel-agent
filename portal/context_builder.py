"""
Context Builder — Server-side 9-layer system prompt assembly.
Replaces the client-side _buildSystemPrompt with DB-driven on-demand loading.

Architecture:
  Layer 0: Core Instructions (500 tok)
  Layer 1: Project Meta (300 tok)
  Layer 2: Chapter Context — outline + danger_issue + prev ending (800 tok)
  Layer 3: Characters (2000 tok) — vector search top-3
  Layer 4: Foreshadowing (1500 tok) — DB filter by target_vol
  Layer 5: World Building (1500 tok) — vector search top-5
  Layer 6: Pacing/Emotion (500 tok) — DB filter by vol/ch
  Layer 7: Revelation (500 tok) — DB filter by reveal_vol
  Layer 8: Plot Arcs (1000 tok) — DB filter by vol range
  Layer 9: Style (500 tok) — user config
  Total max: 10000 tokens
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from token_budget import TokenBudget
import content_db as db


# ═══════════════════════════════════════════════════════════════════════
# Layer Definitions
# ═══════════════════════════════════════════════════════════════════════

CORE_INSTRUCTIONS = """你是一个专业的长篇网文写作Agent。你的任务是**严格按照项目设定和大纲**写出高质量的小说章节。

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

    # LAYER 0: Core Instructions (always included)
    core_tokens = _count_tokens(CORE_INSTRUCTIONS)
    budget.allocate("核心指令", core_tokens)
    layers.append({"name": "核心指令", "content": CORE_INSTRUCTIONS, "tokens_used": core_tokens})

    # LAYER 1: Project Meta
    meta_text = _build_project_meta(novel_name)
    meta_tokens = _count_tokens(meta_text)
    allocated = budget.allocate("项目元信息", min(meta_tokens, 300))
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

    # LAYER 4: Foreshadowing (DB query)
    fs_text = _build_foreshadowing_context(novel_name, volume)
    fs_tokens = _count_tokens(fs_text)
    allocated = budget.allocate("伏笔待办", min(fs_tokens, 1500))
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
    """Extract project metadata from novels table"""
    conn = db.get_db()
    novel = conn.execute("SELECT title, genre, subgenre, word_goal FROM novels WHERE name=?",
                         (novel_name,)).fetchone()
    conn.close()
    if not novel:
        return ""
    return f"""## 项目信息
- 书名：{novel['title'] or novel_name}
- 类型：{novel['genre'] or '未设置'}
- 目标篇幅：{novel['word_goal'] or '未设置'}"""


def _build_chapter_context(novel_name, volume, chapter_num):
    """Get outline section + danger issue + previous chapter ending"""
    parts = []

    # Outline section
    outlines = db.get_db().execute(
        "SELECT content FROM outlines WHERE novel_id=(SELECT id FROM novels WHERE name=?) AND volume=?",
        (novel_name, f"vol-{volume:02d}")).fetchone()
    if outlines:
        content = outlines["content"]
        # Try to extract relevant chapter section
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
    danger = db.get_db().execute(
        """SELECT content FROM danger_issues WHERE novel_id=(SELECT id FROM novels WHERE name=?)
           AND volume=? AND chapter_num=?""",
        (novel_name, f"vol-{volume:02d}", chapter_num)).fetchone()
    if danger:
        parts.append(f"## 本章危机/关卡\n{danger['content'][:800]}")

    # Previous chapter ending (for continuity)
    if chapter_num > 1:
        prev_ch = db.get_db().execute(
            """SELECT content FROM chapters WHERE novel_id=(SELECT id FROM novels WHERE name=?)
               AND volume=? AND chapter_num=?""",
            (novel_name, f"vol-{volume:02d}", chapter_num - 1)).fetchone()
        if prev_ch:
            parts.append(f"## 上一章结尾（衔接）\n{prev_ch['content'][-2000:]}")

    return "\n\n".join(parts)


def _build_character_context(novel_name, volume, chapter_num):
    """Get relevant character info from DB (characters appearing in this volume)"""
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
    return "\n\n".join(parts)


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
    """Get relevant world building entries"""
    conn = db.get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return ""
    nid = novel["id"]

    # Get entries relevant to current volume range
    rows = conn.execute(
        """SELECT domain, name, content FROM world_building
           WHERE novel_id=? AND (related_vol=0 OR related_vol BETWEEN ? AND ?)
           LIMIT 10""",
        (nid, max(1, volume - 1), volume + 1)).fetchall()
    conn.close()

    if not rows:
        return ""

    parts = ["## 世界观参考"]
    for r in rows:
        parts.append(f"- **[{r['domain']}] {r['name']}**：{r['content'][:300]}")
    return "\n".join(parts)


def _build_pacing_context(novel_name, volume, chapter_num):
    """Get pacing guidance for this chapter"""
    conn = db.get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return ""
    nid = novel["id"]

    row = conn.execute(
        """SELECT pace_type, intensity, emotion_target, word_budget_min, word_budget_max
           FROM pacing_control
           WHERE novel_id=? AND volume=? AND chapter_start<=? AND chapter_end>=?
           LIMIT 1""",
        (nid, volume, chapter_num, chapter_num)).fetchone()
    conn.close()

    if not row:
        return ""

    return f"""## 节奏/情感指引
- 本章节奏：{row['pace_type']}
- 强度：{row['intensity']}/10
- 情感目标：{row['emotion_target'] or '未设定'}
- 字数范围：{row['word_budget_min']}-{row['word_budget_max']}字"""


def _build_revelation_context(novel_name, volume):
    """Get info that should be revealed in this volume"""
    conn = db.get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return ""
    nid = novel["id"]

    rows = conn.execute(
        """SELECT name, info_type, content FROM revelation_schedule
           WHERE novel_id=? AND reveal_volume=? LIMIT 5""",
        (nid, volume)).fetchall()
    conn.close()

    if not rows:
        return ""

    parts = ["## 信息释放约束（本章可透露以下信息）"]
    for r in rows:
        parts.append(f"- [{r['info_type']}] {r['name']}：{r['content'][:200]}")
    return "\n".join(parts)


def _build_plot_arc_context(novel_name, volume):
    """Get active plot arcs for this volume"""
    conn = db.get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return ""
    nid = novel["id"]

    rows = conn.execute(
        """SELECT name, type, summary FROM plot_arcs
           WHERE novel_id=? AND status='active'
           AND volume_start<=? AND volume_end>=?
           LIMIT 5""",
        (nid, volume, volume)).fetchall()
    conn.close()

    if not rows:
        return ""

    parts = ["## 当前剧情弧线"]
    for r in rows:
        parts.append(f"- **[{r['type']}] {r['name']}**：{r['summary'][:300]}")
    return "\n".join(parts)


def _build_style_context(style, instructions, novel_name):
    """Build style guidance"""
    parts = []
    if style:
        parts.append(f"写作风格：{style}")
    if instructions:
        parts.append(f"用户指示：{instructions}")
    return "\n".join(parts)


def get_context_stats(novel_name, volume, chapter_num):
    """Return available context statistics for a given chapter"""
    layers = []
    conn = db.get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    nid = novel["id"] if novel else None
    conn.close()

    if nid:
        conn = db.get_db()
        # Characters
        char_count = len(db.get_characters(novel_name))
        layers.append({"name": "角色", "available": char_count})

        # Foreshadowing
        fs_count = len(db.get_unresolved_foreshadowing(novel_name, current_vol=volume))
        layers.append({"name": "待填伏笔", "available": fs_count})

        # World building
        wb_count = conn.execute(
            "SELECT COUNT(*) FROM world_building WHERE novel_id=?", (nid,)).fetchone()[0]
        layers.append({"name": "世界观条目", "available": wb_count})

        # Plot arcs
        pa_count = conn.execute(
            "SELECT COUNT(*) FROM plot_arcs WHERE novel_id=?", (nid,)).fetchone()[0]
        layers.append({"name": "剧情弧线", "available": pa_count})

        # Pacing
        pc_count = conn.execute(
            "SELECT COUNT(*) FROM pacing_control WHERE novel_id=?", (nid,)).fetchone()[0]
        layers.append({"name": "节奏条目", "available": pc_count})

        # Revelation
        rs_count = conn.execute(
            "SELECT COUNT(*) FROM revelation_schedule WHERE novel_id=?", (nid,)).fetchone()[0]
        layers.append({"name": "信息释放", "available": rs_count})

        conn.close()

    return {"layers": layers, "novel": novel_name, "volume": volume, "chapter": chapter_num}

#!/usr/bin/env python3
"""
sync_novel_files.py

Reads all novel metadata files and syncs them into content_db.

Usage:
  python sync_novel_files.py <novel_name> [vol_ref]

Example:
  python sync_novel_files.py "大强成神啦"
  python sync_novel_files.py "大强成神啦" vol-01
"""
import sys, os, re, json

NOVEL_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(NOVEL_AGENT_ROOT, "portal"))
from content_db import upsert_danger_issue, get_danger_issues, upsert_story_tracking

# ─── Danger Issues ───────────────────────────────────────────────────────────

def parse_danger_issue(filepath):
    """Parse a danger_issue_XXX.md file into a dict."""
    import re
    content = open(filepath, encoding='utf-8').read()

    # danger_level: "⚠️ 低（氛围压迫型）" → "low"
    lvl_match = re.search(r'⚠️\s*([低中高])', content)
    level_map = {'低': 'low', '中': 'medium', '高': 'high'}
    danger_level = level_map.get(lvl_match.group(1), 'low') if lvl_match else 'low'

    # core_danger: second line of header block
    core_match = re.search(r'核心危险：(.+)', content)
    core_danger = core_match.group(1).strip() if core_match else ''

    # rhythm_data: parse table | 时间段 | 情节 | 张力 |
    # Fix: capture full row content (between outer pipes), then split on '|'.
    # The previous regex `\|(.+?)\|` captured a single cell, not a full row,
    # so row.split('|') produced only one element and the parser silently dropped all rows.
    rhythm_data = {}
    # Tension level → numeric. Cells may carry annotations, e.g. "高（章末钩子）".
    tension_levels = [('低', 1), ('中', 2), ('中高', 3), ('高', 4)]
    full_rows = re.findall(r'^\|(.+)\|$', content, re.MULTILINE)
    for full_row in full_rows:
        cols = [c.strip() for c in full_row.split('|')]
        if len(cols) >= 3 and re.match(r'\d{2}:\d{2}', cols[0]):
            key = cols[0]
            t_raw = cols[-1].strip()
            # Match the LONGEST level keyword that is a prefix of t_raw.
            # "中高" must win over "中" and "高"; "高" wins over "中" alone.
            # Using `in` would falsely match "高" inside "中高", so we use
            # a longest-prefix match instead.
            t_level = 0
            best_len = 0
            for keyword, level in tension_levels:
                if t_raw.startswith(keyword) and len(keyword) > best_len:
                    t_level = level
                    best_len = len(keyword)
            rhythm_data[key] = {'scene': cols[1] if len(cols) > 1 else '', 'tension': t_level}

    # foreshadowing_data: parse table | 伏笔ID | 内容 | 揭示时机 |
    # Fix: MD cells have a space after each `|` (e.g. `| FP001 | 描述 | 揭示 |`).
    # The previous regex `^\|(FP\d+)\|...` required `|FP001` with no space, so 0 rows matched.
    foreshadowing_data = []
    fp_rows = re.findall(
        r'^\|\s*(FP\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
        content,
        re.MULTILINE,
    )
    for fp_id, desc, reveal in fp_rows:
        foreshadowing_data.append({'id': fp_id, 'description': desc.strip(), 'reveal_at': reveal.strip()})

    return {
        'danger_level': danger_level,
        'core_danger': core_danger,
        'content': content,
        'rhythm_data': rhythm_data,
        'foreshadowing_data': foreshadowing_data,
    }


def sync_danger_issues(novel_name, vol_ref='vol-01'):
    """Sync all danger_issue files for a volume."""
    import glob
    base = os.path.join(NOVEL_AGENT_ROOT, "novels", novel_name, "outline", f"danger_issue_{vol_ref}")
    if not os.path.isdir(base):
        print(f"No danger_issue dir: {base}")
        return

    files = sorted(glob.glob(os.path.join(base, "danger_issue_*.md")))
    count = 0
    for fp in files:
        m = re.search(r'danger_issue_(\d+)', os.path.basename(fp))
        if not m:
            continue
        ch_num = int(m.group(1))
        data = parse_danger_issue(fp)
        upsert_danger_issue(novel_name, vol_ref, ch_num, data)
        print(f"  danger_issue {ch_num}: {data['danger_level']} | {data['core_danger'][:30]}")
        count += 1
    print(f"Synced {count} danger_issues for {novel_name} {vol_ref}")


# ─── Story Tracking ──────────────────────────────────────────────────────────

def parse_current_status(filepath):
    """Parse current_status.md into a list of (record_type, key, value) tuples."""
    import re
    content = open(filepath, encoding='utf-8').read()
    records = []

    def add_record(key, value, rec_type='status'):
        # Skip header/separator rows
        if not key or key in ('字段', ':---:', '---', '人物', '序号', '卷数', 'ID'):
            return
        if not value or value in (':---:', '---', ''):
            return
        # Skip rows where JSON value contains header cell values (e.g. "古神", "卷名", "揭示卷")
        if any(h in value for h in ('"古神"', '"卷名"', '"揭示卷"')):
            return
        records.append((rec_type, key, value))

    def get_section(name, content):
        """Extract section up to --- or end of file."""
        m = re.search(rf'## {name}(.+?)(?=\n---\n|\n## |\Z)', content, re.DOTALL)
        return m.group(1) if m else ''

    def parse_table(section, num_cols):
        """Parse markdown table rows, skip separator rows."""
        rows = []
        for row in re.findall(r'^\|(.+?)\|$', section, re.MULTILINE):
            cols = [c.strip() for c in row.split('|')]
            if len(cols) == num_cols and cols[0] not in ('字段', ':---:', '---', ''):
                rows.append(cols)
        return rows

    # Project overview: | 字段 | 内容 |
    sec = get_section('项目总览', content)
    for row in parse_table(sec, 2):
        add_record(row[0], row[1], 'project_overview')

    # Writing progress: | 章节号 | 标题 | 状态 | 字数 | 审稿 |
    sec = get_section('第1卷写作进度', content)
    for row in parse_table(sec, 5):
        ch_ref = row[0]
        if re.match(r'ch-\d+', ch_ref):
            add_record(ch_ref, json.dumps({
                'title': row[1], 'status': row[2],
                'word_count': row[3], 'review': row[4]
            }, ensure_ascii=False), 'writing_progress')

    # Character state: | 人物 | 状态 | 位置 |
    sec = get_section('人物状态', content)
    for row in parse_table(sec, 3):
        add_record(row[0], json.dumps({'state': row[1], 'position': row[2]}, ensure_ascii=False), 'character_state')

    # Volume planning: | 卷数 | 卷名 | 规划状态 | 章数 | 字数目标 | 核心古神 | 系统剧情 | 女主节点 |
    sec = get_section('各卷规划状态', content)
    for row in parse_table(sec, 8):
        add_record(row[0], json.dumps({
            'name': row[1], 'plan_status': row[2], 'chapters': row[3],
            'word_goal': row[4], 'core_god': row[5], 'system_plot': row[6], 'heroine': row[7]
        }, ensure_ascii=False), 'volume_plan')

    # 8-god challenge: | 序号 | 古神 | 真名 | 容器宿主 | 挑战卷数 | 状态 |
    sec = get_section('八神挑战进度', content)
    for row in parse_table(sec, 6):
        add_record(f"god_{row[0]}", json.dumps({
            'god_name': row[1], 'true_name': row[2], 'host': row[3],
            'challenge_vol': row[4], 'status': row[5]
        }, ensure_ascii=False), 'god_challenge')

    # Foreshadowing tracking: | ID | 伏笔 | 首次 | 揭示卷 | 状态 |
    fp_m = re.search(r'## 伏笔追踪（(\d+)条）', content)
    if fp_m:
        sec = get_section(f'伏笔追踪（{fp_m.group(1)}条）', content)
        for row in parse_table(sec, 5):
            add_record(row[0], json.dumps({
                'description': row[1], 'intro_vol': row[2],
                'reveal_vol': row[3], 'status': row[4]
            }, ensure_ascii=False), 'foreshadowing_tracking')

    return records


def sync_current_status(novel_name):
    """Sync current_status.md into story_tracking."""
    path = os.path.join(NOVEL_AGENT_ROOT, "novels", novel_name, "state", "current_status.md")
    if not os.path.exists(path):
        print(f"current_status not found: {path}")
        return

    records = parse_current_status(path)
    print(f"Parsing {len(records)} records from current_status.md")
    for rec_type, key, value in records:
        upsert_story_tracking(novel_name, rec_type, key, value)
        print(f"  [{rec_type}] {key}: {value[:60] if len(value) > 60 else value}")
    print(f"Synced {len(records)} records for {novel_name}")


# ─── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python sync_novel_files.py <novel_name> [vol_ref]")
        sys.exit(1)

    novel_name = sys.argv[1]
    vol_ref = sys.argv[2] if len(sys.argv) > 2 else 'vol-01'

    print(f"\n=== Syncing danger_issues for {novel_name} {vol_ref} ===")
    sync_danger_issues(novel_name, vol_ref)

    print(f"\n=== Syncing current_status for {novel_name} ===")
    sync_current_status(novel_name)

    print("\nDone.")
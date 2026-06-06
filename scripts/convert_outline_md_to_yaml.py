#!/usr/bin/env python3
"""
convert_outline_md_to_yaml.py

Reads a vol-XX-chapters.md file and its companion vol-XX-chapters.yaml (if exists),
merges them (YAML fields override MD-derived fields), saves as .yaml,
and upserts into chapter_outlines DB.

Usage:
  python convert_outline_md_to_yaml.py <novel_name> <vol_ref>

Example:
  python convert_outline_md_to_yaml.py "大强成神啦" vol-01
"""
import sys
import re
import json
import os

NOVEL_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(NOVEL_AGENT_ROOT, "portal"))

from content_db import upsert_chapter_outline, get_chapter_outlines


def parse_md_outline(md_content):
    """Parse a vol-XX-chapters.md file into a list of chapter dicts."""
    # Chinese digit map for chapter number parsing
    CN_MAP = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'零':0}

    def cn_to_int(cn):
        if cn in CN_MAP: return CN_MAP[cn]
        if '十' in cn:
            parts = cn.split('十')
            if len(parts) == 2:
                left = CN_MAP.get(parts[0], 0) if parts[0] else 0
                right = CN_MAP.get(parts[1], 0) if parts[1] else 0
                if parts[0] == '': left = 1
                return left * 10 + right
        return 0

    chapters = []
    # Split into chapter blocks: each starts with #### **
    blocks = re.split(r'(?=#### \*\*)', md_content)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Match chapter header: #### **第N章：标题** or **第N章 标题**
        m = re.match(r'#### \*\*第([一二三四五六七八九十零]+)章[：:]\s*([^*]+)\*\*', block)
        if not m:
            m = re.match(r'#### \*\*第([一二三四五六七八九十零]+)章\s+([^*]+)\*\*', block)
        if not m:
            continue
        ch_num = cn_to_int(m.group(1))
        title = m.group(2).strip()

        # Extract **内容：** lines (may span multiple bullet lines)
        content_lines = []
        in_content = False
        for line in block.split('\n'):
            line = line.rstrip()
            # Start of content block
            if re.match(r'^\*   \*\*内容：\*\*', line):
                in_content = True
                content_lines.append(re.sub(r'^\*   \*\*内容：\*\*', '', line).strip())
            # Continuation lines (bullet with content but no ** marker)
            elif in_content and re.match(r'^\*   ', line) and not re.match(r'^\*   \*\*', line):
                content_lines.append(re.sub(r'^\*   ', '', line).strip())
            else:
                in_content = False
        core_events = ' '.join(content_lines)

        # Extract **钩子：**
        hooks = re.findall(r'^\*   \*\*钩子：\*\*\s*(.+)$', block, re.MULTILINE)
        ending_hook = hooks[0] if hooks else ''

        chapters.append({
            'number': ch_num,
            'title': title,
            'function': [],
            'core_events': core_events,
            'foreshadowing': [],
            'ending_hook': ending_hook,
            'is_danger_scene': False,
            'word_count': 0,
        })
    return chapters


def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_outline_md_to_yaml.py <novel_name> <vol_ref>")
        sys.exit(1)

    novel_name = sys.argv[1]
    vol_ref = sys.argv[2]  # e.g. "vol-01"

    outline_dir = os.path.join(NOVEL_AGENT_ROOT, "novels", novel_name, "outline")
    md_path = os.path.join(outline_dir, f"{vol_ref}-chapters.md")
    yaml_path = os.path.join(outline_dir, f"{vol_ref}-chapters.yaml")

    if not os.path.exists(md_path):
        print(f"MD outline not found: {md_path}")
        sys.exit(1)

    md_content = open(md_path, encoding='utf-8').read()
    chapters = parse_md_outline(md_content)
    print(f"Parsed {len(chapters)} chapters from MD")

    # If companion YAML exists, merge its per-chapter fields
    if os.path.exists(yaml_path):
        import yaml
        yaml_content = open(yaml_path, encoding='utf-8').read()
        yaml_data = yaml.safe_load(yaml_content)
        if yaml_data and 'chapters' in yaml_data:
            yaml_chapters = {ch['number']: ch for ch in yaml_data['chapters']}
            for ch in chapters:
                if ch['number'] in yaml_chapters:
                    yc = yaml_chapters[ch['number']]
                    ch['title'] = yc.get('title', ch['title'])
                    ch['function'] = yc.get('function', [])
                    ch['core_events'] = yc.get('core_events', ch['core_events'])
                    ch['foreshadowing'] = yc.get('foreshadowing', [])
                    ch['ending_hook'] = yc.get('ending_hook', ch['ending_hook'])
                    ch['is_danger_scene'] = yc.get('is_danger_scene', False)
                    ch['word_count'] = yc.get('word_count', 0)
            print("Merged YAML fields into chapters")

    # Save as .yaml
    yaml_output = {
        'volume': int(re.search(r'\d+', vol_ref).group()),
        'volume_name': vol_ref,
        'chapters': chapters,
    }
    with open(yaml_path, 'w', encoding='utf-8') as f:
        import yaml
        yaml.dump(yaml_output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"Saved YAML to: {yaml_path}")

    # Upsert to DB
    existing = get_chapter_outlines(novel_name, vol_ref)
    print(f"Existing DB chapters: {len(existing)}")

    for ch in chapters:
        upsert_chapter_outline(novel_name, vol_ref, ch['number'], ch)
        print(f"  Upserted ch{ch['number']}: {ch['title']}")

    print("Done.")


if __name__ == '__main__':
    main()
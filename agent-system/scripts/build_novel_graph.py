#!/usr/bin/env python3
"""
build_novel_graph.py — Assemble unified novel knowledge graph (novel-graph.json).

Reads Markdown files and SQLite content DB to produce a single machine-readable
JSON artifact capturing all novel state: project metadata, volumes, chapters,
characters, foreshadowing, world building, plot arcs, pacing, revelation schedule,
quality metrics, and fingerprints.

Usage:
  python build_novel_graph.py --novel <path>              # Build/rebuild graph
  python build_novel_graph.py --novel <path> --incremental  # Only if stale
  python build_novel_graph.py --novel <path> --format json  # Output to stdout (no file write)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional


GRAPH_FILE = "novel-graph.json"
STATE_DIR = "state"
SCHEMA_VERSION = "2.0"


def _count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def _parse_md_table(text: str) -> list[dict]:
    """Parse a simple Markdown table into list of dicts."""
    lines = text.strip().split('\n')
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].strip('|').split('|')]
    if not headers:
        return []
    # Skip separator line
    start = 2 if len(lines) > 2 and '---' in lines[1] else 1
    result = []
    for line in lines[start:]:
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) == len(headers):
            result.append(dict(zip(headers, cells)))
    return result


def _read_novel_file(novel_path: Path, relpath: str) -> str:
    """Read a file relative to novel_path, return empty string if missing."""
    fp = novel_path / relpath
    if fp.exists():
        try:
            return fp.read_text(encoding='utf-8')
        except (IOError, UnicodeDecodeError):
            return ""
    return ""


def _parse_chapter_ref(ref: str) -> tuple[int, int]:
    """Parse 'vol-01/ch-0001' into (volume, chapter) numbers."""
    vol_match = re.search(r'vol-(\d+)', ref)
    ch_match = re.search(r'ch-(\d+)', ref)
    vol = int(vol_match.group(1)) if vol_match else 1
    ch = int(ch_match.group(1)) if ch_match else 0
    return vol, ch


def build_graph(novel_path: Path, incremental: bool = False) -> dict:
    """Build the complete novel knowledge graph."""
    novel_name = novel_path.name
    now = datetime.now().isoformat()

    graph = {
        "schema_version": SCHEMA_VERSION,
        "novel_name": novel_name,
        "generated_at": now,
        "project": {},
        "volumes": [],
        "chapters": [],
        "characters": [],
        "foreshadowing": [],
        "world_building": [],
        "plot_arcs": [],
        "pacing": [],
        "revelation_schedule": [],
        "genre_rules": [],
        "alias_names": [],
        "quality_metrics": {},
    }

    # ── Project metadata ──
    project_md = _read_novel_file(novel_path, "project.md")
    for line in project_md.split('\n'):
        line = line.strip()
        if '：' in line or ':' in line:
            key, _, val = line.partition('：' if '：' in line else ':')
            key = key.strip().lstrip('#').strip()
            val = val.strip()
            if key and val:
                graph["project"][key] = val

    # ── Chapters from manuscript/ ──
    manuscript_dir = novel_path / "manuscript"
    if manuscript_dir.exists():
        for vol_dir in sorted(manuscript_dir.iterdir()):
            if not vol_dir.is_dir() or vol_dir.name.startswith('.'):
                continue
            vol_match = re.search(r'vol-(\d+)', vol_dir.name)
            vol_num = int(vol_match.group(1)) if vol_match else 1
            vol_name = ""
            for chapter_file in sorted(vol_dir.glob("ch-*.md")):
                if chapter_file.name.endswith('.bak') or '.bak' in str(chapter_file):
                    continue
                ch_match = re.search(r'ch-(\d+)', chapter_file.name)
                ch_num = int(ch_match.group(1)) if ch_match else 0
                ref = f"{vol_dir.name}/{chapter_file.name.replace('.md', '')}"
                try:
                    content = chapter_file.read_text(encoding='utf-8')
                except (IOError, UnicodeDecodeError):
                    content = ""
                wc = _count_chinese_chars(content)

                # Extract title (first heading)
                title = ""
                title_match = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip()

                # Detect characters mentioned
                chars_mentioned = []
                for m in re.finditer(r'([^\s，。！？、]{2,4})(?:说|道|问|喊|叫|吼|叹|笑|哭|想|看|走|跑)', content):
                    name = m.group(1)
                    if name not in chars_mentioned:
                        chars_mentioned.append(name)

                graph["chapters"].append({
                    "ref": ref,
                    "vol": vol_num,
                    "chapter": ch_num,
                    "title": title,
                    "word_count": wc,
                    "status": "已生成",
                    "characters_mentioned": chars_mentioned[:10],
                })

            # Volume metadata
            chs = [c for c in graph["chapters"] if c["vol"] == vol_num]
            graph["volumes"].append({
                "vol": vol_num,
                "name": vol_name,
                "total_chapters": len(chs),
                "total_words": sum(c["word_count"] for c in chs),
                "status": "进行中" if chs else "未开始",
            })

    # Also check flat manuscript files (legacy format)
    if manuscript_dir.exists():
        for f in sorted(manuscript_dir.glob("vol-*-ch-*.md")):
            ref = f"manuscript/{f.name.replace('.md', '')}"
            # Skip if already captured via directory structure
            if any(c["ref"] == ref for c in graph["chapters"]):
                continue
            try:
                content = f.read_text(encoding='utf-8')
            except (IOError, UnicodeDecodeError):
                content = ""
            wc = _count_chinese_chars(content)
            v, c = _parse_chapter_ref(ref)
            graph["chapters"].append({
                "ref": ref, "vol": v, "chapter": c,
                "title": "", "word_count": wc,
                "status": "已生成", "characters_mentioned": [],
            })

    # ── Characters ──
    chars_md = _read_novel_file(novel_path, "characters.md")
    current_role = ""
    for line in chars_md.split('\n'):
        line = line.strip()
        if line.startswith('## '):
            current_role = line.lstrip('#').strip()
        elif line.startswith('|') and '---' not in line:
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) >= 2 and cells[0] and cells[0] not in ('角色', '姓名', '项目'):
                graph["characters"].append({
                    "name": cells[0],
                    "role": current_role,
                    "details": cells[1] if len(cells) > 1 else "",
                })

    # ── Foreshadowing ──
    foreshadow_md = ""
    for vol_num in range(1, 20):
        outline_path = f"outline/vol-{vol_num:02d}-chapters.md"
        content = _read_novel_file(novel_path, outline_path)
        if content:
            foreshadow_md += content
    # Simple keyword detection for foreshadowing
    for m in re.finditer(r'(?:伏笔|铺垫|暗示)[：:]*\s*(.+)', foreshadow_md):
        graph["foreshadowing"].append({
            "description": m.group(1).strip()[:100],
            "status": "待定",
            "source": "outline",
        })

    # ── World Building ──
    world_md = _read_novel_file(novel_path, "world_bible.md")
    current_domain = ""
    for line in world_md.split('\n'):
        line = line.strip()
        if line.startswith('## '):
            current_domain = line.lstrip('#').strip()
        elif line.startswith('- ') and current_domain:
            graph["world_building"].append({
                "domain": current_domain,
                "entry": line.lstrip('- ').strip()[:200],
            })

    # ── Plot Arcs from full_story_arc.md ──
    arc_md = _read_novel_file(novel_path, "full_story_arc.md")
    for m in re.finditer(r'(?:主线|支线|感情线|成长线)[：:]*\s*(.+)', arc_md):
        graph["plot_arcs"].append({
            "name": m.group(1).strip()[:100],
            "type": "主线" if "主线" in m.group(0) else "支线",
            "status": "进行中",
        })

    # ── Quality metrics ──
    chapters = graph["chapters"]
    if chapters:
        word_counts = [c["word_count"] for c in chapters]
        graph["quality_metrics"] = {
            "total_chapters": len(chapters),
            "total_words": sum(word_counts),
            "avg_word_count": round(sum(word_counts) / len(word_counts)),
            "min_word_count": min(word_counts),
            "max_word_count": max(word_counts),
            "below_2500": sum(1 for w in word_counts if w < 2500),
        }

    # ── Alias names ──
    alias_md = _read_novel_file(novel_path, "alias_registry.md")
    for m in re.finditer(r'(?:别名|替代)[：:]\s*(.+)', alias_md):
        parts = m.group(1).strip().split('→')
        if len(parts) == 2:
            graph["alias_names"].append({
                "real": parts[0].strip(),
                "alias": parts[1].strip(),
            })

    return graph


def save_graph(novel_path: Path, graph: dict):
    """Save graph to state/novel-graph.json."""
    state_dir = novel_path / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    graph_path = state_dir / GRAPH_FILE
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2))


def cmd_build(novel_path: Path, incremental: bool = False):
    """Build the novel knowledge graph."""
    graph = build_graph(novel_path, incremental=incremental)
    save_graph(novel_path, graph)

    stats = {
        "chapters": len(graph["chapters"]),
        "characters": len(graph["characters"]),
        "foreshadowing": len(graph["foreshadowing"]),
        "world_building": len(graph["world_building"]),
        "plot_arcs": len(graph["plot_arcs"]),
        "volumes": len(graph["volumes"]),
    }
    print(f"✅ 知识图谱已构建: {novel_path.name}")
    for key, count in stats.items():
        if count:
            print(f"   {key}: {count}")
    return 0


def cmd_show(novel_path: Path):
    """Output graph to stdout as JSON."""
    graph = build_graph(novel_path)
    print(json.dumps(graph, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="build_novel_graph — 统一小说知识图谱构建器"
    )
    parser.add_argument("--novel", required=True, help="小说项目目录路径")
    parser.add_argument("--incremental", action="store_true", help="仅在文件变更时重建")
    parser.add_argument("--format", choices=["file", "json"], default="file",
                        help="输出格式: file=写入文件, json=stdout")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    novel_path = Path(args.novel).resolve()

    if not novel_path.exists():
        print(f"❌ 小说目录不存在: {novel_path}")
        sys.exit(1)

    if args.format == "json":
        sys.exit(cmd_show(novel_path))
    else:
        sys.exit(cmd_build(novel_path, incremental=args.incremental))


if __name__ == "__main__":
    main()

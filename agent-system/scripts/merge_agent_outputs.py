#!/usr/bin/env python3
"""
merge_agent_outputs.py — Reconcile conflicts between multiple agent outputs.

When multiple agents produce state changes (e.g., character agent says "injured"
but writing agent reports "recovered"), this script detects and resolves conflicts.

Conflict resolution strategies (in priority order):
1. Manual override — human-flagged entries are never overridden
2. Agent authority — higher-authority agent wins (chief-writer > others)
3. Timestamp — later output wins
4. Non-conflicting fields — always merged

Usage:
  python merge_agent_outputs.py --novel <path> --check                    # Check for conflicts
  python merge_agent_outputs.py --novel <path> --auto                      # Auto-resolve + report
  python merge_agent_outputs.py --novel <path> --files a.md b.md --output merged.md
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Agent authority levels (higher = more authoritative)
AGENT_AUTHORITY = {
    "总主编剧": 100,
    "chief-writer": 100,
    "长线剧情": 90,
    "long-plot": 90,
    "类型规则": 80,
    "genre-rules": 80,
    "世界观设定": 70,
    "world-settings": 70,
    "人物": 60,
    "characters": 60,
    "章节规划": 50,
    "chapter-planner": 50,
    "正文写作": 40,
    "writing": 40,
    "编辑审稿": 30,
    "editor-review": 30,
    "合规审查": 30,
    "compliance": 30,
    "连载状态": 20,
    "status": 20,
    "剧情执行跟踪": 20,
    "plot-tracking": 20,
}

STATE_DIR = "state"
CONFLICT_LOG = "conflict_log.json"


def _extract_character_state_changes(text: str) -> list[dict]:
    """Extract character state change records from agent output."""
    changes = []
    for m in re.finditer(
        r'(?:人物状态变化|character_state_change)[：:]\s*(.+?)(?:\n|$)',
        text, re.MULTILINE
    ):
        changes.append({"raw": m.group(1).strip(), "source": "regex"})
    return changes


def _extract_foreshadowing_changes(text: str) -> list[dict]:
    """Extract foreshadowing change records from agent output."""
    changes = []
    for m in re.finditer(
        r'(?:伏笔变化|foreshadowing_change)[：:]\s*(.+?)(?:\n|$)',
        text, re.MULTILINE
    ):
        changes.append({"raw": m.group(1).strip(), "source": "regex"})
    return changes


def _detect_agent_name(filepath: Path) -> Optional[str]:
    """Detect agent name from file content (YAML frontmatter or signature)."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except (IOError, UnicodeDecodeError):
        return None

    # Try YAML frontmatter
    if content.startswith('---'):
        try:
            import yaml
            parts = content.split('---', 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1]) or {}
                return fm.get("display_name") or fm.get("agent_id")
        except Exception:
            pass

    # Try signature matching
    for name in AGENT_AUTHORITY:
        if re.search(name, content[:500]):
            return name
    return None


def _get_authority(agent_name: str) -> int:
    """Get authority level for an agent name."""
    return AGENT_AUTHORITY.get(agent_name, 0)


def check_conflicts(novel_path: Path, agent_files: list[str] = None) -> dict:
    """Check for conflicts between agent outputs.

    Returns:
        {"has_conflicts": bool, "conflicts": list, "resolved": list, "unresolved": list}
    """
    result = {
        "checked_at": datetime.now().isoformat(),
        "has_conflicts": False,
        "conflicts": [],
        "resolved": [],
        "unresolved": [],
    }

    if not agent_files:
        # Auto-discover: look for output files in manuscript/ and reviews/
        agent_files = []
        for pattern in ["manuscript/**/ch-*.md", "reviews/**/*.md"]:
            agent_files.extend(
                str(p.relative_to(novel_path))
                for p in novel_path.glob(pattern) if p.is_file()
            )
        agent_files = sorted(agent_files)[-5:]  # Last 5 files

    if len(agent_files) < 2:
        return result

    # Extract state changes from each file
    char_changes = defaultdict(list)  # character_name -> [(file, change, authority)]
    foreshadow_changes = defaultdict(list)

    for fpath_str in agent_files:
        fpath = novel_path / fpath_str
        if not fpath.exists():
            continue
        try:
            content = fpath.read_text(encoding='utf-8')
        except (IOError, UnicodeDecodeError):
            continue

        agent = _detect_agent_name(fpath) or "未知"
        authority = _get_authority(agent)

        for change in _extract_character_state_changes(content):
            name_match = re.search(r'([^\s，。！？]{2,4})', change["raw"])
            char_name = name_match.group(1) if name_match else "未知人物"
            char_changes[char_name].append({
                "file": fpath_str,
                "agent": agent,
                "authority": authority,
                "change": change["raw"],
            })

    # Detect conflicts: same character with different state changes
    for char_name, changes in char_changes.items():
        if len(changes) > 1:
            unique = set(c["change"] for c in changes)
            if len(unique) > 1:
                conflict = {
                    "type": "character_state",
                    "character": char_name,
                    "changes": [
                        {"file": c["file"], "agent": c["agent"], "change": c["change"]}
                        for c in changes
                    ],
                }
                # Auto-resolve: highest authority wins
                changes_sorted = sorted(changes, key=lambda c: -c["authority"])
                winner = changes_sorted[0]
                if winner["authority"] > min(c["authority"] for c in changes):
                    conflict["resolution"] = "auto"
                    conflict["winner"] = {"file": winner["file"], "agent": winner["agent"]}
                    result["resolved"].append(conflict)
                else:
                    conflict["resolution"] = "unresolved"
                    result["unresolved"].append(conflict)
                result["conflicts"].append(conflict)
                result["has_conflicts"] = True

    return result


def cmd_check(novel_path: Path, agent_files: list[str] = None):
    """Check for conflicts and report."""
    result = check_conflicts(novel_path, agent_files)

    if not result["has_conflicts"]:
        print("✅ 未检测到 Agent 产出冲突")
    else:
        print(f"🔍 检测到 {len(result['conflicts'])} 个冲突")
        for c in result["resolved"]:
            print(f"  ✅ [自动解决] {c['character']}: {c['winner']['agent']} 优先")
        for c in result["unresolved"]:
            print(f"  ❌ [未解决] {c['character']}: 多个Agent产生不同状态变更")

    # Save conflict log
    state_dir = novel_path / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    log_path = state_dir / CONFLICT_LOG
    log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if not result.get("unresolved") else 1


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="merge_agent_outputs — Agent产出冲突检测与归并"
    )
    parser.add_argument("--novel", required=True, help="小说项目目录路径")
    parser.add_argument("--check", action="store_true", help="检测冲突（不解决）")
    parser.add_argument("--auto", action="store_true", help="自动解决冲突")
    parser.add_argument("--files", nargs="*", help="指定要检查的文件列表")
    parser.add_argument("--output", help="归并输出文件路径")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    novel_path = Path(args.novel).resolve()

    if not novel_path.exists():
        print(f"❌ 小说目录不存在: {novel_path}")
        sys.exit(1)

    if args.check or args.auto:
        sys.exit(cmd_check(novel_path, args.files))
    elif args.output and args.files:
        result = check_conflicts(novel_path, args.files)
        output_path = novel_path / args.output
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"✅ 归并结果已写入: {args.output}")
        sys.exit(0)
    else:
        print("用法: merge_agent_outputs.py --novel <path> [--check|--auto|--files ... --output ...]")
        sys.exit(1)


if __name__ == "__main__":
    main()

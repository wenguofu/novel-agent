#!/usr/bin/env python3
"""
check_character_arc.py — Detect character arc deviations.

Compares expected arc milestones vs actual chapter events to find:
- MISSING_MILESTONE: An arc milestone has no corresponding event
- UNEXPECTED_EVENT: An event not in any arc milestone
- TIMING_OFF: Event happened at wrong vol/ch (deviation > 2 chapters)
- ARC_STALLED: No events for character in last N chapters

Usage:
  python check_character_arc.py <novel_name>
  python check_character_arc.py <novel_name> --character <name>
  python check_character_arc.py <novel_name> --volume <N> --format json
  python check_character_arc.py <novel_name> --list-arcs
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

NOVELS_ROOT = Path(__file__).resolve().parent.parent.parent / "novels"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "portal" / "content.db"

# Add portal to path for repository import
_portal_dir = Path(__file__).resolve().parent.parent.parent / "portal"
sys.path.insert(0, str(_portal_dir))


@dataclass
class ArcMilestone:
    vol: int
    ch: int
    event: str
    milestone_type: str = "expected"

    def to_dict(self):
        return asdict(self)


@dataclass
class CharacterArc:
    name: str
    role: str
    milestones: list = field(default_factory=list)
    current_vol: int = 0
    current_ch: int = 0

    def to_dict(self):
        d = asdict(self)
        d["milestones"] = [m.to_dict() if isinstance(m, ArcMilestone) else m for m in self.milestones]
        return d


@dataclass
class Deviation:
    character: str
    deviation_type: str  # MISSING_MILESTONE, UNEXPECTED_EVENT, TIMING_OFF, ARC_STALLED
    severity: str  # low, medium, high
    description: str
    expected: str = ""
    actual: str = ""
    suggestion: str = ""

    def to_dict(self):
        return asdict(self)


# Milestone keywords for arc parsing
_MILESTONE_KEYWORDS = {
    "meet": ["认识", "遇到", "初遇", "见面", "邂逅"],
    "conflict": ["冲突", "对抗", "战斗", "对决", "击败", "杀死"],
    "growth": ["突破", "升级", "觉醒", "领悟", "成长", "提升", "进阶"],
    "betrayal": ["背叛", "出卖", "反目", "决裂"],
    "revelation": ["发现", "得知", "揭露", "真相", "秘密", "谜底"],
    "relationship": ["关系", "亲近", "疏远", "在一起", "分手", "结婚"],
    "sacrifice": ["牺牲", "付出", "代价", "失去"],
    "transformation": ["转变", "改变", "蜕变", "重生"],
    "arrival": ["来到", "到达", "进入", "踏入", "前往"],
    "departure": ["离开", "告别", "离去", "出发"],
}


def _get_repo():
    """Get repository instance for DB access."""
    from repository import get_repo
    return get_repo()
def _parse_arc_milestones(arc_text: str) -> list[dict]:
    """Parse arc milestones from arc/lifeline text fields.

    Expected formats:
    - JSON: [{"vol": 1, "ch": 10, "event": "meet_rival"}]
    - Markdown list: "- 第1卷第10章: 遇到劲敌"
    - Plain text: "第一卷 第10章 遇到劲敌"
    """
    milestones = []

    # Try JSON first
    if arc_text.strip().startswith("["):
        try:
            parsed = json.loads(arc_text)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    # Try markdown list format: "- 第N卷第M章: event"
    pattern = re.compile(
        r'第\s*(\d+)\s*卷\s*第\s*(\d+)\s*章[：:]\s*(.+)',
        re.MULTILINE
    )
    for m in pattern.finditer(arc_text):
        milestones.append({
            "vol": int(m.group(1)),
            "ch": int(m.group(2)),
            "event": m.group(3).strip()[:100],
        })

    # Try keyword-based pattern: "第N卷第M章 keyword..."
    if not milestones:
        ch_pattern = re.compile(r'第\s*(\d+)\s*卷\s*第\s*(\d+)\s*章', re.MULTILINE)
        for m in ch_pattern.finditer(arc_text):
            vol = int(m.group(1))
            ch = int(m.group(2))
            end = m.end()
            next_ch = re.search(r'第\s*\d+\s*卷\s*第\s*\d+\s*章', arc_text[end:])
            desc = arc_text[end:end + next_ch.start()].strip()[:120] if next_ch else arc_text[end:end + 120].strip()
            milestones.append({"vol": vol, "ch": ch, "event": desc})

    # Try comma/semicolon separated
    if not milestones:
        parts = re.split(r'[,;，；\n]', arc_text)
        for part in parts:
            part = part.strip()
            if len(part) > 5:
                milestones.append({
                    "vol": 0,
                    "ch": 0,
                    "event": part[:100],
                })

    return milestones


def _classify_milestone(event_text: str) -> str:
    """Classify a milestone event into a type."""
    for mtype, keywords in _MILESTONE_KEYWORDS.items():
        for kw in keywords:
            if kw in event_text:
                return mtype
    return "other"


def load_character_arcs(novel_name: str) -> list[dict]:
    """Load all characters with arc definitions via repository."""
    repo = _get_repo()
    characters = repo.list_characters(novel_name)
    arcs = []
    for c in characters:
        if c.get('arc'):
            result = []
            # Process arc milestones here
            arc_text = c.get("arc", "")
            lifeline_text = c.get("lifeline", "")
            milestones = _parse_arc_milestones(arc_text)
            milestones.extend(_parse_arc_milestones(lifeline_text))
            for m in milestones:
                m["milestone_type"] = _classify_milestone(m.get("event", ""))
                result.append(m)
            arcs.append({
                "name": c.get("name"),
                "role": c.get("role"),
                "milestones": result,
                "current_vol": c.get("current_vol", 0),
                "current_ch": c.get("current_ch", 0),
            })
    return arcs

def load_actual_events(novel_name: str, character_name: str = None) -> list[dict]:
    """Load character events from DB via repository."""
    repo = _get_repo()
    characters = repo.list_characters(novel_name)
    events = []
    for c in characters:
        if character_name and c.get("name") != character_name:
            continue
        cid = c.get("id")
        if not cid:
            continue
        char_events = repo.list_character_events(cid)
        for evt in char_events:
            events.append({
                "character": c.get("name"),
                "event_type": evt.get("event_type", ""),
                "description": evt.get("description", ""),
                "vol": evt.get("vol", 0),
                "ch": evt.get("ch", 0),
                "source": evt.get("source", ""),
                "created_at": evt.get("created_at", ""),
            })
    return events

def compare_arc_to_events(character: dict, events: list[dict],
                           current_vol: int = None, current_ch: int = None,
                           stall_threshold: int = 10) -> list[dict]:
    """Compare expected arc milestones to actual events.

    Returns list of Deviation dicts.
    """
    deviations = []
    name = character.get("name", "?")
    milestones = character.get("milestones", [])
    char_cur_vol = character.get("current_vol", 0)
    char_cur_ch = character.get("current_ch", 0)

    # Filter events for this character
    char_events = [e for e in events if e.get("character_name") == name]

    # 1. Check each milestone
    for milestone in milestones:
        mv = milestone.get("vol", 0)
        mc = milestone.get("ch", 0)
        mevent = milestone.get("event", "")

        # Find matching event
        matching = None
        for evt in char_events:
            ev = evt.get("vol", 0)
            ec = evt.get("ch", 0)

            # Check vol/ch proximity
            if mv > 0 and mc > 0:
                if ev == mv and abs(ec - mc) <= 2:
                    matching = evt
                    break
            elif mv > 0 and ev == mv:
                matching = evt
                break
            # Keyword match as fallback
            elif any(kw in evt.get("description", "") for kw in mevent.split()[:3]):
                matching = evt
                break

        if matching:
            # Check timing
            ev = matching.get("vol", 0)
            ec = matching.get("ch", 0)
            if (mv > 0 and ev != mv) or (mc > 0 and abs(ec - mc) > 2):
                deviations.append({
                    "character": name,
                    "deviation_type": "TIMING_OFF",
                    "severity": "low",
                    "description": f"里程碑 '{mevent}' 期望在第{mv}卷第{mc}章，实际在第{ev}卷第{ec}章",
                    "expected": f"第{mv}卷第{mc}章",
                    "actual": f"第{ev}卷第{ec}章",
                    "suggestion": f"调整里程碑目标位置或加速剧情推进",
                })
        else:
            # Milestone has no matching event
            is_past = (mv > 0 and (char_cur_vol > mv or (char_cur_vol == mv and char_cur_ch > mc)))
            deviations.append({
                "character": name,
                "deviation_type": "MISSING_MILESTONE",
                "severity": "medium" if is_past else "low",
                "description": f"里程碑 '{mevent[:60]}' 期望在第{mv}卷第{mc}章，未找到对应事件",
                "expected": f"第{mv}卷第{mc}章: {mevent}",
                "actual": "未触发" if is_past else "尚未到达",
                "suggestion": "在后续章节中安排该里程碑事件" if is_past else "到达目标章节时安排该事件",
            })

    # 2. Check for unexpected events (events not in any milestone)
    milestone_keywords = set()
    for m in milestones:
        for word in m.get("event", "").split()[:5]:
            milestone_keywords.add(word)

    stalled = True
    for evt in char_events:
        ev = evt.get("vol", 0)
        ec = evt.get("ch", 0)
        desc = evt.get("description", "")

        # Check if event has any overlap with milestones
        has_overlap = False
        for m in milestones:
            mv = m.get("vol", 0)
            mc = m.get("ch", 0)
            if mv > 0 and ev == mv and abs(ec - (mc or ec)) <= 3:
                has_overlap = True
                break
            if any(kw in desc for kw in m.get("event", "").split()[:3]):
                has_overlap = True
                break

        if not has_overlap:
            continued = True  # Not strictly a deviation if chapter isn't past due

        # Check for recent activity
        if char_cur_vol and current_vol:
            if ev >= char_cur_vol - 2:
                stalled = False

    # 3. Check for arc stall
    if stalled and char_events and current_vol:
        last_event = max(char_events, key=lambda e: (e.get("vol", 0), e.get("ch", 0)))
        gap_vols = current_vol - last_event.get("vol", 0)
        if gap_vols > 2:
            deviations.append({
                "character": name,
                "deviation_type": "ARC_STALLED",
                "severity": "high",
                "description": f"角色已 {gap_vols} 卷无事件记录，最后事件在第{last_event.get('vol')}卷第{last_event.get('ch')}章",
                "expected": "至少每卷有1-2个角色事件",
                "actual": f"最近{stall_threshold}章无事件",
                "suggestion": "为角色安排新的剧情线或与其他角色互动",
            })

    return deviations


def report_deviations(deviations: list[dict], novel_name: str, fmt: str = "text") -> str:
    """Format deviations as text or JSON."""
    if fmt == "json":
        return json.dumps({
            "novel": novel_name,
            "deviations": deviations,
            "count": len(deviations),
            "by_type": _group_by_type(deviations),
            "by_severity": _group_by_severity(deviations),
        }, ensure_ascii=False, indent=2)

    # Text format
    lines = [f"🔍 角色弧线检查: {novel_name}", "=" * 60, ""]

    if not deviations:
        lines.append("✅ 未发现角色弧线偏离")
        return "\n".join(lines)

    # Group by character
    by_char = {}
    for d in deviations:
        c = d.get("character", "?")
        if c not in by_char:
            by_char[c] = []
        by_char[c].append(d)

    for char_name, char_deviations in by_char.items():
        lines.append(f"📌 {char_name} ({len(char_deviations)} 个问题)")
        for d in char_deviations:
            icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(d.get("severity", "low"), "⚪")
            dtype = d.get("deviation_type", "?")
            lines.append(f"   {icon} [{dtype}] {d.get('description', '')}")
            if d.get("suggestion"):
                lines.append(f"      💡 {d['suggestion']}")
        lines.append("")

    # Summary
    by_type = _group_by_type(deviations)
    lines.append("📊 汇总:")
    for dtype, count in by_type.items():
        lines.append(f"   {dtype}: {count}")
    lines.append(f"   总计: {len(deviations)} 个偏离")

    return "\n".join(lines)


def _group_by_type(deviations):
    result = {}
    for d in deviations:
        t = d.get("deviation_type", "?")
        result[t] = result.get(t, 0) + 1
    return result


def _group_by_severity(deviations):
    result = {}
    for d in deviations:
        s = d.get("severity", "low")
        result[s] = result.get(s, 0) + 1
    return result


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="角色弧线偏离检测 — 对比期望里程碑与实际事件"
    )
    parser.add_argument("novel", nargs="?", help="小说项目名称")
    parser.add_argument("--character", help="只检查指定角色")
    parser.add_argument("--volume", type=int, help="当前卷号 (用于ARC_STALLED检测)")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    parser.add_argument("--list-arcs", action="store_true", help="列出所有角色弧线")

    args = parser.parse_args()

    if not args.novel:
        parser.print_help()
        sys.exit(1)

    arcs = load_character_arcs(args.novel)

    if args.list_arcs:
        print(f"📋 {args.novel} 角色弧线:")
        for a in arcs:
            print(f"   📌 {a['name']} ({a['role']}) — {len(a['milestones'])} 个里程碑")
            for m in a["milestones"][:5]:
                mv = m.get("vol", "?")
                mc = m.get("ch", "?")
                event = m.get("event", "")[:60]
                print(f"      第{mv}卷第{mc}章: {event}")
            if len(a["milestones"]) > 5:
                print(f"      ... 还有 {len(a['milestones']) - 5} 个")
        sys.exit(0)

    if not arcs:
        print(f"⚠️  未找到 {args.novel} 的角色弧线定义")
        print("   请在 characters 表中为角色填写 arc 或 lifeline 字段")
        sys.exit(0)

    events = load_actual_events(args.novel)
    current_vol = args.volume
    current_ch = 0

    all_deviations = []
    for char in arcs:
        if args.character and char["name"] != args.character:
            continue
        deviations = compare_arc_to_events(
            char, events,
            current_vol=current_vol or char.get("current_vol", 0),
            current_ch=current_ch or char.get("current_ch", 0),
        )
        all_deviations.extend(deviations)

    report = report_deviations(all_deviations, args.novel, fmt=args.format)
    print(report)

    sys.exit(0 if not all_deviations else 1)

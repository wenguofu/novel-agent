"""
State Tracker — Automatically extracts and tracks state changes across chapters.

After each chapter save, analyzes the content to detect:
  1. Character state changes (location, emotions, abilities, relationships)
  2. World/map updates (new locations, changed rules, new factions)
  3. Plot milestone completions
  4. Foreshadowing planted/resolved

Stores structured state diffs in the content_db for retrieval during
context building — enabling the agent to "remember" what changed.

Integration point:
  - Called from app.py's api_edit_chapter after save
  - Queried by context_builder.py's memory layer
"""

import json
import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Detection Patterns ──────────────────────────────────────────────────

# Patterns for detecting character state changes in chapter content
STATE_CHANGE_PATTERNS = {
    "location_change": [
        r"(?:来到|到达|进入|离开|前往|抵达)(.{1,20}?)(?:[，。；\n])",
        r"(.{1,20}?)(?:到了|到了手)",
    ],
    "emotion_change": [
        r"(?:感到|觉得|变得|变得异常|突然)(.{1,15}?)(?:[，。])",
        r"心中.{0,5}(.{1,10}?)(?:[，。])",
    ],
    "ability_upgrade": [
        r"(?:突破|晋升|升级|领悟|掌握|觉醒|获得)(?:了)?(.{1,20}?)(?:[，。！\n])",
        r"实力.{0,5}(?:提升|增强|暴涨|突破)(.{1,10}?)",
    ],
    "relationship_change": [
        r"(?:与|和)(.{1,8}?)(?:关系|之间的)(.{1,10}?)(?:[，。])",
        r"(?:成为|变成|化为)(.{1,6}?)(?:的)?(.{1,8}?)(?:[，。])",
    ],
    "goal_change": [
        r"(?:决定|决心|立志|发誓|目标)(.{1,20}?)(?:[，。！])",
        r"新的目标.{0,5}(.{1,15}?)",
    ],
}

# Patterns for world building changes
WORLD_CHANGE_PATTERNS = {
    "new_location": [
        r"(?:来到|发现|进入|踏入|抵达)(.{1,20}?)(?:[，。！\n])",
        r"(.{1,15}?)(?:城|镇|村|山|谷|洞|殿|塔|国|界|域)(?:[，。])",
    ],
    "new_rule": [
        r"(?:原来|原来如此|竟然|原来是这样)(.{1,30}?)(?:[，。])",
        r"规则.{0,3}(?:是|为)(.{1,20}?)",
    ],
    "new_faction": [
        r"(.{1,15}?)(?:宗|派|门|会|帮|族|国|组织)(?:[，。])",
        r"(?:势力|组织)(.{1,15}?)(?:[，。])",
    ],
    "item_discovery": [
        r"(?:得到|获得|捡到|发现|入手)(?:了)?(.{1,20}?)(?:[，。！])",
        r"(.{1,15}?)(?:神器|法宝|丹药|秘籍|灵物|宝物)",
    ],
}

FORESHADOWING_PATTERNS = {
    "planted": [
        r"(?:暗中|悄无声息|不动声色|似乎在)(.{1,30}?)(?:[，。])",
        r"(?:伏笔|暗示|隐晦|预示)(.{1,20}?)",
    ],
    "resolved": [
        r"(?:原来|真相|终于|果然)(.{1,30}?)(?:[，。！])",
        r"(?:揭晓|揭示|解密|真相大白)(.{1,20}?)",
    ],
}


# ── State Change Extraction ─────────────────────────────────────────────

class StateTracker:
    """Extracts and tracks state changes from chapter content."""

    def __init__(self):
        self._cache: Dict[str, List[dict]] = {}  # novel_name -> state changes

    def analyze_chapter(
        self,
        novel_name: str,
        volume: int,
        chapter_num: int,
        content: str,
        character_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Analyze a chapter for state changes.

        Args:
            novel_name: Novel project name
            volume: Volume number
            chapter_num: Chapter number
            content: Full chapter content
            character_names: Known character names for filtering

        Returns:
            Dict with detected changes by category
        """
        character_names = character_names or []
        changes = {
            "novel": novel_name,
            "volume": volume,
            "chapter": chapter_num,
            "timestamp": datetime.now().isoformat(),
            "characters": self._detect_character_changes(content, character_names),
            "world": self._detect_world_changes(content),
            "foreshadowing": self._detect_foreshadowing(content),
            "summary": self._extract_summary(content),
        }

        # Cache the result
        key = f"{novel_name}:v{volume}:ch{chapter_num}"
        if novel_name not in self._cache:
            self._cache[novel_name] = []
        self._cache[key] = changes

        return changes

    def _detect_character_changes(
        self, content: str, char_names: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect character state changes in chapter content."""
        changes = []
        paragraphs = content.split("\n")

        # For each known character, find paragraphs where they appear
        for char_name in char_names:
            if len(char_name) < 2:
                continue

            # Find paragraphs mentioning this character
            char_paragraphs = [
                p for p in paragraphs if char_name in p and len(p) > 10
            ]

            if not char_paragraphs:
                continue

            char_changes = {"name": char_name, "changes": []}

            for category, patterns in STATE_CHANGE_PATTERNS.items():
                for pattern in patterns:
                    for para in char_paragraphs[:20]:  # limit search
                        for match in re.finditer(pattern, para):
                            matched = match.group(1).strip()
                            if len(matched) >= 2 and len(matched) <= 30:
                                char_changes["changes"].append({
                                    "category": category,
                                    "detail": matched,
                                    "context": para[:200].strip(),
                                })

            if char_changes["changes"]:
                changes.append(char_changes)

        return changes

    def _detect_world_changes(self, content: str) -> List[Dict[str, Any]]:
        """Detect world building changes."""
        changes = []

        for category, patterns in WORLD_CHANGE_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    matched = match.group(1).strip()
                    if 2 <= len(matched) <= 30:
                        # Get surrounding context
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 100)
                        changes.append({
                            "category": category,
                            "detail": matched,
                            "context": content[start:end].strip(),
                        })

        return changes[:20]  # Limit to avoid noise

    def _detect_foreshadowing(self, content: str) -> List[Dict[str, Any]]:
        """Detect foreshadowing planted or resolved."""
        events = []

        for event_type, patterns in FORESHADOWING_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    matched = match.group(1).strip()
                    if 3 <= len(matched) <= 60:
                        events.append({
                            "type": event_type,
                            "detail": matched,
                            "position": match.start(),
                        })

        return events[:10]

    def _extract_summary(self, content: str) -> str:
        """Extract a brief summary of what happened in this chapter."""
        # Get the first 300 chars as a rough summary
        # Remove markdown headers and formatting
        clean = re.sub(r"^#\s+.*$", "", content, flags=re.MULTILINE)
        clean = re.sub(r"^#{2,6}\s+.*$", "", clean, flags=re.MULTILINE)
        clean = clean.strip()

        # Take first substantial paragraph
        paragraphs = [p.strip() for p in clean.split("\n") if len(p.strip()) > 20]
        if paragraphs:
            return paragraphs[0][:300]
        return clean[:300]

    def get_state_changes_for_volume(
        self, novel_name: str, volume: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get all state changes for a given volume."""
        results = []
        prefix = f"{novel_name}:v{volume}:"
        for key, changes in self._cache.items():
            if key.startswith(prefix):
                results.append(changes)
        return sorted(results, key=lambda c: c.get("chapter", 0))[-limit:]

    def format_for_context(
        self, novel_name: str, volume: int, max_chapters: int = 15
    ) -> str:
        """Format recent state changes as a readable context section.

        This is injected into the writing prompt to inform the agent
        about what's changed across recent chapters.
        """
        # Collect changes from recent chapters
        changes = self.get_state_changes_for_volume(novel_name, volume, max_chapters)

        if not changes:
            return ""

        sections = ["## 📊 近期状态变更追踪"]

        character_events = {}
        world_events = []
        foreshadowing_events = []

        for ch in changes:
            ch_ref = f"第{ch['volume']}卷第{ch['chapter']}章"

            # Character changes
            for cc in ch.get("characters", []):
                name = cc.get("name", "unknown")
                if name not in character_events:
                    character_events[name] = []
                for c in cc.get("changes", []):
                    character_events[name].append(
                        f"[{ch_ref}] {c['category']}: {c['detail']}"
                    )

            # World changes
            for wc in ch.get("world", []):
                world_events.append(
                    f"[{ch_ref}] {wc['category']}: {wc['detail']}"
                )

            # Foreshadowing
            for fe in ch.get("foreshadowing", []):
                foreshadowing_events.append(
                    f"[{ch_ref}] {fe['type']}: {fe['detail']}"
                )

        # Format character changes
        if character_events:
            sections.append("\n### 👤 角色状态变化")
            for name, events in character_events.items():
                # Deduplicate similar events
                unique = list(dict.fromkeys(events))
                sections.append(f"\n**{name}**:")
                for ev in unique[-5:]:  # Last 5 per character
                    sections.append(f"  - {ev}")

        # Format world changes
        if world_events:
            sections.append("\n### 🌍 世界观变化")
            unique = list(dict.fromkeys(world_events))
            for ev in unique[-10:]:
                sections.append(f"  - {ev}")

        # Format foreshadowing
        if foreshadowing_events:
            sections.append("\n### 🔮 伏笔追踪")
            unique = list(dict.fromkeys(foreshadowing_events))
            for ev in unique[-8:]:
                sections.append(f"  - {ev}")

        sections.append(
            f"\n> 以上状态变更基于最近 {len(changes)} 章的内容自动提取。"
            f"请在写作时保持一致性。"
        )

        return "\n".join(sections)

    def clear_cache(self):
        """Clear the state change cache."""
        self._cache.clear()


# ── Global instance ─────────────────────────────────────────────────────

_state_tracker: Optional[StateTracker] = None


def get_state_tracker() -> StateTracker:
    global _state_tracker
    if _state_tracker is None:
        _state_tracker = StateTracker()
    return _state_tracker


def analyze_and_store_chapter(
    novel_name: str,
    volume: int,
    chapter_num: int,
    content: str,
    character_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convenience function: analyze a chapter and store state changes."""
    tracker = get_state_tracker()

    # Get character names from DB if not provided
    if not character_names:
        try:
            import content_db as db
            chars = db.get_characters(novel_name)
            character_names = [c.get("name", "") for c in chars if c.get("name")]
        except Exception:
            character_names = []

    result = tracker.analyze_chapter(
        novel_name=novel_name,
        volume=volume,
        chapter_num=chapter_num,
        content=content,
        character_names=character_names,
    )

    logger.info(
        f"[StateTracker] Chapter v{volume}ch{chapter_num}: "
        f"{len(result.get('characters', []))} character changes, "
        f"{len(result.get('world', []))} world changes, "
        f"{len(result.get('foreshadowing', []))} foreshadowing events"
    )

    return result

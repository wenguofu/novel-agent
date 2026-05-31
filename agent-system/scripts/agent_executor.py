#!/usr/bin/env python3
"""
Agent Execution Framework — real agent validation, execution tracking, and pipeline orchestration.

Capabilities:
- JSON Schema definitions for all 12 agents (input/output schemas + prerequisites)
- validate_agent_output() — validates agent output against schema + heuristics
- check_prerequisites() — checks required input files exist before agent runs
- run_agent_pipeline() — orchestrates all agents for a given stage
- Execution log management — writes state/agent_execution_log.json

Backwards-compatible with agent_tracker.py regex signature detection.
Schema validation produces warnings by default; use --strict for errors.

Usage:
  python agent_executor.py --novel <novel_name> [--novel-root <path>] check <stage>
  python agent_executor.py --novel <novel_name> validate --file <path> --agent <name>
  python agent_executor.py --novel <novel_name> pipeline <stage>
  python agent_executor.py --novel <novel_name> log
  python agent_executor.py --list-agents
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# YAML frontmatter support — optional dependency
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ValidationResult:
    valid: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class PrerequisiteResult:
    passed: bool
    missing: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class StageResult:
    stage: str
    passed: bool
    agents_checked: list = field(default_factory=list)
    agents_failed: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class PipelineResult:
    passed: bool
    stages: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class ExecutionRecord:
    agent_name: str
    stage: str
    start_time: str
    end_time: str = ""
    status: str = "pending"
    output_file: str = ""
    validation_errors: list = field(default_factory=list)
    schema_version: str = "1.0"

    def to_dict(self):
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# Agent Schema Definitions (YAML Frontmatter + Hardcoded Fallback)
# ═══════════════════════════════════════════════════════════════════════

# Resolve agent-system directory relative to this script
_SCRIPT_DIR = Path(__file__).resolve().parent
_AGENT_SYSTEM_DIR = _SCRIPT_DIR.parent
_AGENT_TEAM_DIR = _AGENT_SYSTEM_DIR / "team"

# Display name → agent filename mapping (for frontmatter lookup)
_AGENT_NAME_TO_FILE = {
    "总主编剧": "agent-chief-writer.md",
    "类型规则": "agent-genre-rules.md",
    "世界观设定": "agent-world-settings.md",
    "人物": "agent-characters.md",
    "长线剧情": "agent-long-plot.md",
    "章节规划": "agent-chapter-planner.md",
    "正文写作": "agent-writing.md",
    "编辑审稿": "agent-editor-review.md",
    "合规审查": "agent-compliance.md",
    "连载状态": "agent-status.md",
    "剧情执行跟踪": "agent-plot-tracking.md",
    "写作助手": "agent-assistant.md",
}


def _read_frontmatter(filepath: Path) -> Optional[dict]:
    """Parse YAML frontmatter from a Markdown file.

    Returns dict of frontmatter fields, or None if no frontmatter found.
    """
    if not _HAS_YAML or not filepath.exists():
        return None
    try:
        content = filepath.read_text(encoding='utf-8')
        if not content.startswith('---'):
            return None
        # Extract between first and second ---
        parts = content.split('---', 2)
        if len(parts) < 3:
            return None
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return None


def _load_schema_from_frontmatter(agent_name: str) -> Optional[dict]:
    """Try to load agent schema from YAML frontmatter in the agent's Markdown file.

    Returns schema dict on success, None if the file or frontmatter is unavailable.
    """
    filename = _AGENT_NAME_TO_FILE.get(agent_name)
    if not filename:
        return None
    filepath = _AGENT_TEAM_DIR / filename
    fm = _read_frontmatter(filepath)
    if not fm:
        return None

    return {
        "display_name": fm.get("display_name", agent_name),
        "agent_file": f"team/{filename}",
        "required_inputs": fm.get("prerequisites", []),
        "output_files": fm.get("outputs", []),
        "output_schema": fm.get("output_schema", {}),
        "signatures": fm.get("signatures", []),
        "content_heuristics": fm.get("content_heuristics", {}),
        "severity_levels": fm.get("severity_levels", {}),
        "stage": fm.get("stage", ""),
        "escalation": fm.get("escalation", {}),
        "_source": "frontmatter",
    }


_AGENT_SCHEMAS = {
    "总主编剧": {
        "display_name": "总主编剧",
        "agent_file": "team/agent-chief-writer.md",
        "required_inputs": ["genre_bible.md", "full_story_arc.md"],
        "output_files": ["outline/vol-XX-chapters.md", "volume_plan.md"],
        "output_schema": {
            "type": "object",
            "required": ["volume_chapters_file", "chapter_assignments"],
            "properties": {
                "volume_chapters_file": {"type": "string", "minLength": 5},
                "chapter_assignments": {"type": "array", "minItems": 1},
                "rhythm_map": {"type": "object"},
            },
        },
        "signatures": [
            r"总主编剧",
            r"卷级章纲|章节预排|本卷预计章节数",
            r"genre_bible.*约束",
            r"节奏规则表|类型节奏映射",
        ],
    },
    "类型规则": {
        "display_name": "类型规则",
        "agent_file": "team/agent-genre-rules.md",
        "required_inputs": ["genre_bible.md"],
        "output_files": ["genre_bible.md"],
        "output_schema": {
            "type": "object",
            "required": ["genre"],
            "properties": {
                "genre": {"type": "string", "minLength": 1},
                "promises": {"type": "array"},
                "required_elements": {"type": "array"},
                "compliance_check": {"type": "object"},
            },
        },
        "signatures": [
            r"类型(?:承诺|检查|规则)",
            r"是否加载.*genre_bible",
            r"是否符合类型承诺",
            r"是否包含危机.*专业解释.*主角反差",
        ],
    },
    "世界观设定": {
        "display_name": "世界观设定",
        "agent_file": "team/agent-world-settings.md",
        "required_inputs": ["world_bible.md"],
        "output_files": ["world_bible.md"],
        "output_schema": {
            "type": "object",
            "required": ["overall_compliance"],
            "properties": {
                "new_settings": {"type": "array"},
                "chapter_setting_review": {"type": "object"},
                "overall_compliance": {"type": "string", "enum": ["通过", "需修改"]},
            },
        },
        "signatures": [
            r"世界观|世界设定|设定(?:检查|一致性)",
            r"是否违反世界观",
            r"是否新增设定",
            r"力量体系|地图|组织|限制条件",
        ],
    },
    "人物": {
        "display_name": "人物",
        "agent_file": "team/agent-characters.md",
        "required_inputs": ["characters.md", "current_status.md"],
        "output_files": ["characters.md"],
        "output_schema": {
            "type": "object",
            "required": ["overall_compliance"],
            "properties": {
                "characters_involved": {"type": "array"},
                "overall_compliance": {"type": "string", "enum": ["通过", "需修改"]},
            },
        },
        "signatures": [
            r"人物(?:检查|一致性|档案|状态)",
            r"是否(?:符合|违反)人物",
            r"人物(?:关系|状态|行为)",
        ],
    },
    "长线剧情": {
        "display_name": "长线剧情",
        "agent_file": "team/agent-long-plot.md",
        "required_inputs": ["full_story_arc.md", "volume_plan.md"],
        "output_files": ["full_story_arc.md"],
        "output_schema": {
            "type": "object",
            "required": ["current_phase", "plot_alignment"],
            "properties": {
                "current_phase": {"type": "string", "minLength": 1},
                "plot_alignment": {"type": "string"},
                "foreshadowing_management": {"type": "object"},
            },
        },
        "signatures": [
            r"长线剧情|主线|分卷",
            r"伏笔(?:检查|状态|变化)",
            r"full_story_arc|volume_plan",
        ],
    },
    "章节规划": {
        "display_name": "章节规划",
        "agent_file": "team/agent-chapter-planner.md",
        "required_inputs": [
            "outline/vol-XX-chapters.md",
            "current_status.md",
            "danger_issue_{章节号}.md",
        ],
        "output_files": [],
        "output_schema": {
            "type": "object",
            "required": ["chapter_number", "chapter_function", "scene_sequence"],
            "properties": {
                "chapter_number": {"type": "integer", "minimum": 1},
                "chapter_title": {"type": "string", "minLength": 1},
                "chapter_function": {"type": "string", "minLength": 1},
                "scene_sequence": {"type": "array", "minItems": 1},
                "style_directive": {"type": "string"},
                "word_count_target": {"type": "integer", "minimum": 2500},
            },
        },
        "signatures": [
            r"章纲|章节规划",
            r"主要冲突|信息增量|结尾悬念",
            r"本章功能(?!.*审稿)",
        ],
    },
    "正文写作": {
        "display_name": "正文写作",
        "agent_file": "team/agent-writing.md",
        "required_inputs": [
            "outline/vol-XX-chapters.md",
            "current_status.md",
        ],
        "output_files": ["manuscript/vol-XX/ch-XXXX.md"],
        "output_schema": {
            "type": "object",
            "required": ["chapter_file", "word_count"],
            "properties": {
                "chapter_file": {"type": "string", "minLength": 10},
                "word_count": {"type": "integer", "minimum": 2500},
                "style_applied": {"type": "string"},
                "new_settings_introduced": {"type": "array"},
                "character_state_changes": {"type": "array"},
                "foreshadowing_changes": {"type": "object"},
            },
        },
        "signatures": [
            r"正文[：:]",
            r"章节标题[：:]",
            r"(?:新增设定|人物状态变化|伏笔变化)",
            r"^#\s*第.{1,6}章",
        ],
        "content_heuristics": {
            "min_chinese_chars": 2500,
            "must_start_with_chapter_title": True,
            "max_binary_contrasts": 2,
        },
    },
    "编辑审稿": {
        "display_name": "编辑审稿",
        "agent_file": "team/agent-editor-review.md",
        "required_inputs": [
            "manuscript/vol-XX/ch-XXXX.md",
            "outline/vol-XX-chapters.md",
        ],
        "output_files": ["reviews/ch-XXXX-review.md"],
        "output_schema": {
            "type": "object",
            "required": ["conclusion", "revision_count"],
            "properties": {
                "conclusion": {
                    "type": "string",
                    "enum": ["通过", "修改", "重写", "升级(修改3次)", "升级(重写2次)"],
                },
                "revision_count": {"type": "integer", "minimum": 0},
                "character_check": {"type": "object"},
                "setting_check": {"type": "object"},
                "foreshadowing_check": {"type": "object"},
                "crisis_check": {"type": "object"},
                "script_check_results": {"type": "object"},
                "revision_requirements": {"type": "array"},
            },
        },
        "signatures": [
            r"审稿(?:结论|记录|维度)",
            r"评分卡|评分[：:]\s*\d",
            r"章节功能.*节奏.*信息密度",
            r"通过.*修改.*重写",
        ],
    },
    "合规审查": {
        "display_name": "合规审查",
        "agent_file": "team/agent-compliance.md",
        "required_inputs": [
            "manuscript/vol-XX/ch-XXXX.md",
            "alias_registry.md",
        ],
        "output_files": ["alias_registry.md"],
        "output_schema": {
            "type": "object",
            "required": ["compliance_conclusion"],
            "properties": {
                "compliance_conclusion": {"type": "string", "enum": ["通过", "修改", "重写"]},
                "replacement_list": {"type": "array"},
                "new_alias_registrations": {"type": "array"},
            },
        },
        "signatures": [
            r"合规(?:检查|审查|结论|名称)",
            r"是否出现真实",
            r"alias_registry|别名",
            r"虚构别名|替代名",
        ],
    },
    "连载状态": {
        "display_name": "连载状态",
        "agent_file": "team/agent-status.md",
        "required_inputs": [
            "current_status.md",
            "manuscript/vol-XX/ch-XXXX.md",
        ],
        "output_files": ["state/current_status.md"],
        "output_schema": {
            "type": "object",
            "required": ["status_file", "current_chapter"],
            "properties": {
                "status_file": {"type": "string"},
                "current_chapter": {"type": "string"},
                "status_summary": {"type": "object"},
                "volume_update_needed": {"type": "string", "enum": ["是", "否"]},
            },
        },
        "signatures": [
            r"连载状态|current_status",
            r"当前(?:剧情|状态)",
            r"资料更新|状态更新",
        ],
    },
    "剧情执行跟踪": {
        "display_name": "剧情执行跟踪",
        "agent_file": "team/agent-plot-tracking.md",
        "required_inputs": [
            "full_story_arc.md",
            "outline/vol-XX-chapters.md",
            "current_status.md",
        ],
        "output_files": ["antagonist_timeline.md", "plot_execution_log.md"],
        "output_schema": {
            "type": "object",
            "required": ["check_type", "overall_health"],
            "properties": {
                "check_type": {"type": "string"},
                "overall_health": {
                    "type": "string",
                    "enum": ["正常", "需关注", "需调整"],
                },
                "antagonist_progress": {"type": "object"},
                "protagonist_progress": {"type": "object"},
                "deviation_alerts": {"type": "array"},
            },
        },
        "signatures": [
            r"剧情.*跟踪|执行.*偏差|偏差.*告警",
            r"反派.*时间线|antagonist_timeline",
            r"信息(?:差|不对称)|执行报告",
            r"plot_execution_log",
        ],
    },
    "写作助手": {
        "display_name": "写作助手",
        "agent_file": "team/agent-assistant.md",
        "required_inputs": ["project.md"],
        "output_files": [],
        "output_schema": {
            "type": "object",
            "required": [],
            "properties": {},
        },
        "signatures": [
            r"写作助手|agent-assistant",
            r"【任务】|【工作流】|【状态】",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════
# Stage → Agents Mapping (single source of truth)
# ═══════════════════════════════════════════════════════════════════════

STAGE_AGENTS = {
    "phase1_opening": ["总主编剧", "类型规则", "世界观设定", "人物"],
    "phase2_arc": ["总主编剧", "长线剧情", "类型规则"],
    "phase3_volume_outline": ["总主编剧", "类型规则", "世界观设定", "长线剧情"],
    "phase4_chapter_planning": ["总主编剧", "章节规划"],
    "phase5_writing": ["正文写作"],
    "phase6_review": ["编辑审稿", "类型规则", "人物", "世界观设定", "合规审查"],
    "phase7_status_update": ["连载状态"],
}

PHASE_LABELS = {
    "phase1_opening": "开书",
    "phase2_arc": "长线剧情",
    "phase3_volume_outline": "卷级章纲预排",
    "phase4_chapter_planning": "章节规划",
    "phase5_writing": "正文写作",
    "phase6_review": "编辑审稿",
    "phase7_status_update": "状态更新",
}

PHASE_ORDER = list(PHASE_LABELS.keys())


# ═══════════════════════════════════════════════════════════════════════
# Execution Log Management
# ═══════════════════════════════════════════════════════════════════════


def get_execution_log_path(novel_path: str) -> Path:
    return Path(novel_path) / "state" / "agent_execution_log.json"


def load_execution_log(novel_path: str) -> list[dict]:
    log_path = get_execution_log_path(novel_path)
    if not log_path.exists():
        return []
    try:
        return json.loads(log_path.read_text())
    except (json.JSONDecodeError, IOError):
        return []


def append_execution_record(novel_path: str, record: dict):
    log_path = get_execution_log_path(novel_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    records = load_execution_log(novel_path)
    records.append(record)
    log_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))


def create_execution_record(
    agent_name: str, stage: str, status: str = "pending",
    output_file: str = "", validation_errors: list = None,
) -> dict:
    return ExecutionRecord(
        agent_name=agent_name,
        stage=stage,
        status=status,
        output_file=output_file,
        validation_errors=validation_errors or [],
        start_time=datetime.now().isoformat(),
    ).to_dict()


# ═══════════════════════════════════════════════════════════════════════
# Core Validation Logic
# ═══════════════════════════════════════════════════════════════════════


# Cache for frontmatter-loaded schemas (lazy, first-access)
_SCHEMA_CACHE: dict = {}


def get_agent_schema(agent_name: str) -> Optional[dict]:
    """Get agent schema, preferring YAML frontmatter, falling back to hardcoded."""
    if agent_name in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[agent_name]

    # Try frontmatter first
    fm_schema = _load_schema_from_frontmatter(agent_name)
    if fm_schema:
        _SCHEMA_CACHE[agent_name] = fm_schema
        return fm_schema

    # Fall back to hardcoded
    hardcoded = _AGENT_SCHEMAS.get(agent_name)
    if hardcoded:
        hardcoded["_source"] = "hardcoded"
    _SCHEMA_CACHE[agent_name] = hardcoded
    return hardcoded


def list_agents() -> list[str]:
    return list(_AGENT_SCHEMAS.keys())


def list_agents_detail() -> list[dict]:
    result = []
    for name, schema in _AGENT_SCHEMAS.items():
        result.append({
            "name": name,
            "display_name": schema["display_name"],
            "agent_file": schema["agent_file"],
            "required_inputs": schema["required_inputs"],
            "output_files": schema["output_files"],
            "signature_count": len(schema.get("signatures", [])),
        })
    return result


def check_prerequisites(agent_name: str, novel_path: str) -> PrerequisiteResult:
    """Check that all required input files exist for an agent."""
    schema = get_agent_schema(agent_name)
    if not schema:
        return PrerequisiteResult(passed=False, missing=[f"Unknown agent: {agent_name}"])

    missing = []
    novel_dir = Path(novel_path)

    for rel_path in schema.get("required_inputs", []):
        # Handle placeholder paths like "outline/vol-XX-chapters.md"
        if "XX" in rel_path or "XXXX" in rel_path:
            # Pattern match: find files that match the pattern
            pattern = rel_path
            if "vol-XX" in pattern:
                pattern = pattern.replace("vol-XX", "vol-*")
            if "ch-XXXX" in pattern:
                pattern = pattern.replace("ch-XXXX", "ch-*")
            if "ch-{四位章节号}" in pattern:
                pattern = pattern.replace("ch-{四位章节号}", "ch-*")
            if "danger_issue_{章节号}" in pattern:
                pattern = pattern.replace("danger_issue_{章节号}", "danger_issue_*")
            matches = list(novel_dir.glob(pattern))
            if not matches:
                missing.append(
                    f"{rel_path} (no matching files found for pattern: {pattern})"
                )
        else:
            full_path = novel_dir / rel_path
            if not full_path.exists():
                missing.append(rel_path)

    return PrerequisiteResult(passed=len(missing) == 0, missing=missing)


def _extract_plain_text(md_content: str) -> str:
    """Strip markdown formatting for content analysis."""
    text = md_content
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    return text.strip()


def _count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def _check_content_heuristics(content: str, schema: dict) -> list[str]:
    """Apply content-level heuristic checks beyond schema validation."""
    warnings = []
    heuristics = schema.get("content_heuristics", {})
    plain = _extract_plain_text(content)

    if "min_chinese_chars" in heuristics:
        cn_count = _count_chinese_chars(plain)
        if cn_count < heuristics["min_chinese_chars"]:
            warnings.append(
                f"中文字数 {cn_count} < 最低要求 {heuristics['min_chinese_chars']}"
            )

    if heuristics.get("must_start_with_chapter_title"):
        if not re.match(r"^#\s*第.+章", content.strip()):
            warnings.append("未以章节标题开头（# 第X章）")

    if "max_binary_contrasts" in heuristics:
        binary_count = len(
            re.findall(r"不是[^。！？\n]{0,50}(?:。|！|？|\n)[^。！？\n]{0,50}而是", plain)
        )
        if binary_count > heuristics["max_binary_contrasts"]:
            warnings.append(
                f"二元对照句式 {binary_count} 次 > 上限 {heuristics['max_binary_contrasts']} 次"
            )

    return warnings


def _check_signatures(content: str, agent_name: str) -> tuple[bool, list[str]]:
    """Run regex signature matching (backwards compatible with agent_tracker)."""
    schema = get_agent_schema(agent_name)
    if not schema:
        return False, ["Unknown agent"]

    signatures = schema.get("signatures", [])
    if not signatures:
        return agent_name in content, []

    matched = []
    for pattern in signatures:
        if re.search(pattern, content, re.MULTILINE):
            matched.append(pattern)
    return len(matched) > 0, matched


def _validate_output_schema_fields(content: str, output_schema: dict) -> list[str]:
    """Validate that markdown content contains fields matching the JSON Schema structure.
    This is a lightweight structural validation — it checks for the PRESENCE of
    expected sections/fields in the output text, not strict JSON parsing.
    """
    errors = []
    if not output_schema:
        return errors

    required_fields = output_schema.get("required", [])
    properties = output_schema.get("properties", {})

    for field in required_fields:
        props = properties.get(field, {})
        ftype = props.get("type", "string")

        if ftype == "array":
            if props.get("minItems"):
                # Look for list items or array-like structures
                items = re.findall(r"^\s*[-*]\s+", content, re.MULTILINE)
                if len(items) < props["minItems"]:
                    errors.append(
                        f"字段 '{field}' 需要至少 {props['minItems']} 个列表项，实际找到 {len(items)} 个"
                    )
            elif not re.search(rf"{field}", content):
                errors.append(f"缺少字段 '{field}'")

        elif ftype == "integer":
            m = re.search(rf"{field}[：:]\s*(\d+)", content)
            if not m:
                errors.append(f"缺少数值字段 '{field}'")
            elif "minimum" in props:
                val = int(m.group(1))
                if val < props["minimum"]:
                    errors.append(
                        f"字段 '{field}' 值 {val} < 最小值 {props['minimum']}"
                    )

        elif ftype == "string" and "enum" in props:
            found = False
            for val in props["enum"]:
                if val in content:
                    found = True
                    break
            if not found:
                valid_vals = ", ".join(props["enum"])
                errors.append(
                    f"字段 '{field}' 值不在有效范围内，期望: {valid_vals}"
                )

        else:
            # Generic field check — look for field name in content
            if not re.search(rf"{field}", content):
                errors.append(f"缺少字段 '{field}'")

    return errors


def validate_agent_output(
    content: str, agent_name: str, strict: bool = False
) -> ValidationResult:
    """Validate agent output against its schema.

    Performs three levels of validation:
    1. Signature check (regex) — always runs, always backward compatible
    2. Schema field check — validates required fields present
    3. Content heuristics — chapter-specific checks (word count, structure)

    Args:
        content: The agent output text (markdown)
        agent_name: Which agent to validate against
        strict: If True, schema failures are errors. If False, they're warnings.

    Returns:
        ValidationResult with errors and warnings
    """
    schema = get_agent_schema(agent_name)
    if not schema:
        return ValidationResult(
            valid=False,
            errors=[f"Unknown agent: {agent_name}. Known: {', '.join(list_agents())}"],
        )

    errors = []
    warnings = []

    # Level 1: Signature check (always required)
    sig_ok, sig_matched = _check_signatures(content, agent_name)
    if not sig_ok:
        errors.append(
            f"Agent '{agent_name}' 签名未匹配。搜索模式: {schema.get('signatures', [])}"
        )
    else:
        warnings.append(f"签名匹配: {len(sig_matched)}/{len(schema.get('signatures', []))}")

    # Level 2: Schema field validation
    output_schema = schema.get("output_schema", {})
    field_errors = _validate_output_schema_fields(content, output_schema)
    if field_errors:
        if strict:
            errors.extend(field_errors)
        else:
            warnings.extend([f"[schema] {e}" for e in field_errors])

    # Level 3: Content heuristics
    heuristic_warnings = _check_content_heuristics(content, schema)
    if heuristic_warnings:
        if strict:
            errors.extend(heuristic_warnings)
        else:
            warnings.extend([f"[heuristic] {w}" for w in heuristic_warnings])

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def run_agent_pipeline(
    novel_path: str, stage: str, file_path: Optional[str] = None, strict: bool = False
) -> StageResult:
    """Orchestrate agent validation for a given stage.

    Args:
        novel_path: Root directory of the novel project
        stage: Stage identifier (e.g., 'phase5_writing')
        file_path: Specific output file to check (optional)
        strict: Whether to treat schema warnings as errors

    Returns:
        StageResult with pass/fail per agent
    """
    required_agents = STAGE_AGENTS.get(stage, [])
    if not required_agents:
        return StageResult(
            stage=stage,
            passed=False,
            errors=[f"Unknown stage: {stage}"],
        )

    result = StageResult(stage=stage, passed=True)

    for agent_name in required_agents:
        schema = get_agent_schema(agent_name)
        if not schema:
            result.errors.append(f"No schema for agent: {agent_name}")
            continue

        # Check prerequisites
        prereqs = check_prerequisites(agent_name, novel_path)
        if not prereqs.passed:
            result.warnings.append(
                f"[{agent_name}] 前置条件不满足: {', '.join(prereqs.missing)}"
            )

        # If a specific file is given, validate it
        if file_path:
            fp = Path(file_path)
            if fp.exists():
                content = fp.read_text()
                validation = validate_agent_output(content, agent_name, strict=strict)
                if validation.valid:
                    result.agents_checked.append(agent_name)
                else:
                    result.agents_failed.append(agent_name)
                    result.errors.extend(
                        [f"[{agent_name}] {e}" for e in validation.errors]
                    )
                result.warnings.extend(
                    [f"[{agent_name}] {w}" for w in validation.warnings]
                )

                # Record execution
                status = "passed" if validation.valid else "failed"
                record = create_execution_record(
                    agent_name=agent_name,
                    stage=stage,
                    status=status,
                    output_file=str(file_path),
                    validation_errors=validation.errors,
                )
                record["end_time"] = datetime.now().isoformat()
                append_execution_record(novel_path, record)
            else:
                # File doesn't exist — agent hasn't produced output
                schema = get_agent_schema(agent_name)
                expected_outputs = schema.get("output_files", []) if schema else []
                if expected_outputs:
                    result.agents_failed.append(agent_name)
                    result.errors.append(
                        f"[{agent_name}] 输出文件不存在: {file_path}，期望: {expected_outputs}"
                    )
        else:
            # No file given — check if expected outputs exist
            has_output = False
            for out_rel in schema.get("output_files", []):
                if "XX" in out_rel or "XXXX" in out_rel:
                    pattern = out_rel.replace("vol-XX", "vol-*").replace("ch-XXXX", "ch-*")
                    pattern = pattern.replace("ch-{四位章节号}", "ch-*")
                    matches = list(Path(novel_path).glob(pattern))
                    if matches:
                        has_output = True
                        result.agents_checked.append(agent_name)
                        break
                else:
                    fp = Path(novel_path) / out_rel
                    if fp.exists():
                        has_output = True
                        result.agents_checked.append(agent_name)
                        break

            if not has_output:
                result.warnings.append(
                    f"[{agent_name}] 未找到输出文件，无法验证"
                )

    result.passed = len(result.errors) == 0
    return result


def generate_execution_report(novel_path: str) -> dict:
    records = load_execution_log(novel_path)
    if not records:
        return {"novel": os.path.basename(novel_path), "total_executions": 0, "by_stage": {}, "by_agent": {}}

    by_stage = {}
    by_agent = {}
    for r in records:
        stage = r.get("stage", "unknown")
        agent = r.get("agent_name", "unknown")
        if stage not in by_stage:
            by_stage[stage] = {"total": 0, "passed": 0, "failed": 0}
        by_stage[stage]["total"] += 1
        if r.get("status") == "passed":
            by_stage[stage]["passed"] += 1
        else:
            by_stage[stage]["failed"] += 1

        if agent not in by_agent:
            by_agent[agent] = {"total": 0, "passed": 0, "failed": 0}
        by_agent[agent]["total"] += 1
        if r.get("status") == "passed":
            by_agent[agent]["passed"] += 1
        else:
            by_agent[agent]["failed"] += 1

    return {
        "novel": os.path.basename(novel_path),
        "total_executions": len(records),
        "last_execution": records[-1].get("start_time", "") if records else "",
        "by_stage": by_stage,
        "by_agent": by_agent,
    }


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

_NOVELS_ROOT_DEFAULT = Path(__file__).resolve().parent.parent.parent / "novels"


def _resolve_novel(novel_name: str, novel_root: Optional[str] = None) -> str:
    root = Path(novel_root) if novel_root else _NOVELS_ROOT_DEFAULT
    novel_path = root / novel_name
    if not novel_path.exists():
        print(f"❌ 小说目录不存在: {novel_path}")
        sys.exit(1)
    return str(novel_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent Execution Framework — validate agents, track execution, orchestrate pipelines"
    )
    parser.add_argument("--novel", help="小说项目名称")
    parser.add_argument("--novel-root", help="novels 目录路径 (默认: ../novels/)")
    parser.add_argument("--strict", action="store_true", help="schema 警告也视为错误")

    sub = parser.add_subparsers(dest="command")

    # check: check prerequisites for a stage
    sp_check = sub.add_parser("check", help="检查阶段的 Agent 前置条件")
    sp_check.add_argument("stage", help="阶段标识 (e.g., phase5_writing)")

    # validate: validate a file against an agent schema
    sp_val = sub.add_parser("validate", help="验证 Agent 输出文件")
    sp_val.add_argument("--file", required=True, help="要验证的输出文件路径")
    sp_val.add_argument("--agent", required=True, help="Agent 名称")

    # pipeline: run full pipeline check for a stage
    sp_pipe = sub.add_parser("pipeline", help="运行阶段管道检查")
    sp_pipe.add_argument("stage", help="阶段标识")
    sp_pipe.add_argument("--file", help="具体输出文件 (可选)")

    # log: show execution log
    sp_log = sub.add_parser("log", help="查看执行日志")
    sp_log.add_argument("--format", choices=["summary", "full"], default="summary")

    # list-agents
    sub.add_parser("list-agents", help="列出所有 Agent")

    args = parser.parse_args()

    if args.command == "list-agents":
        print("📋 注册的 Agent:")
        for detail in list_agents_detail():
            prereq_str = ", ".join(detail["required_inputs"]) if detail["required_inputs"] else "无"
            output_str = ", ".join(detail["output_files"]) if detail["output_files"] else "无"
            print(f"  📌 {detail['name']} ({detail['display_name']})")
            print(f"     文件: {detail['agent_file']}")
            print(f"     前置条件: {prereq_str}")
            print(f"     输出文件: {output_str}")
            print(f"     签名: {detail['signature_count']} 个正则模式")
            print()
        sys.exit(0)

    if args.command == "check":
        if not args.novel:
            print("❌ 需要 --novel 参数")
            sys.exit(1)
        novel_path = _resolve_novel(args.novel, args.novel_root)
        stage = args.stage
        required = STAGE_AGENTS.get(stage, [])
        if not required:
            print(f"❌ 未知阶段: {stage}")
            print(f"   已知阶段: {', '.join(PHASE_ORDER)}")
            sys.exit(1)

        label = PHASE_LABELS.get(stage, stage)
        print(f"🔍 检查 {label} ({stage}) 前置条件:")
        all_ok = True
        for agent_name in required:
            prereqs = check_prerequisites(agent_name, novel_path)
            status = "✅" if prereqs.passed else "⚠️"
            print(f"   {status} {agent_name}")
            for m in prereqs.missing:
                print(f"      缺失: {m}")
            if not prereqs.passed:
                all_ok = False
        print()
        if all_ok:
            print("✅ 所有前置条件满足")
        else:
            print("⚠️  部分前置条件不满足")
        sys.exit(0 if all_ok else 1)

    elif args.command == "validate":
        if not args.novel:
            print("❌ 需要 --novel 参数")
            sys.exit(1)
        novel_path = _resolve_novel(args.novel, args.novel_root)
        fp = Path(args.file)
        if not fp.is_absolute():
            fp = Path(novel_path) / args.file
        if not fp.exists():
            print(f"❌ 文件不存在: {fp}")
            sys.exit(1)

        content = fp.read_text()
        result = validate_agent_output(content, args.agent, strict=args.strict)
        print(f"🔍 验证 Agent '{args.agent}' 输出: {fp.name}")
        print(f"   有效: {'✅' if result.valid else '❌'}")
        for e in result.errors:
            print(f"   ❌ {e}")
        for w in result.warnings:
            print(f"   ⚠️  {w}")
        sys.exit(0 if result.valid else 1)

    elif args.command == "pipeline":
        if not args.novel:
            print("❌ 需要 --novel 参数")
            sys.exit(1)
        novel_path = _resolve_novel(args.novel, args.novel_root)
        result = run_agent_pipeline(novel_path, args.stage, args.file, strict=args.strict)
        label = PHASE_LABELS.get(args.stage, args.stage)
        print(f"🔍 管道检查: {label} ({args.stage})")
        print(f"   通过: {'✅' if result.passed else '❌'}")
        print(f"   已验证 Agent: {', '.join(result.agents_checked) if result.agents_checked else '无'}")
        print(f"   失败 Agent: {', '.join(result.agents_failed) if result.agents_failed else '无'}")
        for e in result.errors:
            print(f"   ❌ {e}")
        for w in result.warnings:
            print(f"   ⚠️  {w}")
        sys.exit(0 if result.passed else 1)

    elif args.command == "log":
        if not args.novel:
            print("❌ 需要 --novel 参数")
            sys.exit(1)
        novel_path = _resolve_novel(args.novel, args.novel_root)
        if args.format == "full":
            records = load_execution_log(novel_path)
            print(f"📋 执行日志 ({len(records)} 条记录):")
            for r in records:
                status_icon = {"passed": "✅", "failed": "❌", "pending": "⏳"}.get(r.get("status"), "❓")
                print(f"   {status_icon} [{r.get('stage', '?')}] {r.get('agent_name', '?')}")
                print(f"      时间: {r.get('start_time', '?')}")
                print(f"      文件: {r.get('output_file', '?')}")
                if r.get("validation_errors"):
                    print(f"      错误: {', '.join(r['validation_errors'])}")
        else:
            report = generate_execution_report(novel_path)
            print(f"📖 {report['novel']}")
            print(f"   总执行次数: {report['total_executions']}")
            print(f"   最后执行: {report.get('last_execution', '无')}")
            print()
            print("按阶段:")
            for stage, stats in report.get("by_stage", {}).items():
                label = PHASE_LABELS.get(stage, stage)
                total = stats["total"]
                passed = stats["passed"]
                rate = f"{passed}/{total}" if total > 0 else "N/A"
                print(f"   {label}: {rate} 通过")
            print()
            print("按 Agent:")
            for agent, stats in report.get("by_agent", {}).items():
                passed = stats["passed"]
                total = stats["total"]
                icon = "✅" if passed == total else "⚠️"
                print(f"   {icon} {agent}: {passed}/{total} 通过")
        sys.exit(0)

    elif args.command is None:
        parser.print_help()
        sys.exit(1)

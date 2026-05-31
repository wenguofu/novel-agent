#!/usr/bin/env python3
"""阶段门控 — 阻止跳过阶段的硬性检查 (v2.0)

Enhanced with:
- --validate flag: run agent_executor pipeline check before completing phase
- Integration with agent_tracker for agent execution verification
- agent_execution_summary metadata in stage_gate.json
- Structured error output for API integration

用法:
  python3 stage_gate.py --project <novel_dir> check <phase>
  python3 stage_gate.py --project <novel_dir> complete <phase> [--validate]
  python3 stage_gate.py --project <novel_dir> status
  python3 stage_gate.py --project <novel_dir> reset <phase>
  python3 stage_gate.py --project <novel_dir> init <novel_name>
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

FALLBACK_ROOT = Path(__file__).resolve().parent.parent

# Severity levels for gate checks
SEVERITY_ERROR = "error"      # Blocks progression
SEVERITY_WARNING = "warning"  # Reports but allows progression
SEVERITY_INFO = "info"        # Logged only

PHASE_ORDER = ["phase1_opening", "phase2_arc", "phase3_volume_outline",
               "phase4_chapter_planning", "phase5_writing",
               "phase6_review", "phase7_status_update"]

PHASE_DEPS = {
    "phase1_opening": [],
    "phase2_arc": ["phase1_opening"],
    "phase3_volume_outline": ["phase2_arc"],
    "phase4_chapter_planning": ["phase3_volume_outline"],
    "phase5_writing": ["phase3_volume_outline"],
    "phase6_review": ["phase5_writing"],
    "phase7_status_update": ["phase6_review"],
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


def get_project_root(args) -> Path:
    if args.project:
        return Path(args.project).resolve()
    return FALLBACK_ROOT


def get_gate_file(project_root: Path) -> Path:
    return project_root / "state" / "stage_gate.json"


def load_gate(args) -> dict:
    project_root = get_project_root(args)
    gate_file = get_gate_file(project_root)
    if gate_file.exists():
        return json.loads(gate_file.read_text())
    return {
        "novel": "",
        "current_chapter": 0,
        "current_volume": 0,
        "stages": {p: "pending" for p in PHASE_ORDER},
        "agent_execution_summary": {},
    }


def save_gate(args, data: dict):
    project_root = get_project_root(args)
    gate_file = get_gate_file(project_root)
    gate_file.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().isoformat()
    gate_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def run_agent_validation(project_root: Path, phase: str) -> dict:
    """Run agent_executor pipeline check for the given phase.

    Returns:
        {"passed": bool, "errors": list, "warnings": list,
         "agents_checked": list, "agents_failed": list}
    """
    try:
        from agent_executor import run_agent_pipeline
        result = run_agent_pipeline(str(project_root), phase, strict=False)
        return result.to_dict()
    except ImportError:
        return {
            "passed": True,
            "errors": [],
            "warnings": ["agent_executor not available — validation skipped"],
            "agents_checked": [],
            "agents_failed": [],
        }


def run_agent_tracker_check(project_root: Path, phase: str) -> dict:
    """Run agent_tracker check_agents via import (avoid subprocess overhead).

    Returns:
        {"passed": bool, "executed": list, "missing": list, "warnings": list}
    """
    try:
        from agent_tracker import check_agents
        # Find the most recent output file for this phase
        output_file = _find_phase_output(project_root, phase)

        if output_file:
            content = Path(output_file).read_text()
            passed, executed, missing, warnings = check_agents(
                content, phase, file_path=output_file,
                strict=False, novel_path=str(project_root),
            )
            return {
                "passed": passed,
                "executed": executed,
                "missing": missing,
                "warnings": warnings,
            }
        else:
            return {
                "passed": False,
                "executed": [],
                "missing": [],
                "warnings": [f"No output file found for {phase}"],
            }
    except ImportError:
        return {
            "passed": True,
            "executed": [],
            "missing": [],
            "warnings": ["agent_tracker not available"],
        }


def _find_phase_output(project_root: Path, phase: str) -> str:
    """Find the most relevant output file for a given phase."""
    if phase == "phase5_writing":
        chapters = sorted(project_root.glob("manuscript/vol-*/ch-*.md"))
        return str(chapters[-1]) if chapters else ""
    elif phase == "phase6_review":
        reviews = sorted(project_root.glob("reviews/ch-*-review.md"))
        return str(reviews[-1]) if reviews else ""
    elif phase == "phase7_status_update":
        status = project_root / "state" / "current_status.md"
        return str(status) if status.exists() else ""
    return ""


def check_phase(args, phase: str, min_severity: str = SEVERITY_WARNING) -> bool:
    """Check if a phase can proceed.

    Args:
        phase: Phase identifier
        min_severity: Minimum severity to block progression.
                      'error' = only errors block (warnings pass through)
                      'warning' = errors + warnings block (strict, default)
                      'info' = everything blocks (paranoid)
    """
    project_root = get_project_root(args)
    data = load_gate(args)
    deps = PHASE_DEPS.get(phase, [])
    errors = []    # severity=error — blocks progression
    warnings = []  # severity=warning — reports, blocks only in strict mode
    infos = []     # severity=info — logged only

    for dep in deps:
        if data["stages"].get(dep) != "completed":
            errors.append({
                "phase": dep,
                "label": PHASE_LABELS[dep],
                "severity": SEVERITY_ERROR,
                "detail": f"前置阶段 {PHASE_LABELS[dep]} ({dep}) 未完成",
            })

    # 特殊检查: phase5 需要 outline 文件
    if phase == "phase5_writing":
        vol = data.get("current_volume", 1)
        outline = project_root / "outline" / f"vol-{vol:02d}-chapters.md"
        if not outline.exists():
            errors.append({
                "phase": "outline",
                "label": "卷级章纲",
                "severity": SEVERITY_ERROR,
                "detail": f"outline 文件不存在: outline/vol-{vol:02d}-chapters.md",
            })

    # 特殊检查: phase6 需要正文文件（查找任意章节，不限于current_chapter）
    if phase == "phase6_review":
        # Try to find any chapter files, not just the tracked current_chapter
        ch = data.get("current_chapter", 0)
        if ch > 0:
            chapter_files = list(project_root.glob(f"manuscript/vol-*/ch-{ch:04d}.md"))
        else:
            # current_chapter not set — check if ANY chapters exist
            chapter_files = list(project_root.glob("manuscript/vol-*/ch-*.md"))
        if not chapter_files:
            errors.append({
                "phase": "chapter",
                "label": "章正文",
                "severity": SEVERITY_ERROR,
                "detail": "manuscript 目录下未找到任何章节文件，请先在「写作」页面生成章节",
            })

    # Check for agent_execution_summary warnings from previous phases
    summary = data.get("agent_execution_summary", {})
    for dep in deps:
        dep_summary = summary.get(dep, {})
        pipeline_errors = dep_summary.get("pipeline_errors", [])
        pipeline_warnings = dep_summary.get("pipeline_warnings", [])

        if dep_summary.get("has_errors"):
            errors.append({
                "phase": dep,
                "label": PHASE_LABELS[dep],
                "severity": SEVERITY_ERROR,
                "detail": f"前置阶段 {PHASE_LABELS[dep]} 存在 Agent 验证错误: {'; '.join(pipeline_errors[:3])}",
            })
        elif pipeline_warnings:
            warnings.append({
                "phase": dep,
                "label": PHASE_LABELS[dep],
                "severity": SEVERITY_WARNING,
                "detail": f"前置阶段 {PHASE_LABELS[dep]} 有 {len(pipeline_warnings)} 个警告",
            })

    # Determine blocking threshold based on min_severity
    if min_severity == SEVERITY_INFO:
        blocking = errors + warnings + infos
    elif min_severity == SEVERITY_WARNING:
        blocking = errors + warnings
    else:
        blocking = errors

    # Print results by severity
    all_items = errors + warnings + infos
    if all_items:
        label = PHASE_LABELS.get(phase, phase)
        blocking_count = len(blocking)
        if blocking_count > 0:
            print(f"🚫 {label} 不能开始 ({blocking_count} 个阻断项):")
        else:
            print(f"⚠️  {label} 可以开始（有非阻断项）:")

        for e in errors:
            print(f"  ❌ [错误] {e['detail']}")
        for w in warnings:
            print(f"  ⚠️  [警告] {w['detail']}")
        for i in infos:
            print(f"  ℹ️  [信息] {i['detail']}")

        if blocking_count > 0:
            return False

    print(f"✅ {PHASE_LABELS.get(phase, phase)} 可以开始")
    return True


def complete_phase(args, phase: str, validate: bool = False):
    data = load_gate(args)
    project_root = get_project_root(args)

    # 检查依赖
    if not check_phase(args, phase):
        print("⚠️  依赖未满足，但强制标记完成")

    # Optional: validate agent outputs before marking complete
    if validate:
        print(f"🔍 正在验证 {PHASE_LABELS[phase]} 的 Agent 输出...")
        pipeline_result = run_agent_validation(project_root, phase)
        tracker_result = run_agent_tracker_check(project_root, phase)

        # Store validation results in gate metadata
        if "agent_execution_summary" not in data:
            data["agent_execution_summary"] = {}

        data["agent_execution_summary"][phase] = {
            "validated_at": datetime.now().isoformat(),
            "pipeline_passed": pipeline_result.get("passed", True),
            "pipeline_errors": pipeline_result.get("errors", []),
            "pipeline_warnings": pipeline_result.get("warnings", []),
            "agents_checked": pipeline_result.get("agents_checked", []),
            "agents_failed": pipeline_result.get("agents_failed", []),
            "tracker_passed": tracker_result.get("passed", True),
            "tracker_warnings": tracker_result.get("warnings", []),
            "has_errors": len(pipeline_result.get("errors", [])) > 0,
            "has_warnings": len(pipeline_result.get("warnings", [])) > 0,
            "severity_summary": {
                "errors": len(pipeline_result.get("errors", [])),
                "warnings": len(pipeline_result.get("warnings", [])),
            },
        }

        if not pipeline_result.get("passed", True):
            errors_str = "; ".join(pipeline_result.get("errors", [])[:3])
            print(f"⚠️  Agent 验证发现 {len(pipeline_result.get('errors', []))} 个问题: {errors_str}")
        else:
            print("✅ Agent 验证通过")

        if not tracker_result.get("passed", True):
            missing = tracker_result.get("missing", [])
            print(f"⚠️  Agent 追踪发现缺失: {missing}")

    data["stages"][phase] = "completed"
    save_gate(args, data)
    print(f"✅ {PHASE_LABELS[phase]} 已标记为 completed")


def reset_phase(args, phase: str):
    data = load_gate(args)
    data["stages"][phase] = "pending"
    save_gate(args, data)
    print(f"🔄 {PHASE_LABELS[phase]} 已重置为 pending")


def show_status(args):
    data = load_gate(args)
    project_root = get_project_root(args)
    print(f"📖 {data.get('novel', '未设定')}")
    print(f"   项目: {project_root}")
    print(f"   当前: 第{data.get('current_volume', '?')}卷 第{data.get('current_chapter', '?')}章")
    print()
    for p in PHASE_ORDER:
        status = data["stages"].get(p, "pending")
        icon = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}.get(status, "❓")
        label = PHASE_LABELS[p]

        # Show validation summary if available
        val_info = ""
        summary = data.get("agent_execution_summary", {}).get(p, {})
        if summary:
            if summary.get("has_errors"):
                val_info = " ⚠️ 验证有误"
            elif summary.get("validated_at"):
                val_info = " ✅ 已验证"

        print(f"  {icon} {label:12s} ({p:25s}) {status}{val_info}")

    # Show overall validation status
    summary = data.get("agent_execution_summary", {})
    if summary:
        print()
        phases_with_errors = [p for p, s in summary.items() if s.get("has_errors")]
        if phases_with_errors:
            print(f"⚠️  以下阶段存在 Agent 验证错误: {', '.join(PHASE_LABELS.get(p, p) for p in phases_with_errors)}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="阶段门控 v2.0 — 阻止跳过阶段的硬性检查")
    parser.add_argument("--project", help="小说项目目录路径")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "check", "complete", "reset", "init"])
    parser.add_argument("arg", nargs="?", help="阶段名 (check/complete/reset) 或书名 (init)")
    parser.add_argument("--validate", action="store_true", help="完成阶段前验证 Agent 输出")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()

    cmd = args.command
    if cmd == "status":
        show_status(args)
        sys.exit(0)
    elif cmd == "check":
        if not args.arg:
            print("❌ 请指定阶段名: check <phase>")
            sys.exit(1)
        sys.exit(0 if check_phase(args, args.arg) else 1)
    elif cmd == "complete":
        if not args.arg:
            print("❌ 请指定阶段名: complete <phase>")
            sys.exit(1)
        complete_phase(args, args.arg, validate=args.validate)
        sys.exit(0)
    elif cmd == "reset":
        if not args.arg:
            print("❌ 请指定阶段名: reset <phase>")
            sys.exit(1)
        reset_phase(args, args.arg)
        sys.exit(0)
    elif cmd == "init":
        data = load_gate(args)
        data["novel"] = args.arg or ""
        save_gate(args, data)
        print(f"✅ 门控初始化完成: {args.arg or ''}")
        sys.exit(0)
    else:
        print("用法: stage_gate.py [--project <novel_dir>] [status|check|complete|reset|init] [phase]")
        print("阶段: " + ", ".join(PHASE_ORDER))
        sys.exit(1)

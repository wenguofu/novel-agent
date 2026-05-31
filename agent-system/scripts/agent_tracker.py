#!/usr/bin/env python3
"""Agent 运行追踪 — 确保每个阶段必需Agent全部执行 (v2.0)

Enhanced with:
- Output file verification (existence + non-zero size)
- Schema validation via agent_executor.validate_agent_output()
- Execution log recording to state/agent_execution_log.json
- New CLI flags: --exec-log, --prereqs, --validate

用法:
  python3 agent_tracker.py <chapter_or_review_file.md>
  python3 agent_tracker.py --stage <phase> <chapter_or_review_file.md>
  python3 agent_tracker.py --stage <phase> <file> --validate --strict
  python3 agent_tracker.py --stage <phase> <file> --exec-log
  python3 agent_tracker.py --prereqs --agent <name> --project <novel_path>
  python3 agent_tracker.py --list-stages
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 阶段 → 必需Agent 映射 ──────────────────────────

STAGE_AGENTS = {
    "phase1_opening": ["总主编剧", "类型规则", "世界观设定", "人物"],
    "phase2_arc": ["总主编剧", "长线剧情", "类型规则"],
    "phase3_volume_outline": ["总主编剧", "类型规则", "世界观设定", "长线剧情"],
    "phase4_chapter_planning": ["总主编剧", "章节规划"],
    "phase5_writing": ["正文写作"],
    "phase6_review": ["编辑审稿", "类型规则", "人物", "世界观设定", "合规审查"],
    "phase7_status_update": ["连载状态"],
}

# Agent名 → 在输出中的签名特征
AGENT_SIGNATURES = {
    "总主编剧": [
        r'总主编剧',
        r'卷级章纲|章节预排|本卷预计章节数',
        r'genre_bible.*约束',
        r'节奏规则表|类型节奏映射',
    ],
    "类型规则": [
        r'类型(?:承诺|检查|规则)',
        r'是否加载.*genre_bible',
        r'是否符合类型承诺',
        r'是否包含危机.*专业解释.*主角反差',
    ],
    "世界观设定": [
        r'世界观|世界设定|设定(?:检查|一致性)',
        r'是否违反世界观',
        r'是否新增设定',
        r'力量体系|地图|组织|限制条件',
    ],
    "人物": [
        r'人物(?:检查|一致性|档案|状态)',
        r'是否(?:符合|违反)人物',
        r'人物(?:关系|状态|行为)',
    ],
    "长线剧情": [
        r'长线剧情|主线|分卷',
        r'伏笔(?:检查|状态|变化)',
        r'full_story_arc|volume_plan',
    ],
    "章节规划": [
        r'章纲|章节规划',
        r'主要冲突|信息增量|结尾悬念',
        r'本章功能(?!.*审稿)',
    ],
    "正文写作": [
        r'正文[：:]',
        r'章节标题[：:]',
        r'(?:新增设定|人物状态变化|伏笔变化)',
        r'^#\s*第.{1,6}章',
    ],
    "编辑审稿": [
        r'审稿(?:结论|记录|维度)',
        r'评分卡|评分[：:]\s*\d',
        r'章节功能.*节奏.*信息密度',
        r'通过.*修改.*重写',
    ],
    "合规审查": [
        r'合规(?:检查|审查|结论|名称)',
        r'是否出现真实',
        r'alias_registry|别名',
        r'虚构别名|替代名',
    ],
    "连载状态": [
        r'连载状态|current_status',
        r'当前(?:剧情|状态)',
        r'资料更新|状态更新',
    ],
}


# ── 输出文件存在性检查 ─────────────────────────────

def verify_output_file(file_path: str) -> tuple[bool, str]:
    """Verify that an output file exists and is non-empty.

    Returns (exists_and_valid, reason)
    """
    fp = Path(file_path)
    if not fp.exists():
        return False, f"文件不存在: {file_path}"
    if fp.stat().st_size == 0:
        return False, f"文件为空: {file_path}"
    try:
        content = fp.read_text()
        if len(content.strip()) < 10:
            return False, f"文件内容过短 (<10字符): {file_path}"
    except Exception as e:
        return False, f"无法读取文件 {file_path}: {e}"
    return True, ""


def detect_agent(content: str, agent_name: str) -> bool:
    """检查Agent的签名是否出现在内容中 (regex签名匹配)"""
    patterns = AGENT_SIGNATURES.get(agent_name, [])
    if not patterns:
        return agent_name in content

    for pattern in patterns:
        if re.search(pattern, content, re.MULTILINE):
            return True
    return False


def get_current_stage() -> str:
    """从 stage_gate.json 读取当前阶段"""
    gate_path = PROJECT_ROOT / "state" / "stage_gate.json"
    if not gate_path.exists():
        return None

    gate = json.loads(gate_path.read_text())
    stages = gate.get("stages", {})

    order = ["phase1_opening", "phase2_arc", "phase3_volume_outline",
             "phase4_chapter_planning", "phase5_writing",
             "phase6_review", "phase7_status_update"]

    for phase in order:
        if stages.get(phase) in ("in_progress", "pending"):
            return phase

    return order[-1]


def validate_output_format(content: str, agent_name: str, strict: bool = False) -> dict:
    """Validate agent output against schema using agent_executor.

    Returns:
        {"valid": bool, "errors": list, "warnings": list}
    """
    try:
        from agent_executor import validate_agent_output, get_agent_schema
        schema = get_agent_schema(agent_name)
        if not schema:
            return {"valid": True, "errors": [], "warnings": [f"No schema for {agent_name}"]}
        result = validate_agent_output(content, agent_name, strict=strict)
        return result.to_dict()
    except ImportError:
        return {"valid": True, "errors": [], "warnings": ["agent_executor not available"]}


def record_execution(stage: str, agent_name: str, status: str, output_file: str = "",
                     validation_errors: list = None, novel_path: str = None):
    """Persist execution record to agent_execution_log.json."""
    record = {
        "agent_name": agent_name,
        "stage": stage,
        "start_time": datetime.now().isoformat(),
        "end_time": datetime.now().isoformat(),
        "status": status,
        "output_file": output_file,
        "validation_errors": validation_errors or [],
        "schema_version": "1.0",
    }

    if novel_path:
        log_dir = Path(novel_path) / "state"
    else:
        log_dir = PROJECT_ROOT / "state"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "agent_execution_log.json"

    records = []
    if log_path.exists():
        try:
            records = json.loads(log_path.read_text())
        except (json.JSONDecodeError, IOError):
            records = []

    records.append(record)
    log_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return record


def check_agents(content: str, stage: str, file_path: str = None,
                 strict: bool = False, novel_path: str = None) -> tuple[bool, list, list, list]:
    """检查必需Agent是否全部执行。

    Performs three levels of checks:
    1. Regex signature matching (backwards compatible)
    2. Output file verification (if file_path provided)
    3. Schema validation (if agent_executor available)

    Returns: (全部通过, 已执行列表, 缺失列表, 警告列表)
    """
    required = STAGE_AGENTS.get(stage, [])
    if not required:
        return True, [], [], []

    executed = []
    missing = []
    warnings = []

    for agent_name in required:
        # Level 1: Signature check
        sig_ok = detect_agent(content, agent_name)

        # Level 2: File verification
        file_ok = True
        file_note = ""
        if file_path:
            file_ok, file_note = verify_output_file(file_path)

        # Level 3: Schema validation
        schema_valid = True
        schema_warnings = []
        try:
            from agent_executor import validate_agent_output
            result = validate_agent_output(content, agent_name, strict=strict)
            if not result.valid:
                schema_valid = False
                schema_warnings = result.errors + result.warnings
            else:
                schema_warnings = result.warnings
        except ImportError:
            schema_warnings = ["agent_executor not available — schema validation skipped"]

        # Determine overall status
        if sig_ok and file_ok:
            executed.append(agent_name)
            if schema_valid:
                record_status = "passed"
            else:
                record_status = "warning"
                warnings.append(
                    f"[{agent_name}] schema 验证不通过: {'; '.join(schema_warnings)}"
                )
        else:
            missing.append(agent_name)
            record_status = "failed"
            if not sig_ok:
                reasons = [f"签名未匹配"]
            if not file_ok:
                reasons = [file_note]
            if reasons:
                warnings.append(f"[{agent_name}] {'; '.join(reasons)}")

        # Record execution
        if novel_path:
            record_execution(
                stage=stage,
                agent_name=agent_name,
                status=record_status,
                output_file=file_path or "",
                validation_errors=[w for w in schema_warnings if not w.startswith("agent_executor")],
                novel_path=novel_path,
            )

    return len(missing) == 0, executed, missing, warnings


# ── 主入口 ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent 运行追踪 v2.0")
    parser.add_argument("file", nargs="?", help="要检查的文件")
    parser.add_argument("--stage", help="阶段标识 (e.g., phase5_writing)")
    parser.add_argument("--list-stages", action="store_true", help="列出所有阶段")
    parser.add_argument("--exec-log", action="store_true", help="追加执行记录")
    parser.add_argument("--prereqs", action="store_true", help="检查前置条件而非签名")
    parser.add_argument("--agent", help="指定 Agent 名称 (与 --prereqs 配合)")
    parser.add_argument("--project", help="小说项目根目录")
    parser.add_argument("--validate", action="store_true", help="启用 schema 验证")
    parser.add_argument("--strict", action="store_true", help="schema 警告也视为错误")

    args = parser.parse_args()

    if args.list_stages:
        for stage, agents in STAGE_AGENTS.items():
            label = {
                "phase1_opening": "开书",
                "phase2_arc": "长线剧情",
                "phase3_volume_outline": "卷级章纲",
                "phase4_chapter_planning": "章节规划",
                "phase5_writing": "正文写作",
                "phase6_review": "编辑审稿",
                "phase7_status_update": "状态更新",
            }.get(stage, stage)
            print(f"  {label} ({stage}): {', '.join(agents)}")
        sys.exit(0)

    if args.prereqs:
        if not args.agent or not args.project:
            print("❌ --prereqs 需要 --agent 和 --project 参数")
            sys.exit(1)
        try:
            from agent_executor import check_prerequisites, get_agent_schema
            result = check_prerequisites(args.agent, args.project)
            schema = get_agent_schema(args.agent)
            display = schema["display_name"] if schema else args.agent
            print(f"🔍 {display} 前置条件检查:")
            for inp in (schema["required_inputs"] if schema else []):
                status = "✅" if inp not in [m.split(" (")[0] for m in result.missing] else "❌"
                print(f"   {status} {inp}")
            if result.passed:
                print("✅ 所有前置条件满足")
            else:
                print("❌ 缺失文件:")
                for m in result.missing:
                    print(f"   → {m}")
            sys.exit(0 if result.passed else 1)
        except ImportError:
            print("⚠️  agent_executor 不可用，前置条件检查需要 agent_executor.py")
            sys.exit(1)

    if not args.file:
        print("用法: agent_tracker.py [--stage <phase>] <file.md>")
        print("      agent_tracker.py --list-stages")
        print("      agent_tracker.py --prereqs --agent <name> --project <path>")
        sys.exit(1)

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"❌ 文件不存在: {filepath}")
        sys.exit(1)

    content = filepath.read_text()

    # 自动推断阶段
    stage = args.stage
    if not stage:
        stage = get_current_stage()
        if not stage:
            if "审稿" in filepath.name or "review" in filepath.name.lower():
                stage = "phase6_review"
            elif "manuscript" in str(filepath):
                stage = "phase5_writing"
            elif "outline" in str(filepath):
                stage = "phase3_volume_outline"
            else:
                stage = "phase1_opening"

    stage_label = {
        "phase1_opening": "阶段1·开书",
        "phase2_arc": "阶段2·长线剧情",
        "phase3_volume_outline": "阶段3·卷级章纲",
        "phase4_chapter_planning": "阶段4·章节规划",
        "phase5_writing": "阶段5·正文写作",
        "phase6_review": "阶段6·编辑审稿",
        "phase7_status_update": "阶段7·状态更新",
    }.get(stage, stage)

    # Run checks
    novel_path = args.project or str(PROJECT_ROOT)
    passed, executed, missing, warnings = check_agents(
        content, stage,
        file_path=str(filepath),
        strict=args.strict,
        novel_path=novel_path if args.exec_log else None,
    )

    print(f"🔍 Agent 运行检查: {stage_label}")
    print(f"   文件: {filepath.name}")
    print(f"   必需Agent: {len(STAGE_AGENTS.get(stage, []))}个")

    if args.validate:
        print(f"   Schema 验证: 启用{' (strict)' if args.strict else ' (宽松)'}")

    print()

    for agent_name in STAGE_AGENTS.get(stage, []):
        status = "✅" if agent_name in executed else "❌"
        print(f"   {status} {agent_name}")

    if warnings:
        print(f"\n📝 警告:")
        for w in warnings:
            print(f"   ⚠️  {w}")

    print(f"\n{'='*50}")
    if passed:
        print(f"🟢 全部 {len(executed)} 个Agent已执行")
    else:
        print(f"🔴 缺失 {len(missing)} 个Agent: {', '.join(missing)}")
        print(f"\n⚠️  请补运行以下Agent后再进入下一阶段:")
        for agent_name in missing:
            print(f"   → {agent_name} Agent")

    sys.exit(0 if passed else 1)

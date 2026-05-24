#!/usr/bin/env python3
"""阶段门控 — 阻止跳过阶段的硬性检查

用法:
  python3 stage_gate.py --project <novel_dir> check <phase>
  python3 stage_gate.py --project <novel_dir> complete <phase>
  python3 stage_gate.py --project <novel_dir> status
  python3 stage_gate.py --project <novel_dir> reset <phase>
  python3 stage_gate.py --project <novel_dir> init <novel_name>

规则:
  - phase2 (长线剧情) 依赖 phase1 (开书) completed
  - phase3 (卷级章纲) 依赖 phase2 completed
  - phase4 (章节规划) 依赖 phase3 completed
  - phase5 (正文写作) 依赖 phase3 completed + outline 文件存在
  - phase6 (编辑审稿) 依赖 phase5 章正文存在
  - phase7 (状态更新) 依赖 phase6 completed

不传 --project 时，回退到旧行为 (agent-system/ 下查找 state/)。
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# ── 硬编码回退路径 (无 --project 时用) ──
FALLBACK_ROOT = Path(__file__).resolve().parent.parent

PHASE_ORDER = ["phase1_opening", "phase2_arc", "phase3_volume_outline",
               "phase4_chapter_planning", "phase5_writing",
               "phase6_review", "phase7_status_update"]

PHASE_DEPS = {
    "phase1_opening": [],
    "phase2_arc": ["phase1_opening"],
    "phase3_volume_outline": ["phase2_arc"],
    "phase4_chapter_planning": ["phase3_volume_outline"],
    "phase5_writing": ["phase3_volume_outline"],   # + outline file check
    "phase6_review": ["phase5_writing"],            # + chapter file check
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
    """根据 --project 参数确定项目根目录"""
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
    }


def save_gate(args, data: dict):
    project_root = get_project_root(args)
    gate_file = get_gate_file(project_root)
    gate_file.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().isoformat()
    gate_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def check_phase(args, phase: str) -> bool:
    project_root = get_project_root(args)
    data = load_gate(args)
    deps = PHASE_DEPS.get(phase, [])
    errors = []

    for dep in deps:
        if data["stages"].get(dep) != "completed":
            errors.append(f"  ❌ {PHASE_LABELS[dep]} ({dep}) 未完成")

    # 特殊检查: phase5 需要 outline 文件
    if phase == "phase5_writing":
        vol = data.get("current_volume", 1)
        outline = project_root / "outline" / f"vol-{vol:02d}-chapters.md"
        if not outline.exists():
            errors.append(f"  ❌ outline 文件不存在: {outline}")

    # 特殊检查: phase6 需要正文文件
    if phase == "phase6_review":
        ch = data.get("current_chapter", 0)
        chapter_files = list(project_root.glob(f"manuscript/vol-*/ch-{ch:04d}.md"))
        if not chapter_files:
            errors.append(f"  ❌ 章正文不存在: ch-{ch:04d}")

    if errors:
        print(f"🚫 {PHASE_LABELS[phase]} 不能开始:")
        for e in errors:
            print(e)
        return False

    print(f"✅ {PHASE_LABELS[phase]} 可以开始")
    return True


def complete_phase(args, phase: str):
    data = load_gate(args)
    # 检查依赖
    if not check_phase(args, phase):
        print("⚠️  依赖未满足，但强制标记完成")
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
        print(f"  {icon} {label:12s} ({p:25s}) {status}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="阶段门控 — 阻止跳过阶段的硬性检查")
    parser.add_argument("--project", help="小说项目目录路径 (如 novels/光头闲人闯阴阳古墓)")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "check", "complete", "reset", "init"])
    parser.add_argument("arg", nargs="?", help="阶段名 (check/complete/reset) 或书名 (init)")
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
        complete_phase(args, args.arg)
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

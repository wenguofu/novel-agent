#!/usr/bin/env python3
"""Agent 运行追踪 — 确保每个阶段必需Agent全部执行

问题: 多Agent流程中经常有Agent被跳过，LLM不自知。
解决: 每阶段定义必须运行的Agent列表，脚本检测是否全部到位。

用法:
  python3 agent_tracker.py <chapter_or_review_file.md>
  python3 agent_tracker.py --stage <phase> <chapter_or_review_file.md>

阶段 → Agent 映射:
  phase1 (开书):        总主编剧, 类型规则, 世界观设定, 人物
  phase2 (长线剧情):    总主编剧, 长线剧情, 类型规则
  phase3 (卷级章纲):    总主编剧, 类型规则, 世界观设定, 长线剧情
  phase4 (章节规划):    总主编剧, 章节规划
  phase5 (正文写作):    正文写作
  phase6 (编辑审稿):    编辑审稿, 类型规则, 人物, 世界观设定, 合规审查
  phase7 (状态更新):    连载状态
"""

import re
import json
import sys
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
# 每个Agent在产出的markdown中应该留下可检测的痕迹
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
        r'本章功能(?!.*审稿)',  # 不是审稿中的"本章功能"
    ],
    "正文写作": [
        r'正文[：:]',
        r'章节标题[：:]',
        r'(?:新增设定|人物状态变化|伏笔变化)',
        r'^#\s*第.{1,6}章',  # 纯正文格式: # 第X章
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

# ── 检测逻辑 ────────────────────────────────────────

def detect_agent(content: str, agent_name: str) -> bool:
    """检查Agent的签名是否出现在内容中"""
    patterns = AGENT_SIGNATURES.get(agent_name, [])
    if not patterns:
        # fallback: 直接搜索agent名
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
    
    # 找到最后一个 in_progress 或第一个 pending
    order = ["phase1_opening", "phase2_arc", "phase3_volume_outline",
             "phase4_chapter_planning", "phase5_writing",
             "phase6_review", "phase7_status_update"]
    
    for phase in order:
        if stages.get(phase) in ("in_progress", "pending"):
            return phase
    
    return order[-1]  # 默认最后阶段


def check_agents(content: str, stage: str) -> tuple[bool, list, list]:
    """检查必需Agent是否全部执行
    返回: (全部通过, 已执行列表, 缺失列表)
    """
    required = STAGE_AGENTS.get(stage, [])
    if not required:
        return True, [], []
    
    executed = []
    missing = []
    
    for agent in required:
        if detect_agent(content, agent):
            executed.append(agent)
        else:
            missing.append(agent)
    
    return len(missing) == 0, executed, missing


# ── 主入口 ──────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 agent_tracker.py <file.md>")
        print("      python3 agent_tracker.py --stage phase5_writing <file.md>")
        print("      python3 agent_tracker.py --list-stages")
        sys.exit(1)
    
    # --list-stages
    if sys.argv[1] == "--list-stages":
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
    
    # 解析参数
    stage = None
    filepath = None
    
    if sys.argv[1] == "--stage":
        if len(sys.argv) < 4:
            print("❌ 缺少参数: --stage <phase> <file>")
            sys.exit(1)
        stage = sys.argv[2]
        filepath = Path(sys.argv[3])
    else:
        filepath = Path(sys.argv[1])
    
    if not filepath.exists():
        print(f"❌ 文件不存在: {filepath}")
        sys.exit(1)
    
    content = filepath.read_text()
    
    # 自动推断阶段
    if not stage:
        stage = get_current_stage()
        if not stage:
            # 根据文件内容推断
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
    
    passed, executed, missing = check_agents(content, stage)
    
    print(f"🔍 Agent 运行检查: {stage_label}")
    print(f"   文件: {filepath.name}")
    print(f"   必需Agent: {len(STAGE_AGENTS.get(stage, []))}个\n")
    
    for agent in STAGE_AGENTS.get(stage, []):
        status = "✅" if agent in executed else "❌"
        print(f"   {status} {agent}")
    
    print(f"\n{'='*50}")
    if passed:
        print(f"🟢 全部 {len(executed)} 个Agent已执行")
    else:
        print(f"🔴 缺失 {len(missing)} 个Agent: {', '.join(missing)}")
        print(f"\n⚠️  请补运行以下Agent后再进入下一阶段:")
        for agent in missing:
            print(f"   → {agent} Agent")
    
    sys.exit(0 if passed else 1)

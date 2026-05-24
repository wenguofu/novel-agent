#!/usr/bin/env python3
"""章节节奏规则自动检查

扫描最近N章的 outline + review 记录，标记违反节奏规则的章节。

规则（来自 workflow.md 阶段3）:
  R1: 每 3-5 章至少一次主角化解大危机
  R2: 每 10-20 章至少一次副本信息升级
  R3: 相邻两章功能不得完全相同
  R4: 40章后不得连续2章以上为低压章节(查证/调查/铺垫)
  R5: 连续3章不得无信息增量

用法:
  python3 rhythm_check.py [--range N]    # 扫描最近N章，默认20
  python3 rhythm_check.py --vol X        # 扫描第X卷全部章节
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 低压功能类型（不应连续出现）
LOW_TENSION_FUNCTIONS = ["调查", "查证", "铺垫", "过渡", "日常", "介绍", "回忆"]

# 高压功能类型（主角化解危机相关）
HIGH_TENSION_FUNCTIONS = ["危机", "对抗", "化解", "高潮", "决战", "逆转", "逃生", "反击"]

# 信息升级功能类型
INFO_UPGRADE_FUNCTIONS = ["揭秘", "升级", "突破", "真相", "觉醒", "新能力", "世界观扩展"]


def load_outline(vol: int) -> dict:
    """解析 vol-XX-chapters.md 提取章节功能列表"""
    outline_path = PROJECT_ROOT / "outline" / f"vol-{vol:02d}-chapters.md"
    if not outline_path.exists():
        return {}
    
    text = outline_path.read_text()
    chapters = {}
    
    # 解析章节信息：先找章节编号，再提取功能
    # 匹配模式: | ch-0120 | 章名 | 描述 | 功能 | ...
    for line in text.split("\n"):
        # 匹配表格行: | ch-0120 | ... | 功能 | ...
        if "ch-" not in line.lower() and not re.match(r'^\|\s*\d+', line):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        
        # 尝试提取章节号
        ch_id = None
        for p in parts:
            m = re.search(r'ch-(\d+)', p, re.IGNORECASE)
            if m:
                ch_id = int(m.group(1))
                break
            m = re.match(r'^(\d{3,4})$', p)
            if m:
                ch_id = int(m.group(1))
                break
        
        if ch_id is None:
            continue
        
        # 提取功能描述
        function = parts[-1] if len(parts) > 3 else ""
        chapters[ch_id] = {
            "raw": line.strip(),
            "function": function,
        }
    
    return chapters


def scan_reviews() -> dict:
    """扫描 reviews/ 目录提取章节功能标记"""
    reviews_dir = PROJECT_ROOT / "reviews"
    if not reviews_dir.exists():
        return {}
    
    chapters = {}
    for f in sorted(reviews_dir.glob("ch-*-review.md")):
        m = re.search(r'ch-(\d+)-review', f.name)
        if not m:
            continue
        ch_id = int(m.group(1))
        text = f.read_text()
        
        # 尝试从 review 中提取功能描述
        function = ""
        for line in text.split("\n"):
            if "功能" in line or "章节功能" in line:
                function = line.split(":", 1)[-1].strip() if ":" in line else line.strip()
                break
        
        chapters[ch_id] = {"function": function, "has_review": True}
    
    return chapters


def check_rhythm(chapters: dict, vol: int, start_ch: int = 1):
    """执行节奏规则检查"""
    violations = []
    
    if not chapters:
        print("⚠️  未找到章节功能数据，请确保 outline 或 reviews 可用")
        return violations
    
    sorted_chs = sorted(chapters.keys())
    if not sorted_chs:
        return violations
    
    # 过滤指定范围
    target_chs = [ch for ch in sorted_chs if ch >= start_ch]
    if not target_chs:
        print(f"⚠️  第{vol}卷没有第{start_ch}章及之后的章节")
        return violations
    
    # R1: 每3-5章至少一次主角化解大危机
    print("📋 R1: 主角化解大危机检查 (每3-5章)")
    last_crisis = None
    for i, ch in enumerate(target_chs):
        func = chapters[ch].get("function", "")
        if any(kw in func for kw in ["危机", "化解", "逆转", "高潮", "反击"]):
            if last_crisis is not None and ch - last_crisis > 5:
                v = f"  ⚠️ ch-{last_crisis:04d} → ch-{ch:04d} 间隔{ch - last_crisis}章 > 5章上限"
                violations.append(v)
                print(v)
            last_crisis = ch
    if last_crisis and target_chs[-1] - last_crisis > 5:
        v = f"  ⚠️ 最后危机ch-{last_crisis:04d}距今{target_chs[-1] - last_crisis}章"
        violations.append(v)
        print(v)
    if not violations or all("R1" not in x for x in str(violations)):
        print("  ✅ 通过")
    
    # R2: 每10-20章至少一次副本信息升级
    print("\n📋 R2: 信息升级检查 (每10-20章)")
    last_upgrade = None
    for ch in target_chs:
        func = chapters[ch].get("function", "")
        if any(kw in func for kw in INFO_UPGRADE_FUNCTIONS):
            if last_upgrade is not None and ch - last_upgrade > 20:
                v = f"  ⚠️ ch-{last_upgrade:04d} → ch-{ch:04d} 间隔{ch - last_upgrade}章 > 20章上限"
                violations.append(v)
                print(v)
            last_upgrade = ch
    if not last_upgrade or target_chs[-1] - last_upgrade > 20:
        v = f"  ⚠️ 最后升级距今{target_chs[-1] - (last_upgrade or target_chs[0])}章"
        violations.append(v)
        print(v)
    if not any("R2" in str(x) for x in violations):
        print("  ✅ 通过")
    
    # R3: 相邻两章功能不得完全相同
    print("\n📋 R3: 相邻功能重复检查")
    for i in range(len(target_chs) - 1):
        ch_a, ch_b = target_chs[i], target_chs[i+1]
        func_a = chapters[ch_a].get("function", "").strip()
        func_b = chapters[ch_b].get("function", "").strip()
        if func_a and func_b and func_a == func_b:
            v = f"  ⚠️ ch-{ch_a:04d} 与 ch-{ch_b:04d} 功能相同: {func_a}"
            violations.append(v)
            print(v)
    if not any("R3" in str(x) for x in violations):
        print("  ✅ 通过")
    
    # R4: 40章后不得连续2章以上低压
    print("\n📋 R4: 低压章节连续性检查")
    low_streak = 0
    for ch in target_chs:
        if ch < 40:
            continue
        func = chapters[ch].get("function", "")
        is_low = any(kw in func for kw in LOW_TENSION_FUNCTIONS)
        if is_low:
            low_streak += 1
        else:
            if low_streak >= 3:
                v = f"  ⚠️ ch-{ch-low_streak:04d} 起连续{low_streak}章低压"
                violations.append(v)
                print(v)
            low_streak = 0
    if low_streak >= 3:
        v = f"  ⚠️ 末尾连续{low_streak}章低压"
        violations.append(v)
        print(v)
    if not any("R4" in str(x) for x in violations):
        print("  ✅ 通过")
    
    # R5: 连续3章不得无信息增量
    print("\n📋 R5: 信息增量连续性检查")
    # 通过章节功能判断 — 没有明确的"信息增量"标记视为风险
    info_rich = [any(kw in chapters[ch].get("function", "") 
                     for kw in ["揭示", "发现", "新", "变化", "转折", "升级", "反转"])
                 for ch in target_chs]
    no_info_streak = 0
    for i, (ch, has_info) in enumerate(zip(target_chs, info_rich)):
        if not has_info:
            no_info_streak += 1
        else:
            if no_info_streak >= 3:
                v = f"  ⚠️ ch-{target_chs[i-no_info_streak]:04d} 起连续{no_info_streak}章无明显信息增量"
                violations.append(v)
                print(v)
            no_info_streak = 0
    if no_info_streak >= 3:
        v = f"  ⚠️ 末尾连续{no_info_streak}章无明显信息增量"
        violations.append(v)
        print(v)
    if not any("R5" in str(x) for x in violations):
        print("  ✅ 通过")
    
    return violations


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="章节节奏规则检查")
    parser.add_argument("--range", type=int, default=20, help="扫描最近N章")
    parser.add_argument("--vol", type=int, default=2, help="卷号")
    parser.add_argument("--start", type=int, default=0, help="起始章节(0=自动)")
    args = parser.parse_args()
    
    # 尝试加载 stage_gate
    gate_path = PROJECT_ROOT / "state" / "stage_gate.json"
    vol = args.vol
    if gate_path.exists():
        gate = json.loads(gate_path.read_text())
        vol = gate.get("current_volume", args.vol)
    
    outline_data = load_outline(vol)
    review_data = scan_reviews()
    
    # 合并数据: review 优先
    chapters = {**outline_data, **review_data}
    
    if args.start > 0:
        start_ch = args.start
    else:
        # 自动: 当前章 - range
        current = gate.get("current_chapter", 0) if gate_path.exists() else 0
        start_ch = max(1, current - args.range) if current > 0 else 1
    
    print(f"🔍 节奏检查: 第{vol}卷, ch-{start_ch:04d} 起")
    print(f"   章数: {len(chapters)} 章有功能数据\n")
    
    violations = check_rhythm(chapters, vol, start_ch)
    
    print(f"\n{'='*40}")
    if violations:
        print(f"🔴 发现 {len(violations)} 个节奏违规")
    else:
        print(f"🟢 所有节奏规则通过")

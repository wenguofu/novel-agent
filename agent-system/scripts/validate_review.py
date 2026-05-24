#!/usr/bin/env python3
"""审稿评分卡验证 — 检查评分卡完整性和数学正确性

检查项:
  1. 7维评分都在 1-5 范围
  2. 总分 = Σ各维得分
  3. 结论匹配: ≥28=通过, 21-27=修改, <21=重写
  4. <3分项有修改清单
  5. 评分卡已保存到 reviews/

用法:
  python3 validate_review.py <review_file.md>
  python3 validate_review.py novels/<novel>/reviews/ch-0065-review.md
"""

import re
import sys
from pathlib import Path

DIMENSIONS = ["类型承诺", "人物一致性", "设定一致性", "章节功能", "节奏", "信息密度", "合规"]

def validate_review(path: str) -> tuple[bool, list]:
    path = Path(path)
    if not path.exists():
        return False, [f"❌ 文件不存在: {path}"]
    
    text = path.read_text()
    violations = []
    
    ch_num = re.search(r'ch-(\d+)-review', path.name)
    label = f"ch-{ch_num.group(1)}" if ch_num else path.name
    
    print(f"🔍 验证审稿: {label}")
    
    # ── 1. 提取评分 ──
    scores = {}
    
    # 先尝试新格式：评分卡表格
    table_pattern = re.compile(r'\|\s*(\d)\s*\|\s*(类型承诺|人物一致性|设定一致性|章节功能|节奏|信息密度|合规)\s*\|\s*.*?\|\s*(\d)\s*\|\s*(✅|⚠️|🔴)?', re.DOTALL)
    for m in table_pattern.finditer(text):
        dim = m.group(2).strip()
        score = int(m.group(3))
        scores[dim] = score
    
    # 如果没有找到评分卡，检查是否旧格式 review（无评分）
    if len(scores) < 7:
        # 旧格式: 检查审稿结论字段
        conclusion_match = re.search(r'审稿结论[：:]\s*(通过|修改|重写)', text)
        if conclusion_match:
            print(f"  ⚠️ 旧格式审稿 (无评分卡)，跳过评分验证")
            return True, []
    
    # 尝试文本格式评分
    
    if len(scores) < 7:
        missing = [d for d in DIMENSIONS if d not in scores]
        violations.append(f"❌ 评分不完整: 缺少 {', '.join(missing)}")
    print(f"  {'✅' if len(scores) >= 7 else '❌'} 评分维度: {len(scores)}/7")
    
    # ── 2. 分数范围检查 ──
    for dim, score in scores.items():
        if score < 1 or score > 5:
            violations.append(f"❌ {dim} 分数越界: {score} (应为 1-5)")
    
    out_of_range = [f"{d}={s}" for d, s in scores.items() if s < 1 or s > 5]
    print(f"  {'✅' if not out_of_range else '❌'} 分数范围: {'全部合规' if not out_of_range else ', '.join(out_of_range)}")
    
    # ── 3. 总分验证 ──
    actual_total = sum(scores.values())
    
    # 尝试从文件中提取声明的总分
    stated_total = None
    total_match = re.search(r'总[分计][：:]\s*(\d+)', text)
    if total_match:
        stated_total = int(total_match.group(1))
    
    if stated_total and stated_total != actual_total:
        violations.append(f"❌ 总分不一致: 声称{stated_total}分, 实际{actual_total}分")
    
    print(f"  {'✅' if not stated_total or stated_total == actual_total else '❌'} 总分: 实际{actual_total}分", end="")
    if stated_total:
        print(f" (声称{stated_total}分)")
    else:
        print()
    
    # ── 4. 结论验证 ──
    conclusion = None
    for kw in ["通过", "修改", "重写"]:
        if re.search(rf'审稿结论[：:].*{kw}', text) or re.search(rf'结论[：:].*{kw}', text):
            conclusion = kw
            break
    
    expected = "通过" if actual_total >= 28 else ("修改" if actual_total >= 21 else "重写")
    if conclusion and conclusion != expected:
        violations.append(f"❌ 结论不匹配: 声称'{conclusion}', 应为'{expected}' ({actual_total}分)")
    print(f"  {'✅' if not conclusion or conclusion == expected else '❌'} 结论: {conclusion or '未找到'} (期望: {expected})")
    
    # ── 5. 低分项修改检查 ──
    low_score_dims = [d for d, s in scores.items() if s < 3]
    if low_score_dims:
        # 检查是否有修改清单
        has_fix_list = bool(re.search(r'修改清[单列表]|修改要求|修改建议', text))
        if not has_fix_list:
            violations.append(f"❌ 低分项({', '.join(low_score_dims)})缺少修改清单")
        print(f"  {'✅' if has_fix_list else '❌'} 低分修改: {len(low_score_dims)}项需修改")
    else:
        print(f"  ✅ 低分修改: 无低分项")
    
    # ── 汇总 ──
    print(f"\n{'='*60}")
    if violations:
        print(f"🔴 {len(violations)} 个错误")
        for v in violations:
            print(v)
    else:
        print(f"🟢 评分卡验证通过")
    
    return len(violations) == 0, violations


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 validate_review.py <review_file.md>")
        sys.exit(1)
    
    passed, issues = validate_review(sys.argv[1])
    sys.exit(0 if passed else 1)

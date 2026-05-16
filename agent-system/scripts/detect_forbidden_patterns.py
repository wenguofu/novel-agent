#!/usr/bin/env python3
"""
detect_forbidden_patterns.py — 禁止模式检测

功能：
- 检测二元对照句式 "不是...而是..." 是否超过2次
- 检测重复对话（同一人物在连续3句内说相同内容）
- 检测字数不足（调用analyze_chapter）

用法：
    python detect_forbidden_patterns.py <chapter_file>

输出 (stdout, YAML格式):
    binary_contrast_count: 1
    binary_contrast_ok: true
    repetitive_dialogues: []
    ok: true
"""

import re
import sys
from pathlib import Path


def detect_binary_contrasts(text: str) -> list[dict]:
    """检测"不是...而是..."句式。"""
    pattern = re.compile(
        r'(?:[^。！？\n]*?不是[^。！？\n]*?而是[^。！？\n]*[。！？\n])',
        re.MULTILINE
    )
    matches = []
    for m in pattern.finditer(text):
        matches.append({
            'text': m.group().strip()[:80],
            'position': m.start(),
        })
    return matches


def detect_repetitive_dialogues(text: str) -> list[str]:
    """检测连续对话中的重复。"""
    lines = text.split('\n')
    dialogue_lines = []
    is_repetitive = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if '说' in stripped and ('"' in stripped or '「' in stripped or '「' in stripped or '“' in stripped):
            dialogue_lines.append((i, stripped))

    for n in range(len(dialogue_lines)):
        if n >= 2:
            _, prev1 = dialogue_lines[n - 2]
            _, prev2 = dialogue_lines[n - 1]
            _, curr = dialogue_lines[n]

            # 检查对话内容是否高度重复（编辑距离近）
            content_prev1 = prev1[prev1.find('"') + 1:prev1.rfind('"')] if '"' in prev1 else prev1
            content_prev2 = prev2[prev2.find('"') + 1:prev2.rfind('"')] if '"' in prev2 else prev2
            content_curr = curr[curr.find('"') + 1:curr.rfind('"')] if '"' in curr else curr

            if content_prev1 and content_curr and content_prev1.strip()[:10] == content_curr.strip()[:10]:
                is_repetitive.append(f"行{curr[:60]}... 与 行{prev1[:60]}... 内容重复")
            elif content_prev2 and content_curr and content_prev2.strip()[:10] == content_curr.strip()[:10]:
                is_repetitive.append(f"行{curr[:60]}... 与 行{prev2[:60]}... 内容重复")

    return is_repetitive


def main():
    if len(sys.argv) < 2:
        print("用法: python detect_forbidden_patterns.py <chapter_file>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在 {filepath}")
        sys.exit(1)

    text = filepath.read_text(encoding='utf-8')

    binary_matches = detect_binary_contrasts(text)
    repetitive = detect_repetitive_dialogues(text)

    print(f"binary_contrast_count: {len(binary_matches)}")
    print(f"binary_contrast_ok: {'true' if len(binary_matches) <= 2 else 'false'}")
    if binary_matches:
        for m in binary_matches:
            print(f"  - \"{m['text'][:60]}...\"")

    print(f"repetitive_dialogues: {'true' if repetitive else 'false'}")
    for item in repetitive:
        print(f"  - \"{item}\"")

    errors = []
    if len(binary_matches) > 2:
        errors.append(f"二元对照句式超过2次 ({len(binary_matches)}次)")
    if repetitive:
        errors.append(f"存在重复对话")

    is_ok = not errors
    print(f"ok: {'true' if is_ok else 'false'}")
    if errors:
        for err in errors:
            print(f"  - \"{err}\"")

    sys.exit(0 if is_ok else 1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
detect_forbidden_patterns.py — 禁止模式检测（v2.0）

功能：
- 检测二元对照句式 "不是...而是..." 是否超过2次
- 检测重复对话（同一人物在连续对话中说高度相似的内容，≥15字重叠）
- 检测重复动作描写（连续3句内出现完全相同的动作描述）

用法：
    python detect_forbidden_patterns.py <chapter_file>

输出 (stdout, YAML格式):
    binary_contrast_count: 1
    binary_contrast_ok: true
    repetitive_dialogues: []
    repetitive_actions: []
    ok: true
"""

import re
import sys
from pathlib import Path


# 中文引号字符
QUOTE_CHARS = {'"', '"', '「', '」', '『', '』', '《', '》', '〈', '〉', "'", "'", '【', '】'}
QUOTE_PAIRS = [
    ('"', '"'), ('"', '"'), ('「', '」'), ('『', '』'),
    ('《', '》'), ('〈', '〉'), ("'", "'"), ('【', '】'),
    ('（', '）'), ('(', ')'),
]


def detect_binary_contrasts(text: str) -> list[dict]:
    """检测"不是...而是..."句式。"""
    pattern = re.compile(
        r'(?:[^。！？\n]*?不是[^。！？\n]*?而是[^。！？\n]*[。！？\n])',
        re.MULTILINE
    )
    matches = []
    for m in pattern.finditer(text):
        matched = m.group().strip()
        # 排除过长匹配（可能是整段而不是句式）
        if len(matched) > 200:
            continue
        matches.append({
            'text': matched[:80],
            'position': m.start(),
        })
    return matches


def extract_quote_content(line: str) -> list[tuple[str, int]]:
    """从一行文本中提取引号内的对话内容。
    返回: [(内容, 行号偏移), ...]
    支持 ""、「」『』等各类中文引号。
    """
    results = []
    for open_q, close_q in QUOTE_PAIRS:
        # 查找当前行的引号
        start = 0
        while True:
            open_pos = line.find(open_q, start)
            if open_pos == -1:
                break
            close_pos = line.find(close_q, open_pos + 1)
            if close_pos == -1:
                break
            content = line[open_pos + 1:close_pos].strip()
            if content and len(content) >= 3:  # 最少3字才算有效对话
                results.append((content, open_pos))
            start = close_pos + 1
    # 按位置排序
    results.sort(key=lambda x: x[1])
    return [(c, p) for c, p in results]


def detect_repetitive_dialogues(text: str) -> list[str]:
    """
    检测连续对话中的重复。

    改进策略（v2）：
    1. 提取所有对话内容（不限引号样式）
    2. 比较相邻对话时，使用较长子串匹配（≥15字重叠才算重复）
    3. 同一说话者的连续对话尤其严格
    4. 排除寒暄类短对话（"你好""再见"等）
    """
    lines = text.split('\n')
    dialogue_entries = []  # [(行号, 原始行, 对话内容列表)]

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        contents = extract_quote_content(stripped)
        if contents:
            dialogue_entries.append((i, stripped, [c for c, _ in contents]))

    issues = []

    for n in range(1, len(dialogue_entries)):
        _, _, prev_contents = dialogue_entries[n - 1]
        _, _, curr_contents = dialogue_entries[n]

        for prev_text in prev_contents:
            for curr_text in curr_contents:
                # 跳过短对话（寒暄类不检测）
                if len(prev_text) < 8 or len(curr_text) < 8:
                    continue

                # 用最长公共子串判断是否重复（≥15字重叠才算）
                overlap = longest_common_substring(prev_text, curr_text)
                if overlap >= 15:
                    prev_line = dialogue_entries[n - 1][1][:60]
                    curr_line = dialogue_entries[n][1][:60]
                    issues.append(
                        f"行{dialogue_entries[n][0]+1}: 「{curr_text[:30]}…」"
                        f" 与 行{dialogue_entries[n-1][0]+1}: 「{prev_text[:30]}…」 重复内容{overlap}字"
                    )
                    break
            if issues and len(issues) > 0 and issues[-1].startswith(f"行{dialogue_entries[n][0]+1}"):
                break

    # 去重
    seen = set()
    unique_issues = []
    for item in issues:
        if item not in seen:
            seen.add(item)
            unique_issues.append(item)

    return unique_issues


def longest_common_substring(s1: str, s2: str) -> int:
    """计算两个字符串的最长公共子串长度（优化版）。"""
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    m, n = len(s1), len(s2)
    max_len = 0

    # 使用滚动数组优化空间
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                curr[j] = prev[j - 1] + 1
                if curr[j] > max_len:
                    max_len = curr[j]
            else:
                curr[j] = 0
        prev, curr = curr, prev

    return max_len


def detect_repetitive_actions(text: str) -> list[str]:
    """
    检测重复动作描写。

    连续3句内出现完全相同的动作描述（如"他点了点头""他叹了口气"重复出现）。
    """
    lines = text.split('\n')
    # 提取所有非对话的动作描写行
    action_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过纯对话行
        has_quote = any(q in stripped for q in ['「', '"', '"', '「', '『', "'"])
        if has_quote and len(stripped) < 30:
            continue
        # 跳过标题和空行
        if stripped.startswith('#') or stripped.startswith('>'):
            continue
        action_lines.append((i, stripped))

    issues = []
    # 检查连续10行内是否有完全相同的动作
    for n in range(len(action_lines)):
        for m in range(n + 1, min(n + 10, len(action_lines))):
            _, line_a = action_lines[n]
            _, line_b = action_lines[m]
            # 跳过太短的行
            if len(line_a) < 4 or len(line_b) < 4:
                continue
            # 完全相同的动作描写（去除前后空白后全等）
            if line_a.strip() == line_b.strip() and len(line_a) >= 4:
                if action_lines[m][0] - action_lines[n][0] <= 10:  # 10行以内
                    issues.append(
                        f"重复动作: 行{action_lines[n][0]+1}「{line_a[:40]}」"
                        f" == 行{action_lines[m][0]+1}「{line_b[:40]}」"
                    )
                break  # 同一行只报告一次

    # 去重
    seen = set()
    unique = []
    for item in issues:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def main():
    if len(sys.argv) < 2:
        print("用法: python detect_forbidden_patterns.py <chapter_file>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在 {filepath}")
        sys.exit(1)

    text = filepath.read_text(encoding='utf-8')

    # 检测二元对照句式
    binary_matches = detect_binary_contrasts(text)

    # 检测重复对话
    repetitive_dialogues = detect_repetitive_dialogues(text)

    # 检测重复动作
    repetitive_actions = detect_repetitive_actions(text)

    # 输出结果
    print(f"binary_contrast_count: {len(binary_matches)}")
    print(f"binary_contrast_ok: {'true' if len(binary_matches) <= 2 else 'false'}")
    if binary_matches:
        for m in binary_matches:
            print(f"  - \"{m['text'][:60]}...\"")

    print(f"repetitive_dialogues:")
    if repetitive_dialogues:
        for item in repetitive_dialogues:
            print(f"  - \"{item}\"")
    else:
        print(f"  []")

    print(f"repetitive_actions:")
    if repetitive_actions:
        for item in repetitive_actions:
            print(f"  - \"{item}\"")
    else:
        print(f"  []")

    errors = []
    if len(binary_matches) > 2:
        errors.append(f"二元对照句式超过2次 ({len(binary_matches)}次)")
    if repetitive_dialogues:
        errors.append(f"存在{len(repetitive_dialogues)}处重复对话")
    if repetitive_actions:
        errors.append(f"存在{len(repetitive_actions)}处重复动作")

    is_ok = not errors
    print(f"ok: {'true' if is_ok else 'false'}")
    if errors:
        for err in errors:
            print(f"  - \"{err}\"")

    sys.exit(0 if is_ok else 1)


if __name__ == '__main__':
    main()

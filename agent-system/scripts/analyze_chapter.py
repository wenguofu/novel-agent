#!/usr/bin/env python3
"""
analyze_chapter.py — 章节分析工具

功能：
- 统计中文字数（纯中文字符，排除markdown标记、标点、空白）
- 检查结构合规：文件是否以 "# 第XX章" 开头
- 检查是否包含元数据段（章节功能、节奏规则等）
- 检查是否包含结尾总结段

用法：
    python analyze_chapter.py <chapter_file>

输出 (stdout, YAML格式):
    word_count: 2500
    structure_ok: true
    has_metadata: false
    has_summary: false
    errors: []
"""

import re
import sys
from pathlib import Path


def count_chinese_chars(text: str) -> int:
    """统计纯中文字符（Unicode CJK统一表意文字区段）。"""
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    return len(cjk_pattern.findall(text))


def check_structure(text: str) -> tuple[bool, str]:
    """检查章节标题格式: # 第XX章 ..."""
    lines = text.strip().split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('# '):
            if re.match(r'^#\s*第[一二三四五六七八九十百千万\d]+章', stripped):
                return True, stripped
            else:
                return False, f"章节标题格式异常: {stripped}"
    return False, "未找到章节标题 (以 # 开头的行)"


META_PATTERNS = [
    '章节功能', '节奏规则', '对应 outline', '本章功能', '类型节奏',
    '章节编号', '章节标题', '结尾牵引', '关键事件',
]


SUMMARY_PATTERNS = [
    '人物状态变化', '设定变化', '新增伏笔', '待回收伏笔',
    '章末', '章节总结', '尾部牵引', '下章提示',
    '当前章节', '剧情位置',
]


def check_metadata(text: str) -> list[str]:
    """检查正文开头是否包含元数据段。"""
    lines = text.strip().split('\n')
    # 跳过章节标题行
    content_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('# ') and i < 2:
            content_start = i + 1
            break

    # 检查前10行的内容中是否包含元数据模式
    header_lines = lines[content_start:content_start + 10]
    errors = []
    for line in header_lines:
        stripped = line.strip()
        for pattern in META_PATTERNS:
            if pattern in stripped and stripped.startswith('-'):
                errors.append(f"可能的元数据行: '{stripped[:50]}...'")
                break
    return errors


def check_summary(text: str) -> list[str]:
    """检查正文末尾是否包含总结段。"""
    lines = text.strip().split('\n')
    if len(lines) < 5:
        return []

    tail_lines = lines[-20:]
    errors = []
    for line in tail_lines:
        stripped = line.strip()
        for pattern in SUMMARY_PATTERNS:
            if pattern in stripped and stripped.startswith('-'):
                errors.append(f"可能的总结行: '{stripped[:50]}...'")
                break
    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python analyze_chapter.py <chapter_file>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在 {filepath}")
        sys.exit(1)

    text = filepath.read_text(encoding='utf-8')

    word_count = count_chinese_chars(text)
    struct_ok, struct_msg = check_structure(text)
    meta_errors = check_metadata(text)
    summary_errors = check_summary(text)

    is_valid = struct_ok and not meta_errors and not summary_errors

    # 输出 YAML 格式结果
    print(f"word_count: {word_count}")
    print(f"structure_ok: {'true' if struct_ok else 'false'}")
    if struct_msg:
        print(f"structure_note: \"{struct_msg}\"")
    print(f"has_metadata: {'true' if meta_errors else 'false'}")
    print(f"has_summary: {'true' if summary_errors else 'false'}")
    if meta_errors:
        for err in meta_errors:
            print(f"  - \"{err}\"")
    if summary_errors:
        for err in summary_errors:
            print(f"  - \"{err}\"")
    print(f"valid: {'true' if is_valid else 'false'}")
    print(f"min_2500_ok: {'true' if word_count >= 2500 else 'false'}")

    sys.exit(0 if is_valid and word_count >= 2500 else 1)


if __name__ == '__main__':
    main()

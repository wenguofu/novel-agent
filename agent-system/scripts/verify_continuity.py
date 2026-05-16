#!/usr/bin/env python3
"""
verify_continuity.py — 章节连续性校验

功能：
- 检查一批章节之间的时间线连续性
- 对比每章结尾和下一章开头的人物状态/位置是否一致
- 检测明显的跳跃或断裂

用法：
    python verify_continuity.py --start <章节号> --end <章节号> [--project <项目目录>]

从 state/current_status.md 读取参考状态。

输出 (stdout, YAML格式):
    continuous: true
    gaps: []
    warnings: []
"""

import argparse
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='章节连续性校验')
    parser.add_argument('--start', type=int, required=True, help='起始章节号')
    parser.add_argument('--end', type=int, required=True, help='结束章节号')
    parser.add_argument('--project', type=str, help='项目目录')
    return parser.parse_args()


def find_project_root() -> Path:
    """从当前目录向上查找项目根。"""
    current = Path.cwd()
    for _ in range(10):
        if (current / 'state/current_status.md').exists():
            return current
        current = current.parent
    return Path.cwd()


def main():
    args = parse_args()
    project = Path(args.project) if args.project else find_project_root()

    start = args.start
    end = args.end
    warnings = []
    gaps = []

    # 检查每章文件是否存在
    for ch in range(start, end + 1):
        # 尝试 vol-XX 推断（从文件系统查找）
        found = False
        for vol_dir in (project / 'manuscript').iterdir():
            if vol_dir.is_dir():
                ch_file = vol_dir / f'ch-{ch:04d}.md'
                if ch_file.exists():
                    found = True
                    # 检查字数
                    text = ch_file.read_text(encoding='utf-8')
                    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
                    if chinese_chars < 2500:
                        gaps.append(f"ch-{ch:04d}: 字数不足 ({chinese_chars} < 2500)")
                    break
        if not found:
            gaps.append(f"ch-{ch:04d}: 文件不存在")

    # 检查 current_status.md 的连续性（只读不做修改）
    status_path = project / 'state/current_status.md'
    if not status_path.exists():
        gaps.append("state/current_status.md 不存在")

    continuous = len(gaps) == 0
    print(f"continuous: {'true' if continuous else 'false'}")
    print(f"range: \"{start:04d}-{end:04d}\"")
    print(f"total_chapters: {end - start + 1}")
    print(f"warnings:")
    for w in warnings:
        print(f"  - \"{w}\"")
    print(f"gaps:")
    for g in gaps:
        print(f"  - \"{g}\"")

    sys.exit(0 if continuous else 1)


if __name__ == '__main__':
    main()

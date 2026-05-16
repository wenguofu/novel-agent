#!/usr/bin/env python3
"""
check_compliance.py — 合规名称检查

功能：
- 从 alias_registry.md 加载别名表
- 扫描章节正文是否出现真实名称（地名、国家、领导人等）
- 如发现未登记的真实名称，提议替代别名
- 输出违规列表

用法：
    python check_compliance.py <chapter_file> [--alias <alias_registry>]

默认 alias_registry 路径为项目根目录的 alias_registry.md。
从章节文件路径自动推断项目根目录（向上查找包含 alias_registry.md 的目录）。

输出 (stdout, YAML格式):
    pass: true
    violations: []
    new_aliases_proposed: []
"""

import re
import sys
from pathlib import Path


# 已知现实名称模式（匹配后去 alias_registry.md 核实）
REAL_NAME_PATTERNS = [
    # 国家/地区
    r'(?<![a-zA-Z])中国(?![a-zA-Z])',
    r'(?<![a-zA-Z])美国(?![a-zA-Z])',
    r'(?<![a-zA-Z])日本(?![a-zA-Z])',
    r'(?<![a-zA-Z])英国(?![a-zA-Z])',
    r'(?<![a-zA-Z])法国(?![a-zA-Z])',
    r'(?<![a-zA-Z])德国(?![a-zA-Z])',
    r'(?<![a-zA-Z])俄罗斯(?![a-zA-Z])',
    r'(?<![a-zA-Z])韩国(?![a-zA-Z])',
    r'(?<![a-zA-Z])印度(?![a-zA-Z])',
    r'(?<![a-zA-Z])朝鲜(?![a-zA-Z])',
    r'(?<![a-zA-Z])越南(?![a-zA-Z])',
    r'(?<![a-zA-Z])泰国(?![a-zA-Z])',
    r'(?<![a-zA-Z])新加坡(?![a-zA-Z])',
    r'(?<![a-zA-Z])澳大利亚(?![a-zA-Z])',
    r'(?<![a-zA-Z])加拿大(?![a-zA-Z])',
    # 省份
    r'(?<![a-zA-Z])(?:北京|上海|广州|深圳|天津|重庆|杭州|南京|成都|武汉|西安|长沙|郑州|沈阳|青岛|厦门|苏州)(?![a-zA-Z])',
    # 领导人/名人
    r'(?<![a-zA-Z])(?:主席|总书记|总理|总统|首相)(?![a-zA-Z])',
]


def load_alias_registry(registry_path: Path) -> dict[str, str]:
    """加载别名表，返回 {原文: 别名} 映射。"""
    aliases = {}
    if not registry_path.exists():
        return aliases

    text = registry_path.read_text(encoding='utf-8')
    current_original = None
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('别名：') or stripped.startswith('别名:'):
            alias = stripped.split('：', 1)[-1] if '：' in stripped else stripped.split(':', 1)[-1]
            if current_original:
                aliases[current_original] = alias.strip()
        if stripped.startswith('原称：') or stripped.startswith('原称:'):
            current_original = stripped.split('：', 1)[-1] if '：' in stripped else stripped.split(':', 1)[-1]
            current_original = current_original.strip()
        elif stripped.startswith('类别：') or stripped.startswith('类别:'):
            pass  # 只是类别标记

    return aliases


def find_project_root(chapter_path: Path) -> Path:
    """从章节文件向上查找项目根目录。"""
    current = chapter_path.parent
    for _ in range(10):
        if (current / 'alias_registry.md').exists():
            return current
        if (current / 'project.md').exists():
            return current
        current = current.parent
    return chapter_path.parent.parent.parent  # fallback


def main():
    if len(sys.argv) < 2:
        print("用法: python check_compliance.py <chapter_file> [--alias <alias_registry>]")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在 {filepath}")
        sys.exit(1)

    # 确定 alias_registry 路径
    alias_path = None
    for i, arg in enumerate(sys.argv[1:-1]):
        if arg == '--alias':
            alias_path = Path(sys.argv[i + 2])
            break
    if not alias_path:
        project_root = find_project_root(filepath)
        alias_path = project_root / 'alias_registry.md'

    text = filepath.read_text(encoding='utf-8')
    aliases = load_alias_registry(alias_path)

    violations = []
    for pattern in REAL_NAME_PATTERNS:
        for m in re.finditer(pattern, text):
            word = m.group()
            # 检查是否已在别名表中
            is_alias = any(word == v or word in k for k, v in aliases.items())
            if not is_alias:
                violations.append({
                    'word': word,
                    'position': m.start(),
                    'context': text[max(0, m.start() - 10):m.end() + 10],
                })

    # 去重
    seen = set()
    unique_violations = []
    for v in violations:
        if v['word'] not in seen:
            seen.add(v['word'])
            unique_violations.append(v)

    # 提议新别名
    proposed = []
    for v in unique_violations:
        word = v['word']
        if word == '北京':
            proposed.append({'original': word, 'suggested': '上京'})
        elif word == '上海':
            proposed.append({'original': word, 'suggested': '海州'})
        elif word == '广州':
            proposed.append({'original': word, 'suggested': '南陵'})
        elif word == '中国':
            proposed.append({'original': word, 'suggested': '夏国'})
        elif word == '美国':
            proposed.append({'original': word, 'suggested': '鹰国'})
        elif word == '日本':
            proposed.append({'original': word, 'suggested': '樱国'})
        else:
            proposed.append({'original': word, 'suggested': f'{word}（虚构化）'})

    pass_status = len(unique_violations) == 0
    print(f"pass: {'true' if pass_status else 'false'}")
    print(f"violations:")
    for v in unique_violations:
        print(f"  - word: \"{v['word']}\"")
        print(f"    context: \"{v['context']}\"")
    print(f"new_aliases_proposed:")
    for p in proposed:
        print(f"  - original: \"{p['original']}\"")
        print(f"    suggested: \"{p['suggested']}\"")

    sys.exit(0 if pass_status else 1)


if __name__ == '__main__':
    main()

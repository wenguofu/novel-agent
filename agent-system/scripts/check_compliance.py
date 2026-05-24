#!/usr/bin/env python3
"""
check_compliance.py — 合规名称检查（v2.0）

功能：
- 从 compliance_config.json 加载检测规则和别名建议
- 从 alias_registry.md 加载已有别名表
- 扫描章节正文是否出现真实名称（地名、国家、领导人等）
- 支持上下文敏感白名单（如"小说中"/"虚构的"等语境不触发）
- 如发现未登记的真实名称，从配置中查找建议别名
- 输出违规列表

用法：
    python check_compliance.py <chapter_file> [--config <config_path>]
    python check_compliance.py <chapter_file> --alias <alias_registry>

默认 config 路径为 agent-system/compliance_config.json。
从章节文件路径自动推断项目根目录及 config 路径。

输出 (stdout, YAML格式):
    pass: true/false
    violations: []
    new_aliases_proposed: []
"""

import json
import re
import sys
from pathlib import Path


def load_config(config_path: Path) -> dict:
    """加载合规检查配置。"""
    if not config_path.exists():
        print(f"警告: 配置文件不存在 {config_path}，使用内置默认规则", file=sys.stderr)
        return get_default_config()
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_default_config() -> dict:
    """内置降级配置（当 config 文件不存在时的后备）。"""
    return {
        "real_name_patterns": {
            "countries": {
                "patterns": ["中国", "美国", "日本", "英国", "法国", "德国", "俄罗斯", "韩国"]
            },
            "provinces": {
                "patterns": ["北京", "上海", "广州", "深圳", "天津", "重庆"]
            }
        },
        "alias_suggestions": {
            "中国": "夏国", "美国": "鹰国", "日本": "樱国",
            "北京": "上京", "上海": "海州", "广州": "南陵"
        },
        "context_sensitivity": {
            "whitelist_contexts": [
                {"pattern": "小说中", "reason": "元讨论"},
                {"pattern": "虚构的", "reason": "明确声明虚构"}
            ]
        }
    }


def compile_patterns(config: dict) -> list[tuple[str, str, str]]:
    """
    从配置编译正则模式列表。
    返回: [(pattern_str, 类别, 原始词)]
    """
    # CJK 统一汉字范围 (U+4E00–U+9FFF)
    cjk_range = '\u4e00-\u9fff'
    compiled = []
    for category, category_data in config.get("real_name_patterns", {}).items():
        for word in category_data.get("patterns", []):
            # 使用 CJK 字符边界，防止 "山东" 匹配到 "山东省" 里的部分
            # 但 "北京" 在 "北京市" 中也应匹配，所以用更宽松的边界
            pattern = rf'(?<![{cjk_range}]){re.escape(word)}(?![{cjk_range}])'
            compiled.append((pattern, category, word))
    return compiled


def compile_whitelist_patterns(config: dict) -> list[re.Pattern]:
    """编译上下文白名单正则。"""
    patterns = []
    ctx = config.get("context_sensitivity", {}).get("whitelist_contexts", [])
    for item in ctx:
        p = item.get("pattern", "")
        ptype = item.get("type", "literal")
        if ptype == "regex":
            patterns.append(re.compile(p))
        else:
            patterns.append(re.compile(re.escape(p)))
    return patterns


def is_in_whitelist_context(text: str, pos: int, whitelist_patterns: list[re.Pattern]) -> bool:
    """检查某个位置是否处于白名单上下文附近（前50字符内）。"""
    start = max(0, pos - 50)
    preceding = text[start:pos]
    for pattern in whitelist_patterns:
        if pattern.search(preceding):
            return True
    return False


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
            sep = '：' if '：' in stripped else ':'
            alias = stripped.split(sep, 1)[-1].strip()
            if current_original:
                aliases[current_original] = alias
        if stripped.startswith('原称：') or stripped.startswith('原称:'):
            sep = '：' if '：' in stripped else ':'
            current_original = stripped.split(sep, 1)[-1].strip()
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


def find_config_path(chapter_path: Path) -> Path:
    """查找 compliance_config.json。"""
    # 先找 agent-system 目录
    project_root = find_project_root(chapter_path)
    # 从项目根部查找 novel-agent 的 agent-system
    candidate = project_root.parent / 'agent-system' / 'compliance_config.json'
    if candidate.exists():
        return candidate
    # 或者同级
    candidate = project_root / 'agent-system' / 'compliance_config.json'
    if candidate.exists():
        return candidate
    # 或者上级
    candidate = project_root.parent.parent / 'agent-system' / 'compliance_config.json'
    if candidate.exists():
        return candidate
    return Path.cwd() / 'compliance_config.json'


def main():
    if len(sys.argv) < 2:
        print("用法: python check_compliance.py <chapter_file> [--config <config_path>] [--alias <alias_registry>]")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在 {filepath}")
        sys.exit(1)

    # 解析参数
    config_path = None
    alias_path = None
    for i, arg in enumerate(sys.argv[1:-1]):
        if arg == '--config' and i + 2 < len(sys.argv):
            config_path = Path(sys.argv[i + 2])
        if arg == '--alias' and i + 2 < len(sys.argv):
            alias_path = Path(sys.argv[i + 2])

    # 自动推断路径
    if not config_path:
        config_path = find_config_path(filepath)
    if not alias_path:
        project_root = find_project_root(filepath)
        alias_path = project_root / 'alias_registry.md'

    # 加载配置和别名表
    config = load_config(config_path)
    patterns = compile_patterns(config)
    whitelist_patterns = compile_whitelist_patterns(config)
    alias_suggestions = config.get("alias_suggestions", {})
    registered_aliases = load_alias_registry(alias_path)

    # 读取章节正文
    text = filepath.read_text(encoding='utf-8')

    # 扫描违规
    violations = []
    seen_violations = set()

    for pattern_str, category, word in patterns:
        rx = re.compile(pattern_str)
        for m in rx.finditer(text):
            matched = m.group()
            pos = m.start()

            # 去重：同一词只报告第一次
            if word in seen_violations:
                continue

            # 检查是否已在别名表中（原文已注册别名的不算违规）
            already_mapped = (
                word in registered_aliases or
                any(word == v for v in registered_aliases.values()) or
                any(word in k for k in registered_aliases.keys())
            )
            if already_mapped:
                continue

            # 检查是否在白名单上下文附近
            if is_in_whitelist_context(text, pos, whitelist_patterns):
                continue

            seen_violations.add(word)
            context_start = max(0, pos - 15)
            context_end = min(len(text), pos + len(matched) + 15)
            violations.append({
                'word': word,
                'category': category,
                'position': pos,
                'context': text[context_start:context_end].replace('\n', ' '),
            })

    # 提议新别名
    proposed = []
    for v in violations:
        word = v['word']
        if word in alias_suggestions:
            proposed.append({
                'original': word,
                'suggested': alias_suggestions[word],
                'source': 'compliance_config.json'
            })
        else:
            # 自动生成别名规则：
            # 去掉"省""市""自治区""特别行政区"后缀，加"虚构化"标记
            auto_alias = word
            for suffix in ['省', '市', '自治区', '特别行政区', '共和国']:
                if auto_alias.endswith(suffix):
                    auto_alias = auto_alias[:-len(suffix)]
            proposed.append({
                'original': word,
                'suggested': f'{auto_alias}（虚构化）',
                'source': 'auto_generated'
            })

    # 输出结果
    pass_status = len(violations) == 0
    print(f"pass: {'true' if pass_status else 'false'}")
    print(f"config_used: \"{config_path}\"")
    print(f"total_check_items: {len(patterns)}")
    print(f"violations:")
    for v in violations:
        print(f"  - word: \"{v['word']}\"")
        print(f"    category: \"{v['category']}\"")
        print(f"    context: \"{v['context']}\"")
    print(f"new_aliases_proposed:")
    for p in proposed:
        print(f"  - original: \"{p['original']}\"")
        print(f"    suggested: \"{p['suggested']}\"")
        print(f"    source: \"{p['source']}\"")

    sys.exit(0 if pass_status else 1)


if __name__ == '__main__':
    main()

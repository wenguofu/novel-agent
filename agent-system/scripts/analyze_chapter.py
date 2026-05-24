#!/usr/bin/env python3
"""
analyze_chapter.py — 章节综合验证工具 (v3.0)

功能：
- 中文字数统计 (≥2500字)
- 章节标题格式检查
- 元数据/总结段检查 (防止非正文混入)
- 「不是...而是...」二元句式检测 (≤2次)
- 禁用名称扫描 (compliance_config.json + alias_registry.md)
- 人物名称验证 (characters.md)
- 重复段落检测

用法：
    python analyze_chapter.py <chapter_file> [--project <novel_dir>]

输出 (stdout, YAML格式):
    word_count: 2500
    structure_ok: true
    binary_patterns: 1
    banned_names: 0
    unknown_characters: []
    repetition_count: 0
    valid: true
    min_2500_ok: true
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

# ── 配置 ──
MIN_WORDS = 2500
MAX_BINARY_SENTENCES = 2
SCRIPT_DIR = Path(__file__).resolve().parent
COMPLIANCE_CONFIG = SCRIPT_DIR / ".." / "compliance_config.json"


def count_chinese_chars(text: str) -> int:
    cjk = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    return len(cjk.findall(text))


def check_structure(text: str) -> tuple:
    lines = text.strip().split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('# '):
            if re.match(r'^#\s*第[一二三四五六七八九十百千万\d]+章', stripped):
                return True, stripped
            else:
                return False, f"标题格式异常: {stripped}"
    return False, "未找到章节标题"


def extract_body(text: str) -> str:
    """提取正文部分，排除元数据"""
    m = re.search(r'正文[：:]\s*\n?(.*?)(?=\n(?:人物状态变化|设定变化|新增伏笔|待回收伏笔|合规检查|审稿结论|资料更新项)[：:]|\Z)',
                  text, re.DOTALL)
    if m and len(m.group(1).strip()) > 100:
        return m.group(1).strip()
    return text.strip()


def count_binary_patterns(text: str) -> int:
    body = extract_body(text)
    pattern = r'不是[^。！？\n]{0,50}(?:。|！|？|\n)[^。！？\n]{0,50}而是'
    return len(re.findall(pattern, body))


def check_metadata(text: str) -> list:
    """检查正文是否混入元数据行"""
    lines = text.strip().split('\n')
    content_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('# ') and i < 2:
            content_start = i + 1
            break
    header_lines = lines[content_start:content_start + 10]
    meta_patterns = ['章节功能', '节奏规则', '对应 outline', '本章功能', '类型节奏',
                     '章节编号', '章节标题', '结尾牵引', '关键事件']
    errors = []
    for line in header_lines:
        stripped = line.strip()
        for p in meta_patterns:
            if p in stripped and (stripped.startswith('-') or stripped.startswith('*')):
                errors.append(f"元数据混入正文: '{stripped[:50]}...'")
                break
    return errors


def check_summary(text: str) -> list:
    lines = text.strip().split('\n')
    if len(lines) < 5:
        return []
    tail_lines = lines[-20:]
    summary_patterns = ['人物状态变化', '设定变化', '新增伏笔', '待回收伏笔',
                        '章末', '章节总结', '尾部牵引', '下章提示', '当前章节']
    errors = []
    for line in tail_lines:
        stripped = line.strip()
        for p in summary_patterns:
            if p in stripped and (stripped.startswith('-') or stripped.startswith('*')):
                errors.append(f"总结混入正文: '{stripped[:50]}...'")
                break
    return errors


def load_banned_names() -> list:
    """从 compliance_config.json 加载禁用名称"""
    if COMPLIANCE_CONFIG.exists():
        try:
            config = json.loads(COMPLIANCE_CONFIG.read_text())
            patterns = config.get('real_name_patterns', {})
            all_names = []
            for category in patterns.values():
                all_names.extend(category.get('patterns', []))
            return all_names
        except Exception:
            pass
    return []


def check_banned_names(text: str) -> list:
    body = extract_body(text)
    banned = load_banned_names()
    found = [w for w in banned if w in body]
    return found


def load_character_names(novel_dir: Path) -> set:
    chars_file = novel_dir / "characters.md"
    if not chars_file.exists():
        return set()
    text = chars_file.read_text()
    names = set()
    for m in re.finditer(r'\|\s*([^\s|]+)\s*\|', text):
        name = m.group(1).strip()
        if 2 <= len(name) <= 4 and all('\u4e00' <= c <= '\u9fff' for c in name):
            names.add(name)
    return names


def extract_character_names(text: str) -> set:
    body = extract_body(text)
    pattern = r'(?<=[，。！？、：""''（）\s])[\u4e00-\u9fff]{2,4}(?=[，。！？、：""''（）\s])'
    skip = {"什么", "怎么", "那么", "这是", "已经", "突然", "但是",
            "而且", "然后", "所以", "因为", "如果", "虽然", "可是",
            "还是", "或者", "只是", "一直", "一会", "之后",
            "一下", "一点", "上面", "下面", "里面", "外面", "旁边",
            "那个", "这个", "哪些", "哪里", "什么样",
            "没有", "不会", "不能", "可以", "可能", "必须",
            "过来", "过去", "起来", "下来", "进来", "出去",
            "开始", "结束", "继续", "完成", "出现", "消失"}
    names = set()
    for m in re.finditer(pattern, body):
        word = m.group()
        if word not in skip:
            names.add(word)
    return names


def check_repetition(text: str) -> int:
    body = extract_body(text)
    sentences = re.split(r'[。！？\n]', body)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    count = 0
    for i in range(len(sentences) - 2):
        s1, s2, s3 = sentences[i], sentences[i+1], sentences[i+2]
        sim12 = SequenceMatcher(None, s1, s2).ratio()
        sim23 = SequenceMatcher(None, s2, s3).ratio()
        if sim12 > 0.6 and sim23 > 0.6:
            count += 1
    return count


def main():
    if len(sys.argv) < 2:
        print("用法: python analyze_chapter.py <chapter_file> [--project <novel_dir>]")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在 {filepath}")
        sys.exit(1)

    # 推断项目目录
    novel_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == '--project' and i + 1 < len(sys.argv):
            novel_dir = Path(sys.argv[i + 1])
            break
    if not novel_dir:
        # 从路径推断: manuscript/vol-XX/ch-XXXX.md → novel_dir
        novel_dir = filepath.parent.parent.parent

    text = filepath.read_text(encoding='utf-8')
    body = extract_body(text)

    word_count = count_chinese_chars(body)
    struct_ok, struct_msg = check_structure(text)
    meta_errors = check_metadata(text)
    summary_errors = check_summary(text)
    binary_count = count_binary_patterns(text)
    banned_names = check_banned_names(text)

    # 人物验证
    unknown_chars = []
    if novel_dir and novel_dir.exists():
        registered = load_character_names(novel_dir)
        if registered:
            text_names = extract_character_names(text)
            unknown_chars = list(text_names - registered)[:10]

    rep_count = check_repetition(text)

    errors = []
    if word_count < MIN_WORDS:
        errors.append(f"字数不足: {word_count} < {MIN_WORDS}")
    if binary_count > MAX_BINARY_SENTENCES:
        errors.append(f"二元句式超标: {binary_count} > {MAX_BINARY_SENTENCES}")
    if banned_names:
        errors.append(f"禁用名称: {', '.join(banned_names[:10])}")
    if unknown_chars:
        errors.append(f"未登记人物: {', '.join(unknown_chars[:5])}")
    if rep_count > 0:
        errors.append(f"重复段落: {rep_count}处")
    if meta_errors:
        errors.extend(meta_errors)
    if summary_errors:
        errors.extend(summary_errors)

    is_valid = not errors and struct_ok

    # YAML 输出
    print(f"word_count: {word_count}")
    print(f"min_2500_ok: {'true' if word_count >= MIN_WORDS else 'false'}")
    print(f"structure_ok: {'true' if struct_ok else 'false'}")
    if not struct_ok:
        print(f"structure_error: \"{struct_msg}\"")
    print(f"binary_patterns: {binary_count}")
    print(f"binary_ok: {'true' if binary_count <= MAX_BINARY_SENTENCES else 'false'}")
    print(f"banned_names: {len(banned_names)}")
    if banned_names:
        print(f"banned_names_list: [{', '.join(repr(w) for w in banned_names[:10])}]")
    print(f"unknown_characters: {len(unknown_chars)}")
    if unknown_chars:
        print(f"unknown_characters_list: [{', '.join(repr(c) for c in unknown_chars[:5])}]")
    print(f"repetition_count: {rep_count}")
    print(f"has_metadata: {'true' if meta_errors else 'false'}")
    print(f"has_summary: {'true' if summary_errors else 'false'}")
    if errors:
        print("errors:")
        for e in errors:
            print(f"  - \"{e}\"")
    else:
        print("errors: []")
    print(f"valid: {'true' if is_valid else 'false'}")

    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()

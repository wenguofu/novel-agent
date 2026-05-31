#!/usr/bin/env python3
"""
Style Distiller — Extract quantitative writing style fingerprints from real text.

Processes actual author texts to extract:
- Sentence length distribution (mean, std, histogram)
- Paragraph length patterns
- Dialogue ratio (quoted speech vs narration)
- Vocabulary richness (unique words / total words, hapax legomena)
- Transition word frequency (然而/但是/却/于是/接着/后来...)
- Modal particle usage (呢/吧/啊/嘛/了/的...)
- Sentence opener patterns
- Emotional density (adjectives, adverbs per 1000 chars)
- Punctuation profile (comma vs period vs semicolon ratio)
- Rhetorical device markers (metaphor indicators, parallelism, repetition)

Usage:
  python style_distiller.py distill <text_file> --author <name> [--output <dir>]
  python style_distiller.py distill-all --corpus <dir> --output <dir>
  python style_distiller.py inject <style_name> [--format prompt|json]
  python style_distiller.py compare <file1> <file2> [--author <name>]
  python style_distiller.py list
"""

import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"


def _safe_filename(author_name: str) -> str:
    """Generate a safe filename from author name, preserving readability."""
    # Keep alphanumeric, Chinese chars, dash, underscore
    safe = re.sub(r'[^\w一-鿿-]', '_', author_name).strip('_')
    if len(safe) < 2:
        safe = hashlib.md5(author_name.encode()).hexdigest()[:12]
    return safe or "unknown"


@dataclass
class StyleFingerprint:
    author: str
    source: str = ""
    sample_size_chars: int = 0
    sample_count: int = 0

    # Sentence-level
    sentence_length_mean: float = 0.0
    sentence_length_std: float = 0.0
    sentence_length_histogram: dict = field(default_factory=dict)

    # Paragraph-level
    paragraph_length_mean: float = 0.0
    sentences_per_paragraph: float = 0.0

    # Lexical
    unique_word_ratio: float = 0.0
    hapax_ratio: float = 0.0
    top_20_words: list = field(default_factory=list)

    # Structural ratios
    dialogue_ratio: float = 0.0
    action_ratio: float = 0.0
    description_ratio: float = 0.0

    # Transition words per 1000 chars
    transitions: dict = field(default_factory=dict)
    transition_density: float = 0.0

    # Modal particles per 1000 chars
    modal_particles: dict = field(default_factory=dict)
    modal_density: float = 0.0

    # Sentence opener patterns (top 10)
    sentence_openers: list = field(default_factory=list)

    # Emotional density
    adjective_density: float = 0.0
    adverb_density: float = 0.0
    emotion_word_density: float = 0.0

    # Punctuation profile
    punctuation_profile: dict = field(default_factory=dict)

    # Rhetorical
    metaphor_density: float = 0.0
    parallelism_density: float = 0.0

    # Representative excerpts (short, for few-shot prompting)
    excerpts: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# ── Chinese Text Analysis Utilities ──────────────────────────────────

_CHINESE_CHAR = re.compile(r'[一-鿿]')
_TRANSITIONS = [
    "然而", "但是", "可是", "不过", "却", "虽", "尽管", "虽然",
    "于是", "接着", "然后", "后来", "之后", "随即", "立刻",
    "因此", "所以", "因为", "由于", "故",
    "而且", "并且", "况且", "此外", "另外", "还有",
    "总之", "总而言之", "简而言之", "换句话说",
    "首先", "其次", "最后", "最终", "第一", "第二", "第三",
    "反而", "反倒", "相反", "反倒", "居然", "竟然",
]

_MODAL_PARTICLES = [
    "呢", "吧", "啊", "嘛", "呗", "啦", "呀", "哇", "哦", "噢",
    "了", "的", "地", "得",
]

_EMOTION_WORDS = [
    "悲伤", "快乐", "愤怒", "恐惧", "惊讶", "厌恶", "喜欢", "爱",
    "恨", "愁", "喜", "怒", "哀", "乐", "忧", "惧", "惊", "厌",
    "痛苦", "幸福", "激动", "平静", "烦躁", "安心", "忐忑", "坦然",
    "绝望", "希望", "感动", "冷漠", "热情", "温柔", "残酷",
]

_METAPHOR_MARKERS = [
    "像", "如", "似", "仿佛", "好像", "宛如", "宛若", "犹如", "如同",
    "好比", "恰似", "一般",
]

_PARALLELISM_MARKER = re.compile(r'([^。！？\n]{8,30})(?:[，,；;]([^。！？\n]{8,30})){2,}')

_ACTION_VERBS = [
    "走", "跑", "跳", "飞", "打", "杀", "砍", "刺", "击", "踢",
    "冲", "撞", "摔", "扑", "抓", "拿", "放", "推", "拉", "扯",
    "站", "坐", "躺", "倒", "起", "落", "升", "降",
    "挥", "舞", "掷", "射", "劈", "斩", "轰",
]

_DESCRIPTION_ADJECTIVES = [
    "美丽", "丑陋", "高大", "矮小", "宽广", "狭窄", "明亮", "黑暗",
    "温暖", "寒冷", "柔软", "坚硬", "光滑", "粗糙",
    "红", "橙", "黄", "绿", "蓝", "靛", "紫", "黑", "白", "灰",
    "大", "小", "长", "短", "高", "低", "深", "浅", "厚", "薄",
]


def _tokenize_sentences(text: str) -> list[str]:
    """Split Chinese text into sentences."""
    # Split on Chinese punctuation + newlines
    raw = re.split(r'[。！？!?\n]+', text)
    return [s.strip() for s in raw if len(s.strip()) >= 2 and _CHINESE_CHAR.search(s)]


def _tokenize_words(text: str) -> list[str]:
    """Simple Chinese word segmentation using character bigrams + single chars."""
    chars = _CHINESE_CHAR.findall(text)
    words = []
    i = 0
    while i < len(chars):
        if i + 1 < len(chars):
            words.append(chars[i] + chars[i + 1])
        words.append(chars[i])
        i += 1
    return words


def _count_chinese(text: str) -> int:
    return len(_CHINESE_CHAR.findall(text))


def _dialogue_ratio(text: str) -> float:
    """Estimate dialogue proportion by counting quoted text."""
    quoted = len(re.findall(r'[""「」『』"\'][^""「」『』"\']{2,}[""「」『』"\']', text))
    # Also count 说：/道： patterns
    speak_patterns = len(re.findall(r'[说问道叫喊答][：:]', text))
    total = len(text) or 1
    return min(0.8, (quoted * 3 + speak_patterns * 15) / total)


def _sentence_openers(sentences: list[str], top_n: int = 10) -> list[dict]:
    """Extract common sentence opener patterns."""
    openers = Counter()
    for s in sentences:
        if len(s) >= 2:
            openers[s[:2]] += 1
    return [{"opener": k, "count": v} for k, v in openers.most_common(top_n)]


# ── Core Distillation ───────────────────────────────────────────────


def distill_text(text: str, author: str = "", source: str = "") -> StyleFingerprint:
    """Extract style fingerprint from raw text."""
    fp = StyleFingerprint(author=author, source=source)
    fp.sample_size_chars = len(text)
    fp.sample_count = 1

    sentences = _tokenize_sentences(text)
    if not sentences:
        return fp

    words = _tokenize_words(text)
    chinese_chars = _CHINESE_CHAR.findall(text)
    total_chars = len(chinese_chars) or 1

    # ── Sentence Length ──
    sent_lens = [_count_chinese(s) for s in sentences]
    sl_filtered = [l for l in sent_lens if l > 0]
    n_sl = len(sl_filtered) or 1
    fp.sentence_length_mean = sum(sl_filtered) / n_sl
    variance = sum((l - fp.sentence_length_mean) ** 2 for l in sl_filtered) / n_sl
    fp.sentence_length_std = math.sqrt(variance)

    # Histogram buckets
    buckets = {"1-10": 0, "11-20": 0, "21-30": 0, "31-50": 0, "51-80": 0, "81+": 0}
    for l in sl_filtered:
        if l <= 10: buckets["1-10"] += 1
        elif l <= 20: buckets["11-20"] += 1
        elif l <= 30: buckets["21-30"] += 1
        elif l <= 50: buckets["31-50"] += 1
        elif l <= 80: buckets["51-80"] += 1
        else: buckets["81+"] += 1
    fp.sentence_length_histogram = buckets

    # ── Paragraph ──
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    para_lens = [_count_chinese(p) for p in paragraphs]
    fp.paragraph_length_mean = sum(para_lens) / (len(para_lens) or 1)
    fp.sentences_per_paragraph = len(sentences) / (len(paragraphs) or 1)

    # ── Lexical ──
    word_counts = Counter(words)
    fp.unique_word_ratio = len(word_counts) / (len(words) or 1)
    hapax = sum(1 for c in word_counts.values() if c == 1)
    fp.hapax_ratio = hapax / (len(word_counts) or 1)
    fp.top_20_words = [
        {"word": w, "count": c}
        for w, c in word_counts.most_common(20) if len(w) >= 2
    ][:20]

    # ── Dialogue Ratio ──
    fp.dialogue_ratio = round(_dialogue_ratio(text), 3)

    # ── Action / Description Ratio ──
    action_count = sum(text.count(v) for v in _ACTION_VERBS)
    desc_count = sum(text.count(a) for a in _DESCRIPTION_ADJECTIVES)
    fp.action_ratio = round(action_count / total_chars, 3)
    fp.description_ratio = round(desc_count / total_chars, 3)

    # ── Transitions ──
    for t in _TRANSITIONS:
        c = text.count(t)
        if c > 0:
            fp.transitions[t] = c
    fp.transition_density = round(sum(fp.transitions.values()) / total_chars * 1000, 2)

    # ── Modal Particles ──
    for m in _MODAL_PARTICLES:
        c = text.count(m)
        if c > 0:
            fp.modal_particles[m] = c
    fp.modal_density = round(sum(fp.modal_particles.values()) / total_chars * 1000, 2)

    # ── Sentence Openers ──
    fp.sentence_openers = _sentence_openers(sentences)

    # ── Emotional Density ──
    adj_count = sum(len(re.findall(f"{a}", text)) for a in _DESCRIPTION_ADJECTIVES)
    fp.adjective_density = round(adj_count / total_chars * 1000, 2)
    adv_count = len(re.findall(r'[一-鿿]{1,2}[地]', text))
    fp.adverb_density = round(adv_count / total_chars * 1000, 2)
    emo_count = sum(text.count(e) for e in _EMOTION_WORDS)
    fp.emotion_word_density = round(emo_count / total_chars * 1000, 2)

    # ── Punctuation Profile ──
    fp.punctuation_profile = {
        "comma": text.count("，") / (total_chars or 1) * 100,
        "period": text.count("。") / (total_chars or 1) * 100,
        "semicolon": text.count("；") / (total_chars or 1) * 100,
        "colon": text.count("：") / (total_chars or 1) * 100,
        "question": text.count("？") / (total_chars or 1) * 100,
        "exclamation": text.count("！") / (total_chars or 1) * 100,
        "ellipsis": len(re.findall(r'\.{3,}|…{1,}', text)) / (total_chars or 1) * 100,
    }

    # ── Rhetorical ──
    metaphor_count = sum(text.count(m) for m in _METAPHOR_MARKERS)
    fp.metaphor_density = round(metaphor_count / total_chars * 1000, 2)
    para_matches = len(_PARALLELISM_MARKER.findall(text))
    fp.parallelism_density = round(para_matches / total_chars * 1000, 2)

    # ── Excerpts for few-shot ──
    excerpt_sentences = [s for s in sentences if 20 <= len(s) <= 120]
    if len(excerpt_sentences) > 3:
        step = max(1, len(excerpt_sentences) // 3)
        fp.excerpts = excerpt_sentences[::step][:5]
    else:
        fp.excerpts = excerpt_sentences[:5]

    return fp


def distill_files(file_paths: list[str], author: str) -> StyleFingerprint:
    """Distill style from multiple files and merge results."""
    fps = []
    total_text = ""
    for fp_path in file_paths:
        try:
            with open(fp_path, "r", encoding="utf-8") as f:
                text = f.read()
            total_text += text
            fps.append(distill_text(text, author, os.path.basename(fp_path)))
        except Exception as e:
            print(f"⚠️ 跳过 {fp_path}: {e}")

    if not fps:
        return StyleFingerprint(author=author)

    # Merge by re-distilling combined text (more accurate than averaging)
    merged = distill_text(total_text, author, f"{len(fps)} files")
    merged.sample_count = len(fps)
    return merged


def save_fingerprint(fp: StyleFingerprint, output_dir: str = None):
    """Save style fingerprint to JSON file."""
    out = Path(output_dir) if output_dir else STYLES_DIR
    out.mkdir(parents=True, exist_ok=True)
    fname = _safe_filename(fp.author)
    fpath = out / f"{fname}.json"
    fpath.write_text(json.dumps(fp.to_dict(), ensure_ascii=False, indent=2))
    return str(fpath)


def load_fingerprint(author_name: str) -> StyleFingerprint:
    """Load a saved style fingerprint."""
    fname = _safe_filename(author_name)
    fpath = STYLES_DIR / f"{fname}.json"
    if not fpath.exists():
        return None

    data = json.loads(fpath.read_text())
    fp = StyleFingerprint()
    for k, v in data.items():
        if hasattr(fp, k):
            setattr(fp, k, v)
    return fp


def list_fingerprints() -> list[str]:
    """List all saved style fingerprints (returns display names)."""
    if not STYLES_DIR.exists():
        return []
    names = []
    for f in sorted(STYLES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            author = data.get("author", f.stem)
            if author:
                names.append(author)
            else:
                names.append(f.stem)
        except (json.JSONDecodeError, IOError):
            names.append(f.stem)
    return names


def format_style_prompt(fp: StyleFingerprint, max_excerpts: int = 3) -> str:
    """Generate a style injection prompt from a fingerprint."""
    if not fp or not fp.author:
        return ""

    lines = [f"## 写作风格：{fp.author}"]
    lines.append(f"（基于 {fp.sample_count} 篇文本，共 {fp.sample_size_chars} 字分析）")
    lines.append("")

    # Core metrics
    lines.append("### 量化特征")
    lines.append(f"- 句长：均值 {fp.sentence_length_mean:.1f} 字，标准差 {fp.sentence_length_std:.1f}")
    sl_dist = ", ".join(f"{k}:{v}" for k, v in fp.sentence_length_histogram.items() if v > 0)
    lines.append(f"- 句长分布：{sl_dist}")
    lines.append(f"- 段长：均值 {fp.paragraph_length_mean:.0f} 字，每段 {fp.sentences_per_paragraph:.1f} 句")
    lines.append(f"- 对话占比：{fp.dialogue_ratio:.0%}")
    lines.append(f"- 动作密度：{fp.action_ratio:.3f}，描写密度：{fp.description_ratio:.3f}")
    lines.append(f"- 词汇丰富度：{fp.unique_word_ratio:.3f}（独词率），{fp.hapax_ratio:.3f}（罕用词率）")
    lines.append(f"- 转折词密度：{fp.transition_density:.1f}/千字")
    lines.append(f"- 语气词密度：{fp.modal_density:.1f}/千字")
    lines.append(f"- 形容词密度：{fp.adjective_density:.1f}/千字")
    lines.append(f"- 比喻密度：{fp.metaphor_density:.1f}/千字")
    lines.append("")

    # Top transitions
    top_trans = sorted(fp.transitions.items(), key=lambda x: -x[1])[:8]
    if top_trans:
        lines.append(f"常用转折词：{', '.join(f'{k}({v})' for k, v in top_trans)}")

    # Top sentence openers
    if fp.sentence_openers:
        openers_str = ", ".join(f'"{o["opener"]}"({o["count"]})' for o in fp.sentence_openers[:5])
        lines.append(f"常用句首：{openers_str}")

    # Punctuation habits
    pp = fp.punctuation_profile
    lines.append(f"标点习惯：逗号{pp.get('comma', 0):.1f}% 句号{pp.get('period', 0):.1f}% 分号{pp.get('semicolon', 0):.1f}%")

    # Excerpts (few-shot examples)
    if fp.excerpts:
        lines.append("")
        lines.append("### 风格示例（请严格模仿以下句式和节奏）")
        for i, ex in enumerate(fp.excerpts[:max_excerpts], 1):
            lines.append(f"{i}. {ex}")

    lines.append("")
    lines.append(f"写作要求：请以上述量化特征和示例为基准，模仿 {fp.author} 的风格进行写作。")
    lines.append(f"- 句子长度控制在 {fp.sentence_length_mean:.0f} 字左右")
    lines.append(f"- 对话占比约 {fp.dialogue_ratio:.0%}")
    lines.append(f"- 善用转折词：{', '.join(k for k, _ in top_trans[:5])}")

    return "\n".join(lines)


def compare_fingerprints(fp1: StyleFingerprint, fp2: StyleFingerprint) -> str:
    """Generate a human-readable comparison of two fingerprints."""
    lines = [
        f"# 风格对比：{fp1.author} vs {fp2.author}",
        "",
        "| 维度 | {fp1.author} | {fp2.author} | 差异 |",
        "|------|-------------|-------------|------|",
    ]

    metrics = [
        ("句长均值", fp1.sentence_length_mean, fp2.sentence_length_mean, ".1f"),
        ("句长标准差", fp1.sentence_length_std, fp2.sentence_length_std, ".1f"),
        ("段长均值", fp1.paragraph_length_mean, fp2.paragraph_length_mean, ".0f"),
        ("对话占比", fp1.dialogue_ratio * 100, fp2.dialogue_ratio * 100, ".0f%%"),
        ("词汇丰富度", fp1.unique_word_ratio, fp2.unique_word_ratio, ".3f"),
        ("转折词密度/千字", fp1.transition_density, fp2.transition_density, ".1f"),
        ("语气词密度/千字", fp1.modal_density, fp2.modal_density, ".1f"),
        ("比喻密度/千字", fp1.metaphor_density, fp2.metaphor_density, ".1f"),
    ]

    for name, v1, v2, fmt in metrics:
        diff = abs(v1 - v2)
        arrow = "←" if v1 > v2 else "→" if v2 > v1 else "="
        l1 = f"{v1:{fmt}}" if isinstance(v1, float) else str(v1)
        l2 = f"{v2:{fmt}}" if isinstance(v2, float) else str(v2)
        ld = f"{diff:{fmt}}" if isinstance(diff, float) else str(diff)
        lines.append(f"| {name} | {l1} | {l2} | {ld} {arrow} |")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Style Distiller — 从真实文本中提炼写作风格特征"
    )
    sub = parser.add_subparsers(dest="command")

    sp_distill = sub.add_parser("distill", help="从文本文件提炼风格")
    sp_distill.add_argument("file", help="文本文件路径")
    sp_distill.add_argument("--author", required=True, help="作者名称")
    sp_distill.add_argument("--output", default=None, help="输出目录 (默认: styles/)")

    sp_multi = sub.add_parser("distill-all", help="从目录批量提炼")
    sp_multi.add_argument("--corpus", required=True, help="文本文件目录")
    sp_multi.add_argument("--author", required=True, help="作者名称")
    sp_multi.add_argument("--output", default=None, help="输出目录")

    sp_inject = sub.add_parser("inject", help="生成风格注入 prompt")
    sp_inject.add_argument("style", help="风格名称（作者名）")
    sp_inject.add_argument("--format", choices=["prompt", "json"], default="prompt")

    sp_compare = sub.add_parser("compare", help="比较两个文本的风格")
    sp_compare.add_argument("file1")
    sp_compare.add_argument("file2")
    sp_compare.add_argument("--author1", default="文本1")
    sp_compare.add_argument("--author2", default="文本2")

    sp_list = sub.add_parser("list", help="列出已保存的风格指纹")

    args = parser.parse_args()

    if args.command == "list":
        fps = list_fingerprints()
        if fps:
            print(f"📋 已保存的风格指纹 ({len(fps)}):")
            for name in fps:
                fp = load_fingerprint(name)
                if fp:
                    print(f"   📌 {fp.author} — {fp.sample_size_chars} 字, {fp.sample_count} 样本")
                else:
                    print(f"   📌 {name}")
        else:
            print("⚠️  暂无保存的风格指纹")
        sys.exit(0)

    if args.command == "distill":
        fp = distill_files([args.file], args.author)
        path = save_fingerprint(fp, args.output)
        print(f"✅ 风格指纹已保存: {path}")
        print(f"   作者: {fp.author}")
        print(f"   样本: {fp.sample_size_chars} 字")
        print(f"   句长: {fp.sentence_length_mean:.1f} ± {fp.sentence_length_std:.1f}")
        print(f"   对话占比: {fp.dialogue_ratio:.0%}")
        print(f"   词汇丰富度: {fp.unique_word_ratio:.3f}")
        sys.exit(0)

    if args.command == "distill-all":
        corpus = Path(args.corpus)
        if not corpus.exists():
            print(f"❌ 目录不存在: {corpus}")
            sys.exit(1)
        files = sorted(corpus.glob("*.txt")) + sorted(corpus.glob("*.md"))
        if not files:
            print(f"❌ 目录中没有 .txt 或 .md 文件: {corpus}")
            sys.exit(1)
        print(f"📂 处理 {len(files)} 个文件...")
        fp = distill_files([str(f) for f in files], args.author)
        path = save_fingerprint(fp, args.output)
        print(f"✅ 风格指纹已保存: {path}")
        print(f"   作者: {fp.author}")
        print(f"   样本: {fp.sample_count} 文件, {fp.sample_size_chars} 字")
        print(f"   句长: {fp.sentence_length_mean:.1f} ± {fp.sentence_length_std:.1f}")
        sys.exit(0)

    if args.command == "inject":
        fp = load_fingerprint(args.style)
        if not fp:
            print(f"❌ 未找到风格指纹: {args.style}")
            print(f"   可用的风格: {', '.join(list_fingerprints())}")
            sys.exit(1)
        if args.format == "json":
            print(json.dumps(fp.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(format_style_prompt(fp))
        sys.exit(0)

    if args.command == "compare":
        fp1 = distill_text(
            Path(args.file1).read_text() if Path(args.file1).exists() else args.file1,
            args.author1, args.file1,
        )
        fp2 = distill_text(
            Path(args.file2).read_text() if Path(args.file2).exists() else args.file2,
            args.author2, args.file2,
        )
        print(compare_fingerprints(fp1, fp2))
        sys.exit(0)

    parser.print_help()

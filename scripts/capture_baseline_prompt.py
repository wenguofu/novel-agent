"""Capture the baseline DeepSeek system prompt for a known novel × chapter.

Used by M3.2 W5 to establish a regression baseline for prompt-quality
changes. Run from the project root:

    python scripts/capture_baseline_prompt.py

The output is written to docs/prompts/baseline_<novel>_vol01_ch001.md
with a metadata header and the full system_prompt as the body.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "portal"))

from context_builder import build_context
from datetime import datetime

# Adapted: M3.2 plan §T5.1 used the placeholder "yueguang_wenguo"; the
# real DB row is the Chinese title 月光吻过她的谎言 (the plan's pinyin
# guess didn't match the actual seeded name). This novel has the
# richest seeded project_meta + outline (8+ meta keys, vol-01 outline)
# and is the one the M3.2 audit cited most heavily.
NOVEL = "月光吻过她的谎言"
VOLUME = 1
CHAPTER_NUM = 1
STYLE = "辰东风 50%, 默认 50%"
INSTRUCTIONS = "请创作第 1 章"
MAX_TOKENS = 10_000


def main():
    result = build_context({
        "name": NOVEL,
        "volume": VOLUME,
        "chapter_num": CHAPTER_NUM,
        "style": STYLE,
        "instructions": INSTRUCTIONS,
        "max_tokens": MAX_TOKENS,
    })

    # Sanitize the novel name for the filename (Chinese is fine on
    # modern filesystems, but keep the slug predictable).
    novel_slug = NOVEL.replace("/", "_")
    out_path = os.path.join(
        os.path.dirname(__file__), "..",
        "docs", "prompts",
        f"baseline_{novel_slug}_vol{VOLUME:02d}_ch{CHAPTER_NUM:03d}.md",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    layer_summary = "\n".join(
        f"- {layer['name']}: {layer['tokens_used']} tokens"
        for layer in result["layers"]
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Baseline prompt — {NOVEL} vol-{VOLUME:02d} ch-{CHAPTER_NUM:03d}\n\n")
        f.write(f"**Captured:** {datetime.now().strftime('%Y-%m-%d')} (M3.2 W5)\n")
        f.write(f"**Total tokens:** {result['total_tokens']}\n")
        f.write(f"**Max tokens:** {result['max_tokens']}\n")
        f.write(f"**Layers:** {len(result['layers'])}\n\n")
        f.write(f"## Layer breakdown\n\n{layer_summary}\n\n")
        f.write("---\n\n")
        f.write("## System prompt\n\n")
        f.write("```\n")
        f.write(result["system_prompt"])
        f.write("\n```\n")

    print(f"Baseline prompt written to {out_path}")
    print(f"  Total tokens: {result['total_tokens']}")
    print(f"  Layers: {len(result['layers'])}")


if __name__ == "__main__":
    main()

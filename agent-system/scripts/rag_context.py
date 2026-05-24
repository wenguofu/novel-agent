#!/usr/bin/env python3
"""
RAG 自动上下文注入器 —— 在写作Agent启动时自动调用，注入最相关记忆。

用法：
    python3 scripts/rag_context.py <novel_path> [--chapter N] [--max-tokens 2000]

    输出: 标准格式的上下文文本，直接追加到 system-prompt 中。

这是 agent_tracker 的姊妹工具: agent_tracker 检查 Agent 是否全跑，
rag_context 注入长期记忆上下文。
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="RAG 自动上下文注入")
    parser.add_argument("novel_path", help="小说目录路径")
    parser.add_argument("--chapter", type=int, help="当前章节号")
    parser.add_argument("--volume", type=int, help="当前卷号")
    parser.add_argument("--max-tokens", type=int, default=2000, help="最大注入token")
    parser.add_argument("--mode", choices=["inject", "query"], default="inject",
                        help="注入模式: inject=自动上下文, query=自定义查询")
    parser.add_argument("--query", help="自定义查询 (mode=query时使用)")
    args = parser.parse_args()

    novel_path = Path(args.novel_path).resolve()
    novel_name = novel_path.name

    # Extract character names from characters.md for dynamic queries
    char_names = []
    chars_file = novel_path / "characters.md"
    if chars_file.exists():
        import re as _re2
        chars_text = chars_file.read_text(encoding="utf-8")
        # Match patterns like "- 姓名：XXX", "- **姓名**：XXX", "## XXX"
        found = _re2.findall(r'(?:姓名[：:]\s*|^##\s+)(.{1,6}?)(?:\s|$)', chars_text, _re2.MULTILINE)
        char_names = [n.strip() for n in found if n.strip() and len(n.strip()) >= 2][:8]
    if not char_names:
        char_names = ["主角"]

    script_dir = Path(__file__).parent
    query_script = script_dir / "rag_query.py"

    if not query_script.exists():
        print("❌ rag_query.py 未找到")
        sys.exit(1)

    if args.mode == "inject":
        # 自动推断卷号
        volume = args.volume
        chapter = args.chapter

        if not volume:
            # 尝试从路径推断
            for d in novel_path.rglob("vol-*"):
                if d.is_dir():
                    vol_match = __import__("re").search(r"vol-(\d+)", d.name)
                    if vol_match:
                        v = int(vol_match.group(1))
                        if volume is None or v > volume:
                            volume = v
            if not volume:
                volume = 1

        cmd = [
            sys.executable, str(query_script),
            novel_name,
            "--inject",
            f"--max-tokens={args.max_tokens}",
            f"--characters={','.join(char_names)}",
        ]
        if chapter:
            cmd.append(f"--chapter={chapter}")
        if volume:
            cmd.append(f"--volume={volume}")

    else:
        if not args.query:
            print("❌ --query 参数必填 (mode=query)")
            sys.exit(1)
        cmd = [
            sys.executable, str(query_script),
            novel_name, args.query,
            f"--limit={args.max_tokens // 200}",
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"⚠️  RAG查询失败: {result.stderr}")
            print("   (将继续写作，但无长期记忆上下文)")
            sys.exit(0)  # 不阻塞流程

        output = result.stdout.strip()
        if output:
            print(output)
        else:
            print("📭 RAG 记忆库为空 (请先运行 rag_index.py 构建索引)")
            print("   (将继续写作，但无长期记忆上下文)")

    except subprocess.TimeoutExpired:
        print("⚠️  RAG查询超时")
        print("   (将继续写作，但无长期记忆上下文)")
        sys.exit(0)
    except Exception as e:
        print(f"⚠️  RAG查询异常: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()

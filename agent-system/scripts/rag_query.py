#!/usr/bin/env python3
"""
RAG 记忆查询器 —— 语义搜索小说记忆库，返回最相关上下文。

用法：
    # 自然语言查询
    python3 scripts/rag_query.py <novel_name> "陈远山第一次遇到李闲的场景"

    # 带过滤器
    python3 scripts/rag_query.py <novel_name> "苏灵" --type character --limit 5

    # 上下文注入模式 (为写作Agent生成上下文)
    python3 scripts/rag_query.py <novel_name> --inject --chapter 75

    python3 scripts/rag_query.py <novel_name> --info  查看索引信息

依赖：chromadb, sentence-transformers
"""
import argparse
import json
import os
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# ============================================================
# 代理配置 (HuggingFace 模型加载需要)
# ============================================================
import os as _os
if not _os.environ.get("HF_ENDPOINT"):
    _os.environ.setdefault("ALL_PROXY", "socks5h://127.0.0.1:1080")
    _os.environ.setdefault("HTTPS_PROXY", "socks5h://127.0.0.1:1080")
    _os.environ.setdefault("HTTP_PROXY", "socks5h://127.0.0.1:1080")
    _os.environ.setdefault("HF_HUB_OFFLINE", "1")

EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
DB_DIR = Path.home() / ".hermes" / "novel_rag_db"

# ============================================================
# 上下文注入模板
# ============================================================
INJECT_TEMPLATE = """## 📚 RAG 记忆检索结果

以下是从全书记忆中检索到的最相关内容 ({total} chunks, ≤{max_tokens} tokens):

{results}

---
**使用说明**: 以上内容由语义搜索自动检索，请优先参考其中的人物状态、未回收伏笔、世界观规则。
如有矛盾，以正式设定文件 (`characters.md`, `world_bible.md`) 为准。
"""

RESULT_TEMPLATE = """### [{n}] {file_type} | {source}
**匹配度**: {score:.2f} | **字数**: {chars} | {extra_info}
```
{content}
```
"""


def get_collection(novel_name: str):
    """获取或创建 ChromaDB 集合"""
    import re, hashlib
    client = chromadb.PersistentClient(path=str(DB_DIR))
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', novel_name)
    safe_name = safe_name.strip('._-')
    if len(safe_name) < 3:
        safe_name = hashlib.md5(novel_name.encode()).hexdigest()[:16]
    try:
        return client.get_collection(safe_name)
    except Exception:
        print(f"❌ 未找到索引: {novel_name}")
        print(f"   请先运行: python3 scripts/rag_index.py novels/{novel_name}")
        sys.exit(1)


def show_info(novel_name: str):
    """显示索引信息"""
    collection = get_collection(novel_name)
    count = collection.count()
    info = collection.metadata if hasattr(collection, "metadata") else {}

    print(f"📊 索引信息: {novel_name}")
    print(f"   Chunks: {count}")
    if "created_at" in info:
        print(f"   创建时间: {info['created_at']}")
    if "last_updated" in info:
        print(f"   最后更新: {info['last_updated']}")

    # 统计各类型数量
    try:
        all_data = collection.get()
        types = {}
        chapters = set()
        for meta in all_data.get("metadatas", []):
            if meta:
                ft = meta.get("file_type", "unknown")
                types[ft] = types.get(ft, 0) + 1
                if "chapter" in meta:
                    chapters.add(meta["chapter"])
        print(f"\n📁 按类型分布:")
        for ft, cnt in sorted(types.items()):
            print(f"   {ft}: {cnt}")
        if chapters:
            print(f"\n📖 覆盖章节: ch-{min(chapters)} ~ ch-{max(chapters)} ({len(chapters)}章)")
    except Exception:
        pass


def build_filter(ftype: str = None, volume: int = None, chapter: int = None) -> dict:
    """构建 ChromaDB where 过滤条件"""
    conditions = []

    if ftype:
        conditions.append({"file_type": ftype})
    if volume is not None:
        conditions.append({"volume": volume})
    if chapter is not None:
        conditions.append({"chapter": chapter})

    if len(conditions) == 1:
        return conditions[0]
    elif len(conditions) > 1:
        return {"$and": conditions}
    return {}


def query_memory(novel_name: str, query: str, limit: int = 10, ftype: str = None,
                 volume: int = None, chapter: int = None) -> list[dict]:
    """执行语义搜索"""
    collection = get_collection(novel_name)

    # 加载模型
    model = SentenceTransformer(EMBED_MODEL)
    query_embedding = model.encode([query]).tolist()

    # 构建过滤
    where_filter = build_filter(ftype=ftype, volume=volume, chapter=chapter)

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=limit,
        where=where_filter if where_filter else None,
    )

    # 格式化结果
    formatted = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        formatted.append({
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "score": 1.0 - results["distances"][0][i] if results.get("distances") else 0,
            "source": meta.get("source_file", "?"),
            "file_type": meta.get("file_type", "?"),
            "title": meta.get("title", ""),
            "characters": meta.get("characters_mentioned", []),
            "volume": meta.get("volume"),
            "chapter": meta.get("chapter"),
            "chars": meta.get("char_count", 0),
        })

    return formatted


def print_results(results: list[dict]):
    """打印搜索结果"""
    if not results:
        print("🔍 未找到相关内容")
        return

    print(f"\n{'='*60}")
    print(f"🔍 搜索到 {len(results)} 个相关记忆片段")
    print(f"{'='*60}\n")

    for i, r in enumerate(results, 1):
        # 构建额外信息
        extras = []
        if r["volume"]:
            extras.append(f"卷{r['volume']}")
        if r["chapter"]:
            extras.append(f"ch-{r['chapter']:04d}")
        if r["characters"]:
            extras.append(f"人物: {', '.join(r['characters'])}")
        extra_str = " | ".join(extras) if extras else ""

        print(RESULT_TEMPLATE.format(
            n=i,
            file_type=r["file_type"],
            source=r["source"],
            score=r["score"],
            chars=r["chars"],
            extra_info=extra_str,
            content=r["content"][:600] + ("..." if len(r["content"]) > 600 else ""),
        ))


def inject_context(novel_name: str, chapter: int = None, volume: int = None,
                   max_tokens: int = 2000, limit: int = 15, characters: str = ""):
    """
    上下文注入模式: 自动为写作Agent生成关联上下文

    策略:
    1. 检索当前章节相关的最近事件
    2. 检索活跃人物的最新状态
    3. 检索未回收的伏笔
    4. 去重并压缩到 max_tokens
    """
    collection = get_collection(novel_name)
    all_results = []

    # 查询1: 章节相关内容
    if chapter and volume:
        ch_query = f"卷{volume} 第{chapter}章 大纲 剧情 伏笔"
        try:
            r1 = query_memory(novel_name, ch_query, limit=limit // 3)
            all_results.extend(r1)
        except Exception:
            pass

    # 查询2: 人物最新状态 (动态)
    char_names = [c.strip() for c in characters.split(",") if c.strip()]
    if not char_names:
        char_names = ["主角", "主要角色"]
    char_query = " ".join(char_names[:6]) + " 当前状态 最新进展 人物关系"
    try:
        r2 = query_memory(novel_name, char_query, limit=limit // 3, ftype="chapter")
        all_results.extend(r2)
    except Exception:
        pass

    # 查询3: 未回收伏笔 + 世界观规则
    foreshadow_query = "伏笔 未回收 待回收 秘密 揭示 线索 设定 规则 世界观"
    try:
        r3 = query_memory(novel_name, foreshadow_query, limit=limit // 3, ftype="plot_arc")
        all_results.extend(r3)
    except Exception:
        pass

    # 去重 (按ID)
    seen = set()
    unique_results = []
    for r in all_results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique_results.append(r)

    # 按匹配度排序
    unique_results.sort(key=lambda x: x["score"], reverse=True)

    # 截断到 max_tokens (粗略: 1中文≈1.5 token)
    total_chars = 0
    final_results = []
    char_limit = int(max_tokens * 0.7)  # 70% 作为token裕量

    for r in unique_results:
        if total_chars + len(r["content"]) > char_limit:
            break
        final_results.append(r)
        total_chars += len(r["content"])

    # 渲染
    rendered = ""
    for i, r in enumerate(final_results, 1):
        extras = []
        if r["volume"]:
            extras.append(f"卷{r['volume']}")
        if r["chapter"]:
            extras.append(f"ch-{r['chapter']:04d}")
        if r["characters"]:
            extras.append(f"角色: {', '.join(r['characters'][:3])}")
        extra_str = " | ".join(extras)

        rendered += RESULT_TEMPLATE.format(
            n=i,
            file_type=r["file_type"],
            source=r["source"],
            score=r["score"],
            chars=r["chars"],
            extra_info=extra_str,
            content=r["content"][:500] + ("..." if len(r["content"]) > 500 else ""),
        )

    context = INJECT_TEMPLATE.format(
        total=len(final_results),
        max_tokens=max_tokens,
        results=rendered,
    )

    print(context)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG 记忆查询器")
    parser.add_argument("novel", help="小说名称 (目录名)")
    parser.add_argument("query", nargs="?", help="搜索查询 (自然语言)")
    parser.add_argument("--type", dest="ftype", help="过滤文件类型 (chapter/character/plot_arc/...)")
    parser.add_argument("--volume", type=int, help="过滤卷号")
    parser.add_argument("--chapter", type=int, help="过滤章号")
    parser.add_argument("--limit", type=int, default=10, help="返回结果数 (默认10)")
    parser.add_argument("--inject", action="store_true", help="上下文注入模式")
    parser.add_argument("--max-tokens", type=int, default=2000, help="注入最大token数 (默认2000)")
    parser.add_argument("--characters", default="", help="逗号分隔的角色名列表 (注入模式用)")
    parser.add_argument("--info", action="store_true", help="显示索引信息")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")

    args = parser.parse_args()

    if args.info:
        show_info(args.novel)
        sys.exit(0)

    if not args.query and not args.inject:
        parser.print_help()
        sys.exit(1)

    if args.inject:
        inject_context(
            args.novel,
            chapter=args.chapter,
            volume=args.volume,
            max_tokens=args.max_tokens,
            limit=args.limit,
            characters=args.characters,
        )
    else:
        results = query_memory(
            args.novel, args.query,
            limit=args.limit,
            ftype=args.ftype,
            volume=args.volume,
            chapter=args.chapter,
        )

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print_results(results)

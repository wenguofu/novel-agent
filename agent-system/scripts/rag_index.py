#!/usr/bin/env python3
"""
RAG 记忆索引构建器 —— 将小说全文章节、设定文件分块嵌入并存入向量数据库。

用法：
    python3 scripts/rag_index.py <novel_path> [--rebuild]

    novel_path: 小说目录 (如 novels/光头闲人闯阴阳古墓)
    --rebuild:  重建已有索引 (默认增量更新)

依赖：chromadb, sentence-transformers
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings
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

# ============================================================
# 配置
# ============================================================
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
CHUNK_SIZE = 400   # 每块最大字符数 (中文约200-300 tokens)
CHUNK_OVERLAP = 80  # 块间重叠字符数
DB_DIR = Path.home() / ".hermes" / "novel_rag_db"

# 文件名→类型映射
FILE_TYPE_MAP = {
    "characters": "character",
    "world_bible": "world_building",
    "genre_bible": "genre_rules",
    "full_story_arc": "plot_arc",
    "volume_plan": "plot_arc",
    "project": "project_meta",
    "alias_registry": "reference",
    "current_status": "status",
    "outline": "outline",
    "ch-": "chapter",
}


def detect_file_type(filepath: str) -> str:
    """根据文件路径判断内容类型"""
    name = Path(filepath).name.lower().replace(".md", "")
    parent = Path(filepath).parent.name.lower()

    for key, ftype in FILE_TYPE_MAP.items():
        if key in name or key in parent:
            return ftype
    return "unknown"


def extract_metadata(filepath: str, content: str, novel_name: str) -> dict:
    """从文件内容和路径提取元数据"""
    ftype = detect_file_type(filepath)
    relpath = str(Path(filepath).relative_to(Path(filepath).parent.parent.parent))

    meta = {
        "novel": novel_name,
        "file_type": ftype,
        "source_file": relpath,
        "source_path": str(filepath),
    }

    # 章节类型: 提取卷号、章号
    ch_match = re.search(r"vol-(\d+).*?ch-(\d+)", relpath, re.IGNORECASE)
    if ch_match:
        meta["volume"] = int(ch_match.group(1))
        meta["chapter"] = int(ch_match.group(2))

    # 提取章节标题 (第一行 # 标题)
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        meta["title"] = title_match.group(1).strip()

    # 统计字数
    meta["char_count"] = len(content.replace("\n", "").replace(" ", ""))

    # 提取人物提及
    char_names = re.findall(r"(李闲|陈远山|王硕|苏灵|林望舒|唐一梨|陆星野)", content)
    if char_names:
        meta["characters_mentioned"] = list(set(char_names))

    return meta


def chunk_content(content: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """将长文本按块分割，保证句子完整性"""
    chunks = []
    start = 0
    text = content.strip()

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # 回退到最近的句子结束符
        if end < len(text):
            for sep in ["\n\n", "\n", "。", "；", "，", "、"]:
                pos = text.rfind(sep, start, end)
                if pos > start + chunk_size // 2:
                    end = pos + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else end

    return chunks


def build_chunk_id(source: str, idx: int) -> str:
    """生成唯一 chunk ID"""
    raw = f"{source}::{idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def index_novel(novel_path: str, rebuild: bool = False):
    """构建或更新小说向量索引"""
    novel_path = Path(novel_path).resolve()
    novel_name = novel_path.name

    if not novel_path.exists():
        print(f"❌ 小说目录不存在: {novel_path}")
        sys.exit(1)

    # 初始化 ChromaDB
    os.makedirs(DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    # ChromaDB 集合名限制: 3-512字符, [a-zA-Z0-9._-]
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', novel_name)
    safe_name = safe_name.strip('._-')
    if len(safe_name) < 3:
        safe_name = hashlib.md5(novel_name.encode()).hexdigest()[:16]
    collection_name = safe_name

    # 重建模式: 删除旧集合
    if rebuild:
        try:
            client.delete_collection(collection_name)
            print(f"🗑️  已删除旧索引: {collection_name}")
        except Exception:
            pass

    try:
        collection = client.get_collection(collection_name)
        print(f"📂 已有索引: {collection_name} ({collection.count()} chunks)")
    except Exception:
        collection = client.create_collection(
            name=collection_name,
            metadata={"novel_name": novel_name, "created_at": datetime.now().isoformat()},
        )
        print(f"✨ 新建索引: {collection_name}")

    # 加载嵌入模型
    print(f"⏳ 加载嵌入模型: {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)
    print("✅ 模型就绪")

    # 收集所有文件
    files_to_index = []
    for ext in ["*.md"]:
        for f in novel_path.rglob(ext):
            if f.is_file():
                files_to_index.append(f)

    # 过滤已有文件（增量模式）
    existing_sources = set()
    if not rebuild:
        try:
            existing = collection.get()
            for meta in existing.get("metadatas", []):
                if meta and "source_path" in meta:
                    existing_sources.add(meta["source_path"])
        except Exception:
            pass

    new_files = [f for f in files_to_index if str(f) not in existing_sources]
    print(f"\n📊 文件统计: 总计 {len(files_to_index)} 个, 新增 {len(new_files)} 个")

    if not new_files:
        print("✅ 索引已是最新，无需更新")
        return

    # 处理文件
    total_chunks = 0
    batch_size = 50
    batch_docs, batch_ids, batch_metas = [], [], []

    for i, filepath in enumerate(new_files, 1):
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            print(f"⚠️  跳过 {filepath.name}: {e}")
            continue

        if not content.strip():
            continue

        meta = extract_metadata(str(filepath), content, novel_name)
        chunks = chunk_content(content)

        for ci, chunk in enumerate(chunks):
            chunk_id = build_chunk_id(str(filepath), ci)
            batch_ids.append(chunk_id)
            batch_docs.append(chunk)
            batch_metas.append({**meta, "chunk_index": ci, "chunk_total": len(chunks)})

            if len(batch_ids) >= batch_size:
                # 嵌入并存入
                embeddings = model.encode(batch_docs).tolist()
                collection.add(
                    ids=batch_ids,
                    embeddings=embeddings,
                    documents=batch_docs,
                    metadatas=batch_metas,
                )
                total_chunks += len(batch_ids)
                batch_docs, batch_ids, batch_metas = [], [], []

        # 进度
        if i % 10 == 0:
            print(f"  进度: {i}/{len(new_files)} 文件, {total_chunks} chunks 已索引")

    # 剩余批次
    if batch_ids:
        embeddings = model.encode(batch_docs).tolist()
        collection.add(
            ids=batch_ids,
            embeddings=embeddings,
            documents=batch_docs,
            metadatas=batch_metas,
        )
        total_chunks += len(batch_ids)

    print(f"\n✅ 索引完成: {total_chunks} chunks, {len(new_files)} 文件")
    print(f"📍 数据库位置: {DB_DIR / collection_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG 记忆索引构建器")
    parser.add_argument("novel_path", help="小说目录路径")
    parser.add_argument("--rebuild", action="store_true", help="重建索引 (删除旧数据)")
    args = parser.parse_args()

    index_novel(args.novel_path, rebuild=args.rebuild)

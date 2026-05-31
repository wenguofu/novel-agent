"""
RAG Engine — Category-aware vector retrieval with token budgets.
Integrated with existing chromadb index and falls back to DB-only mode.
"""

import os
import sys
from pathlib import Path

# chromadb path — same as agent-system/scripts/rag_query.py
CHROMA_DB_DIR = Path.home() / ".hermes" / "novel_rag_db"

# Lazy imports: sentence-transformers/chromadb are heavy and may hang on network issues.
# Only import when actually needed (first call to _ensure_chroma()).
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
_model = None
_chroma_imported = False
_chroma_available = None

def _ensure_chroma():
    """Lazy-init chromadb + sentence-transformers. Returns True if available."""
    global _chroma_available, _chroma_imported, _model
    if _chroma_imported:
        return _chroma_available
    _chroma_imported = True
    try:
        import chromadb as _cb
        from sentence_transformers import SentenceTransformer as _ST
        globals()['chromadb'] = _cb
        globals()['SentenceTransformer'] = _ST
        _chroma_available = True
    except (ImportError, Exception):
        _chroma_available = False
    return _chroma_available

def _get_model():
    global _model
    if _model is None and _ensure_chroma():
        try:
            _model = SentenceTransformer(EMBED_MODEL)
        except Exception:
            pass
    return _model

CHROMA_AVAILABLE = property(lambda self: _ensure_chroma()) if False else None  # never True at import time

def _is_chroma_available():
    return _ensure_chroma()

# Import shared token utils
from token_utils import count_tokens


def _get_collection(novel_name):
    """Get chromadb collection for a novel. Returns None if unavailable."""
    if not CHROMA_AVAILABLE:
        return None
    import re, hashlib
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', novel_name).strip('._-')
        if len(safe_name) < 3:
            safe_name = hashlib.md5(novel_name.encode()).hexdigest()[:16]
        return client.get_collection(safe_name)
    except Exception:
        return None


def _query_chroma(novel_name, query_text, file_type=None, n_results=5,
                  volume=None, chapter=None):
    """Query chromadb with optional filters. Returns list of dicts."""
    collection = _get_collection(novel_name)
    if collection is None:
        return []

    # Build filter
    where = None
    conditions = []
    if file_type:
        conditions.append({"file_type": file_type})
    if volume is not None:
        conditions.append({"volume": volume})
    if chapter is not None:
        conditions.append({"chapter": chapter})
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    try:
        model = _get_model()
        embedding = model.encode([query_text]).tolist()

        results = collection.query(
            query_embeddings=embedding,
            n_results=min(n_results, 10),
            where=where,
        )

        formatted = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else [{}] * len(ids)
        distances = results.get("distances", [[]])[0] if results.get("distances") else [1.0] * len(ids)

        for i in range(len(ids)):
            meta = metas[i] if i < len(metas) else {}
            formatted.append({
                "id": ids[i] if i < len(ids) else "",
                "content": docs[i] if i < len(docs) else "",
                "score": 1.0 - distances[i] if i < len(distances) else 0,
                "source": meta.get("source_file", "?"),
                "file_type": meta.get("file_type", "?"),
                "title": meta.get("title", ""),
                "volume": meta.get("volume"),
                "chapter": meta.get("chapter"),
                "char_count": meta.get("char_count", 0),
            })
        return formatted
    except Exception:
        return []


def query_categories(novel_name, categories, total_max_tokens=10000):
    """
    Query chromadb for multiple categories with token budgets.

    Args:
        novel_name: str — novel project name
        categories: list of {category, query, max_tokens}
        total_max_tokens: int — hard cap on total tokens

    Returns:
        {results: [{category, chunks, tokens_used}], total_tokens, mode}
    """
    from token_budget import TokenBudget
    budget = TokenBudget(max_tokens=total_max_tokens)

    results = []
    for cat in categories:
        category = cat.get("category", "general")
        query_text = cat.get("query", "")
        max_tok = cat.get("max_tokens", 1000)
        file_type = cat.get("file_type")
        limit = cat.get("limit", 5)
        volume = cat.get("volume")
        chapter = cat.get("chapter")

        # Query chromadb
        chunks = _query_chroma(
            novel_name, query_text,
            file_type=file_type or category,
            n_results=limit,
            volume=volume, chapter=chapter,
        )

        # Apply token budget — collect chunks until budget exhausted
        collected = []
        tokens_used = 0
        allocated = budget.allocate(category, max_tok)

        for chunk in chunks:
            content = chunk.get("content", "")
            est = count_tokens(content)
            if tokens_used + est > allocated:
                break
            collected.append(chunk)
            tokens_used += est

        results.append({
            "category": category,
            "chunks": collected,
            "tokens_used": tokens_used,
            "tokens_requested": max_tok,
        })

    # Only count actual tokens consumed (from retrieved chunks)
    actual_total = sum(r["tokens_used"] for r in results)
    return {
        "results": results,
        "total_tokens": actual_total,
        "max_tokens": budget.max_tokens,
        "mode": "chromadb" if CHROMA_AVAILABLE else "db-only",
    }

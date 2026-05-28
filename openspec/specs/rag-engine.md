# rag-engine

## Purpose
Category-aware vector retrieval engine with per-category token budgets. Wraps the existing chromadb index with structured query support and graceful degradation.

## Architecture
```
rag_engine.py
  ├── CHROMA_AVAILABLE (bool) — chromadb + sentence-transformers presence check
  ├── _get_collection(novel) → chromadb.Collection | None
  ├── _query_chroma(novel, query, file_type, n_results, volume, chapter) → list[dict]
  │   └── Returns: [{id, content, score, source, file_type, title, volume, chapter, char_count}]
  └── query_categories(novel, categories, total_max_tokens) → {results, total_tokens, max_tokens, mode}
      └── categories: [{category, query, max_tokens, file_type?, limit?, volume?, chapter?}]
```

## API
```
POST /api/rag/query
  Request: {
    novel: string,
    queries: [{category, query, max_tokens, file_type?, limit?, volume?, chapter?}],
    total_max_tokens: int (default 10000)
  }
  Response: {
    success: true,
    results: [{category, chunks, tokens_used, tokens_requested}],
    total_tokens: int,
    max_tokens: int,
    mode: "chromadb" | "db-only"
  }
```

## Token Budget
- Uses `token_budget.py` TokenBudget for total enforcement
- Per-category: each query gets up to its `max_tokens` (subject to total remaining)
- Chunk selection: collects chunks until estimated tokens exceed allocation
- Actual `total_tokens` reflects only collected chunks (not allocated budget)

## Fallback Behavior
- If chromadb not installed → `mode: "db-only"`, returns empty chunks (no crash)
- If collection not found for novel → returns empty chunks (no crash)
- If query fails → empty chunks, logs silently

## ChromaDB Details
- Path: `~/.hermes/novel_rag_db`
- Model: `BAAI/bge-small-zh-v1.5` (lazy-loaded, singleton)
- Collection name: sanitized novel name (MD5 fallback for short names)
- Metadata filters: file_type, volume, chapter (AND-combined)

## Dependencies
- `chromadb` (optional — graceful degradation)
- `sentence-transformers` (optional)
- `token_budget.py`
- ChromaDB at `~/.hermes/novel_rag_db` (pre-built by agent-system/scripts/rag_index.py)

## Known Issues
- First call loads SentenceTransformer model (~2-5s, blocks request)
- No model caching across process restarts
- Chinese token estimation is approximate (1.5× chars)

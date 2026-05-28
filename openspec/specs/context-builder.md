# context-builder

## Purpose
Server-side 9-layer system prompt assembly engine. Replaces the v2 client-side `_buildSystemPrompt` with DB-driven on-demand context loading.

## Architecture
```
context_builder.py
  ├── CORE_INSTRUCTIONS (static)
  ├── build_context(params) → {system_prompt, layers, total_tokens}
  │   ├── Layer 0: 核心指令 (500 tok) — static
  │   ├── Layer 1: 项目元信息 (300 tok) — novels table
  │   ├── Layer 2: 章节上下文 (800 tok) — outlines + danger_issues + prev chapter
  │   ├── Layer 3: 角色上下文 (2000 tok) — characters table, top-5 relevant
  │   ├── Layer 4: 伏笔待办 (1500 tok) — foreshadowing filter by target_vol
  │   ├── Layer 5: 世界观 (1500 tok) — world_building filter by related_vol
  │   ├── Layer 6: 节奏情感 (500 tok) — pacing_control filter by vol/ch
  │   ├── Layer 7: 信息释放 (500 tok) — revelation_schedule filter by reveal_vol
  │   ├── Layer 8: 剧情弧线 (1000 tok) — plot_arcs filter by vol range
  │   └── Layer 9: 写作风格 (500 tok) — user style + instructions
  └── get_context_stats(novel, vol, ch) → {layers: [{name, available}]}
```

## API
```
POST /api/context/build
  Request: {novel, volume, chapter_num, style, instructions, max_tokens}
  Response: {success, system_prompt, layers: [{name, content, tokens_used}], total_tokens}

GET /api/context/stats/<novel>/<vol>/<ch>
  Response: {success, layers: [{name, available}], novel, volume, chapter}
```

## Token Budget
- Uses `token_budget.py` TokenBudget class
- Max total: 10000 (configurable via max_tokens param)
- Per-layer budgets: priorities defined in code, adjustable
- Actual tokens used may be less than allocated (DB may have less data)
- Rough estimator: Chinese chars × 1.5 + English words × 1.3

## Dependencies
- `content_db.py` — all DB reads
- `token_budget.py` — budget enforcement
- None on chromadb (DB-only mode by default; RAG integration in future)

## Known Issues
- Pacing/revelation layers return 0 tokens if tables have no data (expected — UI will populate)
- Token estimator is approximate; actual DeepSeek token count may differ
- No caching — rebuilds context on every call (acceptable, < 50ms for DB queries)

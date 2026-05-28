# OpenSpec Directory

## Active Specs

| Spec | Module | Status |
|------|--------|--------|
| [current-architecture](current-architecture.md) | Full system (v3) | ✅ Current |
| [domain-model](domain-model.md) | content_db.py — 12 tables | ✅ v3 |
| [context-builder](context-builder.md) | context_builder.py — 9-layer prompt | ✅ v3 |
| [rag-engine](rag-engine.md) | rag_engine.py — vector retrieval | ✅ v3 |
| [v3-target-architecture](v3-target-architecture.md) | Target design (PRD reference) | ✅ Archived |

## Archived Changes

| Change | Date | Specs |
|--------|------|-------|
| [novel-agent-v3](changes/archive/2026-05-25-novel-agent-v3/) | 2026-05-25 | domain-model, context-builder, rag-engine |

## Modules Not Yet Spec'd
- `app.py` — Flask routes (48 endpoints, needs API spec)
- `token_budget.py` — covered in context-builder.md
- `static/js/app.js` — frontend SPA (needs component spec)
- `agent-system/` — external scripts (has own documentation)

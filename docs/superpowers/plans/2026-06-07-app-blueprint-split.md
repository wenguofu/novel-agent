# M-Split-App: Blueprint Module Split (Harness [4] Future Work)

> **Status:** 📋 SCOPED — not yet started. Reserved for a dedicated multi-day execution cycle.
>
> **Source:** [Harness optimization plan item [4]](../../2026-05-30-harness-optimization-plan.md)

**Goal:** Split `portal/app.py` (currently 4250+ lines, growing) into Flask Blueprint modules organized by domain. Each Blueprint owns one resource group; `portal/app.py` becomes a thin factory that registers Blueprints and configures cross-cutting concerns (error handlers, logging, middleware, CORS).

**Architecture:** Flask Blueprints group related routes under a common URL prefix and a common module. After the split:
- `portal/app.py` shrinks to ~200 lines (factory + cross-cutting config only)
- Each `routes/<domain>.py` is a focused module owning one resource family
- Cross-cutting infrastructure (error handlers, logging middleware, health endpoint, CORS) stays in `app.py` or in dedicated modules under `portal/middleware/`

**Tech Stack:** Flask Blueprints (stdlib Flask), no new dependencies

---

## What's Done vs. What's Left

### ✅ Done
- All routes still work end-to-end (1107/1107 tests pass)
- Cross-cutting infrastructure is factored: `register_error_handlers(app)` ([harness [5]](../../)), `with_logging` + `health_tracker` ([harness [6]](../../)), `api_resilient` ([harness [7]](../../)), `_after_request_set_timing` middleware ([harness [9]](../../))
- Pydantic validation decorator ([harness [3]](../../) commit `a998e2d`) is ready to move with the routes

### ⏳ Remaining (this M-Split-App plan)

1. **Create `portal/routes/` package** — `__init__.py` + 5 submodules
2. **Create 5 Blueprint modules** — each owns one resource family
3. **Define Blueprint registration order** — some routes depend on others (e.g., `/api/novels/<name>/chapters/...` is registered after `/api/novels`); get the order right to avoid 404s
4. **Update imports in tests** — `tests/functional/conftest.py` may need the new module paths
5. **Verify all 1107+ tests still pass**

---

## Suggested File Structure

```
portal/
├── app.py                          # ~200 lines: factory + cross-cutting config
├── routes/
│   ├── __init__.py                 # exports all blueprints for app.py to register
│   ├── ai.py                       # /api/ai/* — chat, stream
│   ├── novels.py                   # /api/novels/* — create, list, edit-chapter, generate-chapter, optimize-chapter, review-chapter, chapters/bak, cleanup-bak, init/*, etc.
│   ├── reviews.py                  # /api/quality-report, /api/context/build, /api/rag/query, etc.
│   ├── export.py                   # /api/content/sync, /api/init/full, /api/export/* (future)
│   └── config.py                   # /api/config/*, /api/config-db/*, /api/wizard/*
```

**Existing route inventory (from `app.py:grep @app.route`):** 48 routes. Distribution estimate:
- `ai.py`: 2 routes (chat, stream)
- `novels.py`: 25+ routes (the bulk — all the per-novel endpoints)
- `reviews.py`: 5-8 routes (quality, context, rag, workflow)
- `export.py`: 5-8 routes (sync, init)
- `config.py`: 8-10 routes (config, config-db, wizard)

---

## Estimated Effort

| Task | Effort | Risk |
|---|---|---|
| 1. Create `routes/` package skeleton | 1 hour | None |
| 2. Move + adapt `ai.py` (smallest, good pilot) | 2-3 hours | Low (only 2 routes, no cross-BP dependencies) |
| 3. Move + adapt `config.py` | 3-4 hours | Medium (the most varied payloads, but no cross-BP dependencies) |
| 4. Move + adapt `export.py` + `reviews.py` | 4-6 hours | Medium (some routes call helper functions defined in `app.py`) |
| 5. Move + adapt `novels.py` (largest) | 1-2 days | **High** — 25+ routes, many helper functions, deep cross-BP dependencies (e.g., `api_novels/<n>/optimize-chapter` calls into `ai.py`'s `deepseek_chat`) |
| 6. Update conftest + run all tests | 2-3 hours | Medium (Flask test client uses app factory — must pass the new app, not the old one) |
| 7. Verify all 1107 tests pass | 1-2 hours | None (it's a verification step) |

**Total:** ~4-6 days of focused work, recommend a dedicated cycle with TDD-shaped test pass before each route is moved.

---

## Strategy: Bottom-Up Migration

The plan recommends a **bottom-up** approach where the smallest, lowest-risk Blueprints are moved first:

1. **Phase 1: `routes/ai.py`** — 2 routes, no cross-BP dependencies. If this works, the pattern is established.
2. **Phase 2: `routes/config.py`** — 8-10 routes, no cross-BP dependencies. Validates the Blueprint registration pattern with a slightly larger surface.
3. **Phase 3: `routes/export.py` + `routes/reviews.py`** — depends on helpers that may need to be moved to a shared module first.
4. **Phase 4: `routes/novels.py`** — the big one, deferred to last so the other Blueprints have stabilized.

After each phase, the test suite must pass 100%. If a test fails, the migration for that phase is not done.

---

## Cross-Cutting Concerns (Stay in `app.py`)

- `register_error_handlers(app)` — global, not per-Blueprint
- `@app.before_request` / `@app.after_request` for response time + request id
- `@app.route("/health")` — global health endpoint
- CORS configuration
- Static file serving (if any)
- App factory function `create_app()`

---

## Cross-BP Dependencies to Watch

These are the known dependencies between routes that will live in different Blueprints after the split. Each one needs a home — either a shared module, a re-import in the new Blueprint, or a deliberate refactor.

| Caller | Callee | Resolution |
|---|---|---|
| `novels.py: api_optimize_chapter` | `ai.py: deepseek_chat` | Import `deepseek_chat` from a shared `services/ai.py` module |
| `novels.py: api_review_chapter` | `reviews.py: helpers` | Move review helpers to a shared `services/review.py` |
| `novels.py: api_generate_chapter` | `ai.py: deepseek_chat` (via streaming) | Same as optimize-chapter |
| `config.py: api_config_save` | `db.py: write_config` | Re-import (no change) |
| `export.py: api_init_full` | multiple novel/review helpers | Likely needs a service module |

The pattern: anything that's called from 2+ Blueprints moves to `portal/services/<area>.py` and is re-imported by the Blueprints that need it.

---

## Task Decomposition (suggested)

1. **T1: Create `portal/routes/__init__.py`** — empty, just package marker
2. **T2: Move `ai.py`** — 2 routes, validate the pattern, run tests
3. **T3: Extract `services/ai.py`** — move `deepseek_chat` and AI helpers here so both `ai.py` and `novels.py` can import it
4. **T4: Move `config.py`** — 8-10 routes, run tests
5. **T5: Extract `services/config.py`** — move `get_active_deepseek_config`, `load_config` here
6. **T6: Move `export.py`** — sync, init routes
7. **T7: Move `reviews.py`** — quality-report, context, rag, workflow
8. **T8: Extract `services/reviews.py` + `services/context.py`** — review/context helpers
9. **T9: Move `novels.py`** — the big one, 25+ routes
10. **T10: Update `conftest.py`** — make sure tests import the new factory correctly
11. **T11: Update `portal/app.py`** — shrink to factory + cross-cutting config
12. **T12: Verify** — full 1107+ test suite passes

---

## Why This Is Deferred (Not Part of Harness [4]→DONE in This Session)

The harness optimization plan was scoped for "wire the existing infrastructure into the critical paths". Splitting a 4250-line `app.py` into 5 focused Blueprints is a structural refactor that:

- **Touches every route** in the system (high regression risk)
- **Requires extracting shared services** (medium refactor surface)
- **Demands careful Blueprint registration order** (test breakage if wrong)
- **Needs to be done bottom-up** to maintain test coverage at each step

The right execution is a 4-6 day dedicated cycle with TDD-shaped test verification at each phase, not a 1-day bolt-on. This plan (`2026-06-07-app-blueprint-split.md`) is the explicit scope for that future work.

---

## Verification Checklist (Run After Each Phase)

- [ ] `python3 -m pytest tests/ -q` shows **1107+ passed** (or the current count, no regressions)
- [ ] `python3 -m pytest tests/functional/test_inventory.py` (if it exists) confirms endpoint count is unchanged
- [ ] No circular imports — `python3 -c "import app; print('OK')"` succeeds
- [ ] No dead code — the moved functions are not still defined in `app.py`
- [ ] `verify_spec.py` (5/5) still passes

# Implementation Plan: Harness Optimization

## Phase 1: Infrastructure (Parallel)
- [-] [1] MySQL + SQLAlchemy: Replace sqlite3 with SQLAlchemy ORM, add Alembic migrations, connection pooling
- [x] [2] Prompt Template Engine: Extract all prompts to Jinja2 templates, PromptManager with caching
- [-] [3] Request Validation: Pydantic models for all API endpoints

## Phase 2: App Modularization
- [ ] [4] Split app.py into Blueprint modules (routes/ai.py, routes/novels.py, routes/reviews.py, routes/export.py, routes/config.py)
- [-] [5] Centralized error handling with exception hierarchy, remove silent pass patterns
- [-] [6] Structured logging throughout

## Phase 3: Resilience
- [-] [7] Circuit breaker + retry for DeepSeek API
- [-] [8] DB-as-primary storage, atomic transactions
- [-] [9] Health check endpoint, response time middleware

## Phase 4: Testing & Fixing
- [x] [10] Test agent: find bugs in optimized code
- [ ] [11] Dev agent: fix all found bugs
- [x] [12] Verification: run existing tests, confirm nothing broken

---

## Implementation Pointer

> **Status (2026-06-06):** 3/12 items DONE, 7 PARTIAL, 2 NOT DONE. The optimization infrastructure (new modules under `portal/`) was added in a single mega-commit `7c9d835` (2026-05-31 22:27 +0800) the same day this plan was written, but the integration into `portal/app.py` was not completed — the new modules exist and are partially wired, but the legacy code paths in `app.py` (raw sqlite3, raw `request.json`, silent `pass`, no `@app.errorhandler` for the new exception classes, no `@app.before_request`/`after_request` middleware) remain.
>
> | # | Item | Status | Commit(s) | Notes |
> |---|---|---|---|---|
> | 1 | MySQL + SQLAlchemy ORM + Alembic | 🟡 PARTIAL | `7c9d835`, `28b48bc` | `portal/db.py` (SQLAlchemy engine + `with transaction()`), `portal/models_orm.py` (declarative models), `portal/alembic/versions/0001_initial_schema.py`, `portal/repository.py` (SQLAlchemy repository) all exist; `requirements.txt` declares `sqlalchemy>=2.0` and a commented `# pymysql>=1.1` for MySQL. **But** `portal/content_db.py:get_db()` still returns a raw `sqlite3.Connection` (MySQL path is a deprecation-warning stub), and `app.py` has 5 `get_db()` calls vs 9 `repository`/`get_repo` references. |
> | 2 | Prompt Template Engine (Jinja2 + PromptManager) | ✅ DONE | `7c9d835` | `portal/prompt_manager.py` (Jinja2 `Environment` + LRU cache + Pydantic-validated template variables) exists; `portal/context_builder.py:60` imports `from prompt_manager import get_prompt_manager` and uses it. |
> | 3 | Pydantic request validation | 🟡 PARTIAL | `7c9d835` | `portal/models.py` (194 lines) defines 10 `BaseModel` request classes: `ChatRequest`, `StreamRequest`, `GenerateStreamRequest`, `CreateNovelRequest`, `GenerateChapterRequest`, `EditChapterRequest`, `EditOutlineRequest`, `DeepSeekConfigRequest`, `ReviewChapterRequest`, `SearchRequest`. **But** `app.py` has **0** `from models import` statements and **36** remaining `request.json` / `request.get_json` calls — no route actually uses Pydantic validation. |
> | 4 | Split app.py into Blueprint modules | ⏳ NOT DONE | — | `portal/routes/` directory does not exist; `portal/app.py` is **4080 lines** with all routes inline. No commit has split it. |
> | 5 | Centralized error handling, remove silent `pass` | 🟡 PARTIAL | `7c9d835` | `portal/errors.py` defines `NovelAgentError` base + `APIError`, `NotFoundError`, `ValidationError`, `DatabaseError`, `ConfigError`, `RateLimitError`, `GateBlockedError`, plus `safe_call`/`safe_db_call`/`safe_io_call` helpers and `register_error_handlers(app)`. `app.py:42-55` imports the exception classes + safe_* helpers, and `app.py:64` calls `register_error_handlers(app)`. **But** `safe_call`/`safe_db_call`/`safe_io_call` are imported but never used, and **10 silent `pass` exception-swallow patterns** remain in `app.py` (lines 93, 682, 793, 900, 1516, 1536, 2650, 2671, 2816, 2818). |
> | 6 | Structured logging throughout | 🟡 PARTIAL | `7c9d835` | `portal/logging_config.py` (272 lines) provides `StructuredLogger` (JSON format), `HealthTracker`, `avg_response_time`/`get_health`, and a `with_logging` decorator that adds `request_id` + timing + health. **But** `app.py` has only `import logging` (stdlib, 1 occurrence) and **0** `from logging_config import` statements — the new structured logger is not used by any route. |
> | 7 | Circuit breaker + retry for DeepSeek API | 🟡 PARTIAL | `7c9d835`, `2d45b4e` | `portal/resilience.py` (225 lines) provides `CircuitBreaker` (dataclass with thread-safe failure threshold + reset timeout), `with_retry` decorator (exponential backoff), and `ResponseTimeTracker` (`slow_threshold=10s`, `critical_threshold=30s`). `2d45b4e` hotfixed `ResponseTimeTracker` to use `RLock` (deadlock fix). **But** `app.py:343 deepseek_chat()` is a plain function with **0** `resilience`/`CircuitBreaker`/`with_retry` references — the resilience primitives are not applied to any API call. |
> | 8 | DB-as-primary storage, atomic transactions | 🟡 PARTIAL | `7c9d835` | `portal/db.py:127` defines `with transaction() as sess:` (SQLAlchemy session context manager). **But** `portal/content_db.py` has 11 raw `conn.execute()` / `cursor.execute()` calls and only 3 `conn.commit()` calls (lines 1377, 1451, 1498) — no `with conn:` blocks, no SQLAlchemy session usage; new writes are not wrapped in the new `transaction()` helper. |
> | 9 | Health check endpoint + response time middleware | 🟡 PARTIAL | `7c9d835`, `2d45b4e` | Primitives exist: `portal/db.py:143 check_db_health()`, `portal/logging_config.py:172 HealthTracker.get_health()`, `portal/resilience.py:150 ResponseTimeTracker`. **But** `app.py` has **no** `/health` or `/api/health` or `/api/status` route, **no** `@app.before_request`/`after_request` middleware, and **no** `X-Response-Time` header handling. The health/response-time primitives are defined but never exposed. |
> | 10 | Test agent: find bugs in optimized code | ✅ DONE | `6d6c3e8`, `1c077d5` | `agent-system/scripts/post_commit_review.sh` (post-commit hook) and `agent-system/scripts/agent_review_lib.py` (390 lines, 6-dim static-analysis runner) exist. `1c077d5` wired the full agent with 6 prompt files: `agent-system/prompts/review/{correctness,security,performance,tests,style,docs}.md`. `tests/functional/test_agent_cr.py` (159 lines) verifies the hook. `.code-reviews/` directory contains 71 commit reports. |
> | 11 | Dev agent: fix all found bugs | ⏳ NOT DONE | — | `agent-system/scripts/` has no `dev-agent`, `fix-issues`, `bug-fixer`, or `repair` script. `agent-system/` has no `CLAUDE.md` or `README.md` describing a fix workflow. The test agent (item 10) writes reports but nothing consumes them. |
> | 12 | Verification: run existing tests | ✅ DONE | — | **Verified 2026-06-06:** `python3 -m pytest tests/ -q` reports `1031 passed in 25.65s`. No regressions from the optimization infrastructure (the 7 PARTIAL items are dormant — the modules exist but are not yet wired into `app.py` route handlers, so they don't affect test results). |
>
> **Verified 2026-06-06:** 1031/1031 tests pass.
>
> **Remaining work (scope assessment):**
> - **Item 4 (Blueprint split, NOT DONE):** Largest single piece of remaining work. `portal/app.py` is 4080 lines; refactoring into 5 blueprint modules (`routes/ai.py`, `routes/novels.py`, `routes/reviews.py`, `routes/export.py`, `routes/config.py`) plus extracting route handlers from `app.py` is a multi-day refactor. Risk: circular-import surface between the new modules and the existing 13 portal/* modules that `app.py` already imports. Recommended as a dedicated plan (M-split-app).
> - **Item 11 (Dev agent, NOT DONE):** Medium scope. The test agent infrastructure is in place; the missing piece is a script (e.g. `agent-system/scripts/dev_fix.sh`) that reads `.code-reviews/<sha>.md`, parses findings, and dispatches a Claude/Cursor session with the report as input. Pattern after `post_commit_review.sh`. Could be ~1 day including tests.
> - **Items 1/3/5/6/7/8/9 (PARTIAL, integration work):** The infrastructure for all 7 PARTIAL items is already implemented (modules exist, are unit-tested, and don't break existing tests). What remains is **wiring the existing modules into `portal/app.py` route handlers** — replacing `get_db()` → `repository.get_repo()`, `request.json` → `Request.model_validate(request.json)`, silent `except: pass` → `safe_db_call(...)` / `NovelAgentError`, bare `logging.warning` → `StructuredLogger(...).warning(...)`, deepseek_chat → `with_resilience(with_retry(...))`, adding `@app.errorhandler(APIError)`, adding `/api/health` route + `@app.after_request` for response time. Estimated ~2-3 days of focused integration work; could be batched as a single "wire-up" plan. The infrastructure is sound — the gap is purely app.py adoption.

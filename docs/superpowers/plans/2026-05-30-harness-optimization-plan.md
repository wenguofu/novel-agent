# Implementation Plan: Harness Optimization

## Phase 1: Infrastructure (Parallel)
- [1] MySQL + SQLAlchemy: Replace sqlite3 with SQLAlchemy ORM, add Alembic migrations, connection pooling
- [2] Prompt Template Engine: Extract all prompts to Jinja2 templates, PromptManager with caching
- [3] Request Validation: Pydantic models for all API endpoints

## Phase 2: App Modularization
- [4] Split app.py into Blueprint modules (routes/ai.py, routes/novels.py, routes/reviews.py, routes/export.py, routes/config.py)
- [5] Centralized error handling with exception hierarchy, remove silent pass patterns
- [6] Structured logging throughout

## Phase 3: Resilience
- [7] Circuit breaker + retry for DeepSeek API
- [8] DB-as-primary storage, atomic transactions
- [9] Health check endpoint, response time middleware

## Phase 4: Testing & Fixing
- [10] Test agent: find bugs in optimized code
- [11] Dev agent: fix all found bugs
- [12] Verification: run existing tests, confirm nothing broken

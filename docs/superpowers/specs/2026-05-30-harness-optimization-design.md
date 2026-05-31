# Harness Engineering Optimization — novel-agent

## Scope: 5-Part Focused Optimization

### Part 1: MySQL + SQLAlchemy Migration
- Replace raw sqlite3 with SQLAlchemy ORM + MySQL driver
- Connection pooling via SQLAlchemy engine
- Keep FTS via MySQL FULLTEXT indexes
- Alembic for schema migrations
- Config via DATABASE_URL env var

### Part 2: Prompt Template Engine
- Extract all hardcoded system prompts from `context_builder.py` and `app.py` into `prompts/` directory
- Implement PromptManager with Jinja2 rendering + caching
- Pydantic schema validation for template variables
- Git-versioned prompt templates

### Part 3: Flask App Modularization
- Split `app.py` into Blueprint modules under `portal/routes/`
- Pydantic request/response models for all endpoints
- Centralized error handler with proper exception hierarchy
- Remove silent `except: pass` patterns

### Part 4: Engineering Constraints
- Structured logging via structlog
- Circuit breaker for DeepSeek API calls (tenacity)
- Response time middleware
- DB health check endpoint `/api/health`

### Part 5: DB-as-Primary Storage
- DB transactions for all writes
- Remove file→DB sync direction
- Keep DB→file export for EPUB/TXT/HTML
- Atomic chapter save with rollback on failure

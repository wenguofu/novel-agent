# Novel-Agent v3.2 Upgrade Guide

## Quick Start (Zero Code Changes!)

```bash
# Install new dependencies
pip install -r requirements-v2.txt

# Start with all v3.2 features enabled (no changes to existing files!)
cd portal && python run_v2.py
```

That's it! `run_v2.py` monkey-patches the old code at runtime — all v3.2 features activate automatically.

## What v3.2 Changes

1. **Unified DB**: All 24 tables (content + config + usage) in a single `content.db` (SQLite) or MySQL database. Old `config.db` and `usage.db` are auto-migrated and renamed to `.bak`.
2. **Volume-Scoped Prompts**: Context builder filters by current volume — no future spoilers, no irrelevant characters, tightly scoped foreshadowing.
3. **MySQL-Ready**: Alembic migrations, dialect-agnostic ORM, data migration script.

## New Files

| File | Purpose |
|------|---------|
| `portal/run_v2.py` | **DROP-IN LAUNCHER** — run this instead of `app.py` |
| `portal/models_orm.py` | 24 SQLAlchemy ORM models |
| `portal/repository.py` | Unified data access layer with dict-based API |
| `portal/db.py` | Updated with `ensure_unified_schema()` |
| `portal/init_unified_db.py` | Unified DB init + seed (replaces init_config_db.py) |
| `portal/alembic/` | Alembic migrations for MySQL |
| `scripts/migrate_sqlite_to_mysql.py` | SQLite→MySQL data migration |
| `scripts/apply_upgrade.py` | Auto-patch script (for permanent changes) |
| `scripts/verify_upgrade.py` | Verification test suite |
| `requirements-v2.txt` | Updated dependencies (+pymysql, +alembic)

## If You Want Permanent Changes (Optional)

Instead of using `run_v2.py`, you can permanently patch the old code. Run:

```bash
python scripts/apply_upgrade.py
```

This modifies `app.py` and `content_db.py` in-place (with `.bak` backups).

---

## MySQL Migration

```bash
pip install -r requirements-v2.txt
export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/novel_agent"
cd portal && alembic upgrade head
cd .. && python scripts/migrate_sqlite_to_mysql.py
```

### Fallback to SQLite
```bash
unset DATABASE_URL  # Uses default: sqlite:///portal/content.db
python portal/run_v2.py
```

---

## Verification

1. **Start portal**: `cd portal && python run_v2.py`
2. **Check DB**: `python portal/init_unified_db.py`
3. **Run tests**: `pytest tests/`
4. **Volume scoping**: Generate a chapter — system prompt should NOT contain future volume data
5. **MySQL**: Set `DATABASE_URL`, run migration, start portal

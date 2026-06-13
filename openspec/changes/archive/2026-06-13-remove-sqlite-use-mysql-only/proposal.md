## Why

`portal/` currently supports both SQLite and MySQL via `DATABASE_URL`. The dual-mode design has 6+ active SQLite branches (engine config, side-DB migration, raw `sqlite3` imports, `NullPool`, PRAGMA setup, `_migrate_sqlite_side_db`) that all have to be kept in sync with MySQL, increasing the surface area for bugs and slowing iteration on the MySQL-only production stack we actually run. Production data already lives in MySQL (`novel_agent` DB on localhost:3306, 28 tables populated via a prior partial migration of `scripts/migrate_sqlite_to_mysql.py`); the remaining SQLite data is the `usage.db.bak` history. We want one engine, one storage path, one migration story.

## What Changes

- **BREAKING**: Drop SQLite as a supported `DATABASE_URL` dialect. `DATABASE_URL` must begin with `mysql+pymysql://`. If unset, default to a localhost MySQL URL (no fallback to a `.db` file).
- Remove all raw `sqlite3` imports from `portal/` (`db.py`, `content_db.py`, `run_v2.py`, `app.py`); delete the `get_raw_connection` backward-compat shim, the `NullPool` + PRAGMA branch, and `_migrate_sqlite_side_db` (side-DB merging no longer applies — all tables already live in MySQL).
- Delete the `portal/content_db.py` SQLite DDL literal (`SCHEMA = """ CREATE TABLE ... AUTOINCREMENT ... """`) and `get_db()` SQLite branch; keep the module as a thin repository-re-export for backward import compat.
- Run `scripts/migrate_sqlite_to_mysql.py` against the production SQLite backups (`portal/content.db`, `portal/config.db`, `portal/usage.db.bak`) to seed any rows still missing in MySQL (e.g. `usage` and `daily_stats`).
- After successful migration: archive `portal/*.db` and `portal/*.db.bak` into `migration_backup/sqlite_snapshot_<ts>/` and add `portal/*.db*` to `.gitignore` to prevent re-commit.
- Update test fixtures in `tests/conftest.py` and `tests/unit/test_db.py` to use a `DATABASE_URL` fixture that points at a transient MySQL test database (or sqlite-for-tests only as an explicit, opt-in test backend — see design D3).
- Update `requirements.txt` and `requirements-v2.txt`: uncomment / require `pymysql>=1.1` (already there in v2), drop the `# pymysql>=1.1 # Uncomment for MySQL support` hint, document that MySQL is the only supported backend.
- Update `README.md`, `UPGRADE_GUIDE.md`, and `openspec/specs/current-architecture.md` to remove SQLite references.

## Capabilities

### New Capabilities

- `database-engine-mysql`: Single supported DB engine. The runtime must construct a SQLAlchemy `Engine` bound to `DATABASE_URL`, must reject startup if `DATABASE_URL` is unset or non-MySQL, and must expose health-check and migration helpers that assume MySQL semantics (utf8mb4, InnoDB, `LONGTEXT` for chapter content, `VARCHAR(255)` for unindexed string columns).
- `sqlite-archive-snapshot`: One-time export of all production SQLite files into `migration_backup/sqlite_snapshot_<UTC-timestamp>/` with a `MANIFEST.md` listing row counts per table. Originals are removed from the working tree after the snapshot is verified.

### Modified Capabilities

_None._ The existing `current-architecture` spec is a flat `.md` file (not a directory under the spec-driven schema) and is updated directly in the docs step rather than as a delta spec. The new capabilities (`database-engine-mysql`, `sqlite-archive-snapshot`) capture the contract; the prose spec is documentation, not source of truth.

## Impact

- **Code removed**:
  - `portal/db.py` — `DEFAULT_SQLITE_URL`, the `if DATABASE_URL.startswith("sqlite")` branch in engine config, `set_sqlite_pragmas` event listener, `get_raw_connection`, the `_migrate_sqlite_side_db` helper, and the SQLite branch in `ensure_unified_schema`. (~90 lines deleted.)
  - `portal/content_db.py` — `DB_PATH`, `get_db()` SQLite branch, the `SCHEMA` literal, the SQLite reset in `init_db()`. (~half the file.)
  - `portal/run_v2.py` — default URL setter (`os.environ.setdefault("DATABASE_URL", sqlite://...)`), raw `sqlite3` import + `_unified_db_path` helpers, the "raw sqlite3 override" comment block.
  - `portal/app.py` — top-of-file `import sqlite3 as _sqlite3`, the bare-except `import sqlite3 as _sq` in `api_usage_stats`, the `_sqlite3.connect(USAGE_DB_PATH)` block in `get_usage_stats`.
  - `portal/models_orm.py` — `sqlite:///...` fallback URLs in the `db_urls()` helper.
  - `portal/alembic/env.py` — SQLite fallback URL in `run_migrations_offline` and `run_migrations_online`.
- **Code added**:
  - `portal/db.py::validate_database_url()` — fail-fast at module import time when `DATABASE_URL` is empty or non-MySQL. Logs a clear error pointing to `mysql+pymysql://user:pass@host:3306/novel_agent`.
  - `tests/unit/test_db.py` — new test cases: `test_rejects_sqlite_url`, `test_rejects_empty_url`, `test_engine_uses_mysql_pool_config` (red→green TDD).
- **Data**:
  - `migration_backup/sqlite_snapshot_<ts>/` — read-only archive of the 3 production SQLite files (content.db, config.db, usage.db.bak) plus a `MANIFEST.md` with `sqlite3 ... "SELECT COUNT(*) FROM <table>"` output.
  - MySQL `novel_agent` database — gains rows in `usage` and `daily_stats` from `usage.db.bak` (currently empty in MySQL).
- **APIs**: no public API change — `DATABASE_URL` semantics tighten; the URL is read in the same 6+ places it was already read.
- **Dependencies**: `pymysql>=1.1` becomes a hard requirement (already present in `requirements-v2.txt`); the `# Uncomment for MySQL support` hint is removed. No new packages.
- **Test backend**: see design.md D3 — tests continue to use SQLite (`:memory:`) **only** through an explicit `TEST_DATABASE_URL` env var, and an opt-in fixture in `tests/conftest.py`. Production code paths never branch on this.

## 1. Pre-flight: snapshot + dry-run migration (TDD N/A — one-shot CLI)

- [x] 1.1 Create `migration_backup/sqlite_snapshot_<UTC-timestamp>/` and copy `portal/content.db`, `portal/config.db`, `portal/usage.db.bak` into it.
- [x] 1.2 Write `MANIFEST.md` with `sqlite3 <db> "SELECT COUNT(*) FROM <table>"` output for every table in the snapshot.
- [x] 1.3 Run `python scripts/migrate_sqlite_to_mysql.py --dry-run --export-dir migration_backup/sqlite_snapshot_<ts>` and confirm the validator reports clean (no orphan FKs).
- [x] 1.4 Document the snapshot location and the dry-run result in this task.

## 2. TDD red: write failing tests for the MySQL-only contract

- [x] 2.1 Add `tests/unit/test_db.py::test_rejects_empty_database_url` — sets `DATABASE_URL=""`, expects `RuntimeError` mentioning `mysql+pymysql://`. (RED)
- [x] 2.2 Add `tests/unit/test_db.py::test_rejects_sqlite_database_url` — sets `DATABASE_URL="sqlite:///portal/content.db"`, expects `RuntimeError` mentioning `mysql+pymysql://`. (RED)
- [x] 2.3 Add `tests/unit/test_db.py::test_accepts_mysql_database_url` — sets `DATABASE_URL="mysql+pymysql://u:p@localhost:3306/db"`, expects `validate_database_url()` to return without raising. (RED)
- [x] 2.4 Add `tests/unit/test_db.py::test_testing_env_bypasses_validation` — sets `TESTING=1` and `DATABASE_URL=""`, expects no raise. (RED)
- [x] 2.5 Add `tests/unit/test_db.py::test_no_sqlite3_import_in_portal` — runs `grep -rn "^import sqlite3\|^from sqlite3" portal/` in a subprocess, expects no matches. (RED — will fail until the SQLite branches are deleted in section 3.)
- [x] 2.6 Add `tests/conftest.py` autouse session fixture that sets `TESTING=1` and `TEST_DATABASE_URL=sqlite:///:memory:` before any `portal.*` import. (RED until 3.1 lands.)
- [x] 2.7 Run `pytest -q tests/unit/test_db.py tests/unit/test_init_unified_db.py` and confirm all 5 new tests fail with the expected reason (validator not yet implemented / SQLite imports still present).

## 3. TDD green: implement the MySQL-only contract

- [x] 3.1 In `portal/db.py`: add `validate_database_url(url: str | None = None) -> None` that raises `RuntimeError` when `url` (or `DATABASE_URL` if `url is None`) is empty or doesn't start with `mysql`, **unless** `os.environ.get("TESTING") == "1"`. Call it at the top of `db.py` (after `DATABASE_URL` is read, before any function definition).
- [x] 3.2 In `portal/db.py`: delete `DEFAULT_SQLITE_URL`, the `if DATABASE_URL.startswith("sqlite"):` branch in engine config (lines around 42–53), the `set_sqlite_pragmas` event listener (lines 66–73), `get_raw_connection()` (lines 224–237), and `_migrate_sqlite_side_db` (lines 262–320).
- [x] 3.3 In `portal/db.py`: replace the `if not DATABASE_URL.startswith("sqlite"):` gate around `_patch_unlengthed_strings_for_mysql` (line 252) with an unconditional call.
- [x] 3.4 In `portal/db.py`: in `ensure_unified_schema()` (line 240), delete the two `_migrate_sqlite_side_db(engine, "config.db")` / `_migrate_sqlite_side_db(engine, "usage.db")` calls.
- [x] 3.5 In `portal/db.py::check_db_health()`: replace `"engine": "sqlite" if DATABASE_URL.startswith("sqlite") else "mysql"` with `"engine": "mysql"`.
- [x] 3.6 In `portal/run_v2.py`: delete the `os.environ.setdefault("DATABASE_URL", f"sqlite:///{PORTAL_DIR}/content.db")` line (line 36). Update the `engine_type = "MySQL" if db_url.startswith("mysql") else "SQLite"` line to just `engine_type = "MySQL"` (line 38). Delete the `import sqlite3` block in `_seed_default_config_unified` (lines 85–87) and the `Override app's raw sqlite3 usage functions` comment block (lines 105+).
- [x] 3.7 In `portal/content_db.py`: delete `DB_PATH` (line 16), the `import sqlite3` branch in `get_db()` (lines 45–50), the entire `SCHEMA = """..."""` literal (line 73+), and the SQLite reset branch in `init_db()` (line 381+). Keep the public re-exports so legacy imports of `from content_db import get_chapter` continue to work.
- [x] 3.8 In `portal/app.py`: delete `import sqlite3 as _sqlite3` (line 18) and the `import sqlite3 as _sq` in `api_usage_stats` (line 789). Rewrite `get_usage_stats` (line 4452) to use `repository.get_repo().list_usage()` instead of a raw `sqlite3` query.
- [x] 3.9 In `portal/models_orm.py`: in the `db_urls()` helper (lines 608–614), drop the three `sqlite:///` fallback URLs — only return the MySQL URL.
- [x] 3.10 In `portal/alembic/env.py`: replace the SQLite fallback URL in `run_migrations_offline` and `run_migrations_online` with `mysql+pymysql://localhost:3306/novel_agent` (or read from `DATABASE_URL`).
- [x] 3.11 Run `pytest -q tests/unit/test_db.py tests/unit/test_init_unified_db.py` and confirm all 5 new tests now pass (GREEN). All previously-passing tests should still pass.

## 4. TDD refactor: tighten + docs

- [x] 4.1 Add `portal/*.db*` to `.gitignore`.
- [x] 4.2 Update `portal/repository.py` docstring: replace "no raw sqlite3 anywhere else" with "no raw DB-API access; everything goes through SQLAlchemy ORM".
- [x] 4.3 Update `openspec/specs/current-architecture.md`: drop the "SQLite (dev) / MySQL (production)" line, rename "MySQL Migration" → "Database Bootstrap", drop the SQLite PRAGMA sentence in "Data Access Layer".
- [x] 4.4 Update `README.md`: drop the SQLite mentions in the "Quickstart" and "Database" sections.
- [x] 4.5 Add a "Migrating from SQLite to MySQL" section to `UPGRADE_GUIDE.md` with the 5 numbered steps from the spec.
- [x] 4.6 Run the full test suite: `pytest -q tests/`. Confirm the baseline pass-rate is unchanged (no new failures from the refactor).

## 5. Backfill: run live migration + clean up

- [x] 5.1 Run the live migration: `DATABASE_URL='mysql+pymysql://root@localhost:3306/novel_agent' python scripts/migrate_sqlite_to_mysql.py`. Verify `usage` and `daily_stats` row counts in MySQL match the `usage.db.bak` counts.
- [x] 5.2 `rm portal/content.db portal/config.db portal/usage.db.bak`. Confirm `ls portal/*.db*` returns no matches.
- [x] 5.3 Smoke test: `DATABASE_URL='mysql+pymysql://root@localhost:3306/novel_agent' python portal/run_v2.py &`, hit `GET /api/novels` and `GET /api/usage/stats` from a curl, kill the server.

## 6. Verification

- [x] 6.1 Run `openspec validate --strict` — must pass with no failures.
- [x] 6.2 Run `pytest -q tests/` — full suite green.
- [x] 6.3 Run `grep -rn "sqlite" portal/ --include="*.py" | grep -v SQLAlchemy` — must be empty.
- [x] 6.4 Run `git status` — only intended files changed; no stray `.db` files.
- [x] 6.5 Invoke `superpowers:verification-before-completion` to audit the work.

## 7. Archive

- [x] 7.1 Run `opsx:archive remove-sqlite-use-mysql-only` to fold the change into the base specs.

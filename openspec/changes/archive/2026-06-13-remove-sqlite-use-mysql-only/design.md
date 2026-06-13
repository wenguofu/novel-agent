## Context

`portal/` was originally a 3-file SQLite app (`content.db` + `config.db` + `usage.db`). In v3.2 the codebase was refactored onto SQLAlchemy 2.0 and gained a `DATABASE_URL` switch: a URL starting with `sqlite:///` uses one of those files (with side-DB merging on first launch); a URL starting with `mysql+pymysql://` uses MySQL. Both paths share `models_orm.py` and `repository.py`; the dialect-specific code lives in `db.py` (engine kwargs, PRAGMA event listener, `_migrate_sqlite_side_db`), `content_db.py` (raw `sqlite3` DDL literal and `get_db()` branch), `run_v2.py` (default URL + raw-`sqlite3` overrides), and `app.py` (raw `import sqlite3 as _sqlite3` for usage stats).

State of the world (as of 2026-06-13):
- MySQL `novel_agent` database (localhost:3306) has all 28 tables created and the content from `content.db` (8 novels, 177 chapters, 27 characters, 13 outlines, plus world_building/plot_arcs/etc.) already migrated via a prior run of `scripts/migrate_sqlite_to_mysql.py`. The `usage` and `daily_stats` tables are still empty in MySQL.
- `portal/content.db` (production snapshot from the SQLite era, ~9 MB), `portal/config.db`, and `portal/usage.db.bak` still exist on disk; `portal/usage.db` is a 0-byte stub.
- `migration_backup/` already contains a JSON export of `content.db` tables.
- The `db.py` code has a MySQL compat helper (`_patch_unlengthed_strings_for_mysql`) that converts unlengthed `String` to `VARCHAR(255)`, indexed `Text` to `VARCHAR(255)`, and other `Text` to `LONGTEXT`. This stays — it's already MySQL-specific.
- Tests do not currently run against a real DB. `tests/conftest.py` patches `repository.get_repo()` to a fake. So removing SQLite is mostly a `portal/` cleanup, not a test-infrastructure rewrite.

Stakeholders: anyone running `python run_v2.py` locally (developer), anyone deploying the portal (ops), and any future contributor (must not have to choose a dialect).

## Goals / Non-Goals

**Goals:**
- One supported engine: MySQL via `mysql+pymysql://`. `DATABASE_URL` is required; if it's empty or non-MySQL, the process fails at import time with a clear error message.
- The working tree no longer contains live `portal/*.db` files; they live in a one-time `migration_backup/sqlite_snapshot_<ts>/` and are gitignored.
- The migration script finishes the data backfill: it must successfully populate `usage` and `daily_stats` from `usage.db.bak` (currently empty in MySQL).
- All public behavior (REST endpoints, repository methods, ORM models) is unchanged. The diff is the negative of the SQLite branches.
- `openspec validate --strict` passes; the test suite still passes (we keep any test-level SQLite-via-`:memory:` use behind an opt-in `TEST_DATABASE_URL`).

**Non-Goals:**
- No change to ORM models (no schema diff — the existing MySQL `LONGTEXT` / `VARCHAR(255)` patches already cover production).
- No new admin UI / migration endpoint. Data movement happens via the existing `scripts/migrate_sqlite_to_mysql.py` CLI, run once by a human.
- No Alembic / online migration framework integration. The schema is created via `Base.metadata.create_all` in `db.ensure_unified_schema()`, the same way it has been for both dialects.
- No test-infra change beyond the small fixture in D3. We are not setting up a docker-compose MySQL for CI in this change.
- No deletion of the `scripts/migrate_sqlite_to_mysql.py` script. The script stays as a one-time tool, and is still useful for the snapshot-to-MySQL backfill in this change. (Future: it can be moved to `scripts/archive/` once `usage.db.bak` is consumed.)
- No change to the `repository.py` API. The repository continues to expose dict-based methods.

## Decisions

### D1: Fail-fast on missing or non-MySQL `DATABASE_URL` (no silent SQLite default)

`portal/db.py` currently defaults `DATABASE_URL` to `sqlite:///<portal_dir>/content.db` if the env var is unset. The MySQL-only build replaces this with an explicit `validate_database_url()` call at module import time: it raises `RuntimeError("DATABASE_URL must be set to a MySQL URL like mysql+pymysql://user:pass@host:3306/novel_agent")` if the URL is empty or doesn't start with `mysql`. This is checked once, before the engine is created.

Alternatives considered:
- **Default to `mysql+pymysql://root@localhost:3306/novel_agent` and let MySQL connection errors propagate naturally** — risks silent confusion when MySQL isn't running locally and a developer sees a `pymysql.err.OperationalError` instead of "set DATABASE_URL". Rejected: the explicit error is much friendlier.
- **Default to a `MYSQL_TEST_URL` for `pytest`** — would conflict with the test fixture in D3. Rejected: tests use their own `TEST_DATABASE_URL` shim.

### D2: Tests continue to use SQLite-via-`:memory:` behind `TEST_DATABASE_URL` (opt-in only)

The existing test suite never touches a real MySQL instance — it monkey-patches `repository.get_repo()` to a `FakeRepo` and otherwise uses `db.get_session()` with whatever `DATABASE_URL` is set in the environment. After this change, that pattern stays, but any test that *does* spin up real SQLAlchemy must set `TEST_DATABASE_URL=sqlite:///:memory:` explicitly. The `portal/db.py::validate_database_url()` function returns early (allows startup) if `TESTING=1` is set in the environment, so test invocations don't have to re-implement the URL check.

The hook script `~/.claude/hooks/tdd-openspec-post-edit.sh` runs `pytest -q --no-cov tests/` after every Write/Edit. We update `.coveragerc` (or a new `tests/conftest.py` autouse fixture) to set `TESTING=1` and `TEST_DATABASE_URL=sqlite:///:memory:` before any `portal.*` import, so the validator doesn't crash on a real run.

Alternatives considered:
- **Convert all tests to use MySQL** — would require every developer (and CI) to have MySQL up. Too high a cost for the value (the tests don't actually test SQL dialect features; they test repository logic via a fake).
- **Use SQLite unconditionally in tests, even before this change** — that's effectively what the codebase already does. The only change here is making it explicit and gating the production validator.

### D3: Migration script is a one-shot CLI; no programmatic integration

`scripts/migrate_sqlite_to_mysql.py` is the canonical SQLite→MySQL mover. For this change, we:
1. Run it with `--export-only` to drop a JSON snapshot of the 3 production SQLite files into `migration_backup/sqlite_snapshot_<ts>/` (we *additionally* copy the raw `.db` files into the snapshot directory; the JSON is the existing behavior).
2. Run it again without `--export-only` to import into MySQL. This is what backfills `usage` and `daily_stats` from `usage.db.bak`.
3. After the import completes and the MySQL row counts match the SQLite counts, the SQLite files are removed from `portal/` and the snapshot is the only on-disk copy.

The script is left in place (not deleted) — it's a one-time tool that's still useful for disaster recovery from the snapshot. If a future change wants to retire it, that's a separate concern.

Alternatives considered:
- **Write a new Python API around the migration so `run_v2.py` can call it** — adds a runtime dependency between the launcher and a script that's meant to be run by a human. Rejected.
- **Alembic-style versioned migrations** — out of scope per the non-goals; the schema-sync helper is `Base.metadata.create_all` and it stays.

### D4: Keep `_patch_unlengthed_strings_for_mysql` (it's already MySQL-specific)

This helper walks the SQLAlchemy `MetaData`, converting unlengthed `String` to `VARCHAR(255)`, indexed `Text` to `VARCHAR(255)`, and other `Text` to `LONGTEXT`. It's gated on `not DATABASE_URL.startswith("sqlite")`. After this change, the gate becomes "always run before DDL emit". Renamed to `_apply_mysql_type_patches(metadata)` for clarity (it now reflects the only target, not an exception path).

### D5: Single `content_db.py` — keep module, remove SQLite DDL

`portal/content_db.py` currently has both a SQL DDL literal (using `INTEGER PRIMARY KEY AUTOINCREMENT`) and a thin repository re-export. After the change, the DDL literal and the `get_db()` SQLite branch are removed. The module keeps its name and its public re-exports (e.g. `from content_db import get_chapter` for any caller that imports from it). Internal imports already use `repository.get_repo()` directly; the legacy imports continue to work because the re-exports stay.

### D6: Gitignore `portal/*.db*` to prevent re-commit

`.gitignore` is updated to include `portal/*.db*`. This is the durable fix for "we removed the files, but `git status` doesn't list them because they were never tracked" — they were untracked already (per the initial git status: `?? migration_backup/` shows the new dir, no `?? portal/*.db`). The gitignore change prevents anyone from accidentally `git add portal/content.db` later.

## Risks / Trade-offs

- **Accidentally breaking a contributor's local SQLite workflow** → If a developer is still running `DATABASE_URL=sqlite:///...` locally, the new `validate_database_url()` will crash on import. **Mitigation**: the error message points to the correct MySQL URL format and the `scripts/migrate_sqlite_to_mysql.py` path. `UPGRADE_GUIDE.md` gets a "Migrating from SQLite to MySQL" section.
- **`db.py::validate_database_url()` is called at import time**, before pytest fixtures can set `TESTING=1` → **Mitigation**: a `tests/conftest.py` autouse session fixture sets `TESTING=1` and `TEST_DATABASE_URL=sqlite:///:memory:` *before* any `portal.*` import, so by the time `db.py` is imported, the validator sees `TESTING=1` and short-circuits.
- **Production restart with no `DATABASE_URL` set** crashes immediately at import → **Mitigation**: acceptable; the alternative (silent fallback) is exactly what we're trying to remove. The error message includes the exact `export DATABASE_URL=...` line.
- **The `usage.db.bak` may not import cleanly** (FK to a `daily_stats` id that doesn't exist in MySQL) → **Mitigation**: `scripts/migrate_sqlite_to_mysql.py` already does a `validate_migration()` pre-check that flags orphan FKs; we'll run it with `--dry-run` first and only commit the live import if dry-run reports clean.
- **Removing `_migrate_sqlite_side_db` deletes 50+ lines of code that "worked"** → **Mitigation**: the function is unreachable once `DATABASE_URL` must be MySQL, so any code that still imports it would also be unreachable. The diff is the negative of those branches; `git blame` traces them.
- **Tests using `sqlite3` import directly** (e.g. the `test_init_unified_db.py` if it asserts on a `.db` file) → **Mitigation**: TDD — write the new `test_db.py` cases first; if any test currently relies on the SQLite default, it will fail at red and we'll fix it as part of the green step.
- **`.env` files or deployment scripts that hardcode `sqlite:///`** → **Mitigation**: grep the repo for `sqlite:///` and update each. `scripts/migrate_sqlite_to_mysql.py` stays unchanged (it reads from SQLite by design).

## Migration Plan

The deployment is a one-shot data backfill + a code drop. Order matters.

1. **Snapshot** the existing SQLite files:
   ```bash
   ts=$(date -u +%Y%m%dT%H%M%SZ)
   mkdir -p migration_backup/sqlite_snapshot_$ts
   cp portal/content.db portal/config.db portal/usage.db.bak migration_backup/sqlite_snapshot_$ts/
   # generate MANIFEST.md
   ```
2. **Dry-run** the migration:
   ```bash
   DATABASE_URL='mysql+pymysql://root@localhost:3306/novel_agent' \
     python scripts/migrate_sqlite_to_mysql.py --dry-run --export-dir migration_backup/sqlite_snapshot_$ts
   ```
   The validator must report clean. If it reports orphan FKs, investigate before proceeding.
3. **Live import**:
   ```bash
   DATABASE_URL='mysql+pymysql://root@localhost:3306/novel_agent' \
     python scripts/migrate_sqlite_to_mysql.py
   ```
   Verify `usage` and `daily_stats` row counts in MySQL match the `usage.db.bak` counts.
4. **Code drop**: switch to a branch, apply the diff (db.py / content_db.py / run_v2.py / app.py / models_orm.py / alembic/env.py), update `.gitignore`, update README + UPGRADE_GUIDE + current-architecture.md.
5. **Restart** `python run_v2.py` and run a smoke test: `GET /api/novels`, `GET /api/usage/stats`, generate one chapter.
6. **Clean up**: `rm portal/*.db portal/*.db.bak` after the snapshot is verified. The `migration_backup/sqlite_snapshot_$ts/` directory is the only on-disk copy.

**Rollback strategy**: each step is independent.
- The data migration is additive (only `INSERT`, no `UPDATE` or `DELETE` on existing rows). If step 4 reveals a bug, the SQLite files in `portal/` are untouched (they were just `cp`-ed, not `mv`-ed) and the portal can be reverted to use them with the previous code.
- The code change is one commit (or two: TDD test-commit + impl-commit). `git revert` cleanly undoes it.
- The gitignore change is independent; it doesn't affect any tracked file.

## Open Questions

- **Should `scripts/migrate_sqlite_to_mysql.py` itself be removed in this change or left in place?** Currently left in place per D3. If the answer is "no, remove it" the change is straightforward: delete the script and update `current-architecture.md` to remove the "Data migration" line. **Decision deferred** — keeping it costs nothing and provides a recovery path.
- **Should we add a CI job that fails the build if `DATABASE_URL` is unset?** Out of scope per the non-goals; could be a follow-up.
- **Should `tests/conftest.py` add a one-line comment explaining why `TESTING=1` is set** to make the next reader's life easier? Yes, will be part of the test change.
- **Should we rename `_patch_unlengthed_strings_for_mysql` to `_apply_mysql_type_patches` per D4**, or keep the old name for minimal diff? **Decision deferred** — the rename is cosmetic; keeping the old name reduces the diff and the helper is still MySQL-specific either way. Default: keep the old name.

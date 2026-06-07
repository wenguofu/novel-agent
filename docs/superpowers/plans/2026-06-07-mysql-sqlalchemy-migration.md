# M-MySQL: MySQL + SQLAlchemy Migration (Harness [1] Future Work)

> **Status:** 📋 SCOPED — not yet started. Reserved for a dedicated multi-day execution cycle.
>
> **Source:** [Harness optimization plan item [1]](../../2026-05-30-harness-optimization-plan.md)

**Goal:** Replace the raw `sqlite3` access in `portal/content_db.py` with the SQLAlchemy infrastructure that already exists in `portal/db.py` + `portal/models_orm.py`, and verify the system works end-to-end on a real MySQL instance.

**Architecture:** The SQLAlchemy infrastructure is already implemented:
- `portal/db.py` (256 lines) — `get_engine()`, `get_session()`, `transaction()` context manager, MySQL connection pooling
- `portal/models_orm.py` (declarative models for all tables)
- `portal/alembic/versions/0001_initial_schema.py` (initial migration)
- `portal/repository.py` (SQLAlchemy repository layer with `get_repo()` factory)
- `requirements.txt` declares `sqlalchemy>=2.0` and `# pymysql>=1.1` (commented — needs to be uncommented for MySQL deployments)

The gap is that `portal/content_db.py` (1520 lines, the largest data-layer module) still uses raw `sqlite3` connections and bypasses the SQLAlchemy infrastructure. The 3 write paths were wrapped in `with conn:` atomic transactions in commit `b665707` (harness [8]), but they are still sqlite3, not SQLAlchemy.

**Tech Stack:** SQLAlchemy 2.0 ORM, Alembic, pymysql, Flask app context

---

## What's Done vs. What's Left

### ✅ Done (in this M-series session, 2026-06-07)
- `portal/db.py` SQLAlchemy engine + `transaction()` / `get_session()` context managers
- `portal/models_orm.py` declarative models
- `portal/repository.py` repository pattern
- `portal/alembic/versions/0001_initial_schema.py` initial migration
- [Harness [8] commit `b665707`](../../) — 3 write paths use `with conn:` for atomic transactions (sqlite3 layer)
- [Harness [3] commit `a998e2d`](../../) — Pydantic validation decorator + 5 critical routes wired

### ⏳ Remaining (this M-MySQL plan)

1. **Uncomment `pymysql>=1.1` in `requirements.txt`** — 1 line
2. **Run alembic migration on MySQL** — `alembic upgrade head` against `mysql+pymysql://user:pass@host:3306/dbname` to verify the schema applies cleanly
3. **Port `content_db.py` from sqlite3 to SQLAlchemy** — the big one. Each function needs to use `repository.get_repo()` (or the ORM session directly) instead of `get_db()` + raw `conn.execute()`. Risk: any function that uses `row['col']` access must be updated to `row.col` (SQLAlchemy ORM) or `result.scalar()` style.
4. **Add MySQL integration test to CI** — spin up a MySQL container (or use a service container in GitHub Actions), set `DATABASE_URL=mysql+pymysql://...`, run the full test suite
5. **Document the DATABASE_URL switch** — add a section to `README.md` explaining how to point the app at a real MySQL instance

---

## Estimated Effort

| Task | Effort | Risk |
|---|---|---|
| 1. Uncomment pymysql | 1 minute | None |
| 2. Run alembic on MySQL | 1-2 hours | Medium (schema drift between SQLite and MySQL — datetime, JSON columns, etc.) |
| 3. Port content_db.py | 2-3 days | High (1520 lines, 30+ functions, all need to switch to SQLAlchemy; some queries use SQLite-specific features like `INSERT OR IGNORE` and `datetime('now')`) |
| 4. MySQL CI test | 4-6 hours | Medium (CI infra — service container, wait-for-ready, env injection) |
| 5. README docs | 1-2 hours | None |

**Total:** ~3-4 days of focused work, recommend as a single dedicated cycle.

---

## File Structure

**Modify:**
- `requirements.txt` — uncomment `pymysql>=1.1`
- `portal/content_db.py` (1520 lines) — convert all `get_db()` callers to `repository.get_repo()` or `with transaction():`
- `README.md` — add MySQL deployment section
- `.github/workflows/ci.yml` (or equivalent) — add MySQL service + integration test job

**Create:**
- `tests/integration/test_mysql_backend.py` — spin up MySQL via testcontainers, set DATABASE_URL, run smoke tests

**Test (existing):**
- `tests/functional/test_atomic_writes.py` (7 tests) — should still pass on MySQL after the port
- `tests/unit/test_repository.py` — already covers the repository layer

---

## Task Decomposition (suggested)

1. **T1: Uncomment pymysql** — `requirements.txt` change, `pip install pymysql`, verify import
2. **T2: Schema validation** — `alembic upgrade head` against a local MySQL instance (Docker), document any schema differences (especially `datetime('now')` → `CURRENT_TIMESTAMP` and JSON columns)
3. **T3: Port helpers** — `_get_novel_id` and other small helpers in `content_db.py` switch to `repository.get_repo()` (these are low-risk, used widely)
4. **T4: Port write paths** — the 3 upsert_* functions (already wrapped in `with conn:`) move to `with transaction() as sess: sess.execute(...)` style
5. **T5: Port read paths** — the many `get_*` functions move to repository methods
6. **T6: MySQL integration test** — `tests/integration/test_mysql_backend.py` with testcontainers
7. **T7: CI integration** — add MySQL service to GitHub Actions
8. **T8: README** — document DATABASE_URL switch
9. **T9: Verify** — full test suite on both SQLite (existing CI) and MySQL (new CI), 1107+ tests pass on both

---

## Open Questions

- **Q1: Backward compatibility?** Should `content_db.get_db()` be kept as a sqlite3-only fallback, or removed entirely? The plan assumes **removed entirely** — `get_db()` is the only thing that needs to change.
- **Q2: Repository or raw ORM?** The plan recommends using `repository.get_repo()` for consistency with the existing test surface (`tests/unit/test_repository.py` already exercises this). Direct ORM usage is OK for the simple `get_*` functions but the upsert_* paths benefit from the repository's explicit upsert methods.
- **Q3: Migration story for existing data?** For a clean-slate deployment, this is a non-issue. For a production deployment with existing SQLite data, an `sqlite3 → MySQL` ETL step is needed (out of scope; document in README).

---

## Why This Is Deferred (Not Part of Harness [1]→DONE in This Session)

The harness optimization plan was scoped for "wire the existing infrastructure into the critical paths". The SQLAlchemy infrastructure is wired into the engine/factory layer and the 3 write paths are atomic via `with conn:` (sqlite3). The remaining work — porting all 30+ `content_db.py` functions to SQLAlchemy and adding MySQL CI — is a multi-day refactor that should be its own plan rather than a 1-day bolt-on to the harness plan.

This plan (`2026-06-07-mysql-sqlalchemy-migration.md`) is the explicit scope for that future work. The harness plan's [1] entry stays PARTIAL until this plan is executed.

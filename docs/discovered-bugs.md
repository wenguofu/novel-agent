# Discovered Bugs

Bugs found by the [Portal functional test suite](portal-ui-testing.md) and other
automated walkthroughs. Each entry: symptom → root cause → fix plan.

---

## BUG-001: `/api/usage/stats` returns 500 when `usage.db` is empty

**Severity:** Medium
**Found by:** [tests/functional/test_portal_endpoints.py::TestTopLevel::test_usage_stats](../tests/functional/test_portal_endpoints.py)
**Found on:** 2026-06-07

### Symptom

```bash
$ curl -sS http://localhost:35001/api/usage/stats
{
  "error": "no such table: usage",
  "success": false
}
```

The HTTP status is 500, not 200. The endpoint exists but cannot serve real data
until the `usage` table is created.

### Root Cause

[portal/app.py:4356](../portal/app.py) opens `USAGE_DB_PATH` directly with raw
`sqlite3.connect()` and runs `SELECT … FROM usage`. The `usage` table is
supposed to be created by the ORM via `ensure_unified_schema()`, but:

1. [`_init_usage_db()`](../portal/app.py) is a no-op (per harness [5] refactor
   in commit `b5324f2`).
2. `ensure_unified_schema()` is never called on Portal startup.
3. The endpoint reads from `USAGE_DB_PATH` (a side DB), not the unified
   `content.db` where the ORM actually manages schema.

So when a fresh Portal starts, `usage.db` is an empty 0-byte file, and the
endpoint hits `sqlite3.OperationalError: no such table: usage`.

### Why the test currently passes

`tests/functional/test_portal_endpoints.py::TestTopLevel::test_usage_stats`
accepts 200 OR 500 as valid, with a comment pointing here. This is a smoke
test for "endpoint exists and returns JSON"; the strict 200-assertion is
deferred until the bug is fixed.

### Fix Plan

Two options, pick one:

**Option A (smaller):** Make `_init_usage_db()` actually create the table on
Portal startup. Restore the original schema-creation logic that the no-op
removed. The `_init_usage_db` docstring even says "Do not add initialization
logic here" — that comment is now stale.

**Option B (cleaner, scoped for [1] MySQL):** Convert the endpoint to use the
ORM session via `repository.get_repo()`. The repo's `get_usage_stats()` method
goes through SQLAlchemy, which knows how to create the schema if it's missing
(when configured to). This is part of the broader content_db.py → SQLAlchemy
migration tracked in [2026-06-07-mysql-sqlalchemy-migration.md](2026-06-07-mysql-sqlalchemy-migration.md).

**Recommended:** Apply Option A immediately (1-2 hours, no design
implications), then Option B as part of the harness [1] migration.

### Workaround (for users)

Call any code path that writes a usage record (e.g. make one chat call) and
the table gets created via `log_token_usage()`. But the empty-DB state on
cold start is still a bug.

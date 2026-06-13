# Novel-Agent Upgrade Guide

## v3.4 — MySQL Only (2026-06-13)

The portal is now MySQL-only. SQLite is no longer a supported
backend. The `DATABASE_URL` env var must point at a MySQL URL or the
launcher refuses to start.

### Migrating from SQLite to MySQL

If you have existing data in `portal/content.db`, `portal/config.db`,
or `portal/usage.db.bak` (the production SQLite era), follow these
5 steps to move to MySQL.

1. **Set `DATABASE_URL`**:
   ```bash
   export DATABASE_URL='mysql+pymysql://user:password@host:3306/novel_agent'
   ```
2. **Snapshot the existing SQLite files** into
   `migration_backup/sqlite_snapshot_<UTC-timestamp>/`:
   ```bash
   ts=$(date -u +%Y%m%dT%H%M%SZ)
   mkdir -p migration_backup/sqlite_snapshot_$ts
   cp portal/content.db portal/config.db portal/usage.db.bak \
      migration_backup/sqlite_snapshot_$ts/
   ```
3. **Dry-run the migration** to validate FK integrity:
   ```bash
   DATABASE_URL='mysql+pymysql://user:pass@host:3306/novel_agent' \
     python scripts/migrate_sqlite_to_mysql.py --dry-run \
       --export-dir migration_backup/sqlite_snapshot_$ts
   ```
   The validator must report clean (no orphan FKs). If it doesn't,
   investigate before proceeding.
4. **Run the live migration**:
   ```bash
   DATABASE_URL='mysql+pymysql://user:pass@host:3306/novel_agent' \
     python scripts/migrate_sqlite_to_mysql.py
   ```
   Verify `usage` and `daily_stats` row counts in MySQL match the
   `usage.db.bak` counts:
   ```bash
   mysql -u user -p novel_agent -e \
     "SELECT 'usage' AS t, COUNT(*) AS n FROM usage
      UNION ALL SELECT 'daily_stats', COUNT(*) FROM daily_stats;"
   ```
5. **Remove the SQLite files** from the working tree:
   ```bash
   rm portal/content.db portal/config.db portal/usage.db.bak
   rm portal/content.db-shm portal/content.db-wal
   ```
   The `migration_backup/sqlite_snapshot_$ts/` directory is the
   read-only record of what was migrated; the gitignore entry
   `portal/*.db*` keeps the working tree clean going forward.

Restart the portal:
```bash
python portal/run_v2.py
```

---

## v3.2 (historical) — Unified DB + MySQL-ready

Earlier releases supported both SQLite and MySQL via `DATABASE_URL`.
That dual-mode design was removed in v3.4 — see "v3.4 — MySQL Only"
above for the migration steps.

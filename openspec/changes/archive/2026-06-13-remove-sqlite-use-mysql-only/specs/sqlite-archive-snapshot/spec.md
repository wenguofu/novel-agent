## ADDED Requirements

### Requirement: One-time snapshot of production SQLite files
The system SHALL provide a one-time `scripts/snapshot_sqlite_to_backup.sh` (or `python -m portal.scripts.snapshot_sqlite`) CLI that copies `portal/content.db`, `portal/config.db`, and `portal/usage.db.bak` into `migration_backup/sqlite_snapshot_<UTC-timestamp>/`. The CLI MUST refuse to run if `portal/*.db*` already exists in the working tree and the target directory is the same as the source.

#### Scenario: Snapshot creates the expected directory layout
- **WHEN** the CLI runs against a working tree that has `portal/content.db`, `portal/config.db`, `portal/usage.db.bak`
- **THEN** `migration_backup/sqlite_snapshot_<ts>/` exists and contains `content.db`, `config.db`, `usage.db.bak`, and `MANIFEST.md`

#### Scenario: MANIFEST lists row counts per table
- **WHEN** the snapshot CLI finishes
- **THEN** `MANIFEST.md` contains, for every table in each `.db` file, a line `<db>::<table> = <row_count>` generated via `sqlite3 <db> "SELECT COUNT(*) FROM <table>"`

### Requirement: Original SQLite files are removed after the snapshot is verified
The system SHALL remove `portal/content.db`, `portal/config.db`, and `portal/usage.db.bak` from the working tree after the migration script reports that all data is present in MySQL with matching row counts. The gitignore pattern `portal/*.db*` MUST be added to `.gitignore` to prevent re-commit.

#### Scenario: Files removed from portal/
- **WHEN** the MySQL row counts equal the SQLite row counts for every table (within a tolerance of 0)
- **THEN** `ls portal/*.db*` returns no matches and `git status` does not list any new untracked `.db` files

#### Scenario: gitignore prevents re-add
- **WHEN** `git check-ignore portal/content.db` runs after `.gitignore` is updated
- **THEN** the command exits 0 (file is ignored)

### Requirement: Snapshot is the single source of truth for pre-migration data
The system SHALL keep the `migration_backup/sqlite_snapshot_<ts>/` directory in version control as the read-only record of what was migrated. A future contributor MAY verify the snapshot by running `python scripts/migrate_sqlite_to_mysql.py --export-only --export-dir migration_backup/sqlite_snapshot_<ts>` and comparing the JSON output against the original SQLite files.

#### Scenario: Re-export from snapshot is deterministic
- **WHEN** `migrate_sqlite_to_mysql.py --export-only` runs against the snapshot directory
- **THEN** the resulting JSON files have the same row counts as the original SQLite files (byte-for-byte JSON equality is NOT required — only row-count equality)

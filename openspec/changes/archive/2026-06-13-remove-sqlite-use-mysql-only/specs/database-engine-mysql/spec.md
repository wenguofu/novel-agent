## ADDED Requirements

### Requirement: DATABASE_URL must be a MySQL URL at runtime
The system SHALL refuse to start if `DATABASE_URL` is unset, empty, or does not begin with `mysql+pymysql://`. The check MUST run at module import time (i.e. before any DB query) and MUST raise `RuntimeError` with a message that includes the expected URL format (`mysql+pymysql://user:pass@host:3306/novel_agent`).

#### Scenario: Empty DATABASE_URL crashes with a helpful error
- **WHEN** the portal starts with `DATABASE_URL=""` (or unset)
- **THEN** `portal.db` raises `RuntimeError` whose message contains the substring `mysql+pymysql://`

#### Scenario: SQLite URL is rejected
- **WHEN** the portal starts with `DATABASE_URL="sqlite:///portal/content.db"`
- **THEN** `portal.db` raises `RuntimeError` whose message contains `mysql+pymysql://`

#### Scenario: MySQL URL is accepted
- **WHEN** the portal starts with `DATABASE_URL="mysql+pymysql://user:pass@localhost:3306/novel_agent"`
- **THEN** `portal.db.get_engine()` returns a SQLAlchemy `Engine` whose `dialect.name == "mysql"`

### Requirement: MySQL connection pooling is configured by default
The system SHALL configure the SQLAlchemy engine with `pool_size=10`, `max_overflow=20`, `pool_recycle=3600`, and `pool_pre_ping=True` when `DATABASE_URL` is a MySQL URL.

#### Scenario: Pool kwargs are applied
- **WHEN** the engine is created from a MySQL URL
- **THEN** `engine.pool.size() == 10` and `engine.pool._max_overflow == 20`

### Requirement: MySQL-specific type patches run before DDL
The system SHALL apply the MySQL type-patch helper to every `Base.metadata.create_all` invocation. The helper MUST convert unlengthed `String` columns to `VARCHAR(255)`, convert indexed `Text` columns to `VARCHAR(255)`, and upgrade non-indexed `Text` columns to `LONGTEXT`.

#### Scenario: Unlengthed String becomes VARCHAR(255)
- **WHEN** the helper walks a model that declares `column = Column(String)` with no length
- **THEN** the emitted DDL for that column is `VARCHAR(255)`

#### Scenario: Indexed Text becomes VARCHAR(255)
- **WHEN** the helper walks a model whose `Text` column appears in an `Index(...)` or `UniqueConstraint(...)`
- **THEN** the emitted DDL for that column is `VARCHAR(255)`

#### Scenario: Non-indexed Text becomes LONGTEXT
- **WHEN** the helper walks a model whose `Text` column is NOT in any index
- **THEN** the emitted DDL for that column is `LONGTEXT`

### Requirement: Tests may bypass the URL validator
The system SHALL allow `portal.db.validate_database_url()` to return without error when the environment variable `TESTING=1` is set, even if `DATABASE_URL` is empty or set to a non-MySQL value.

#### Scenario: TESTING=1 bypasses validation
- **WHEN** `os.environ["TESTING"] == "1"` and `os.environ.get("DATABASE_URL", "") == ""`
- **THEN** `portal.db.validate_database_url()` returns without raising

#### Scenario: TESTING unset enforces validation
- **WHEN** `os.environ.get("TESTING")` is not `"1"` and `DATABASE_URL` is empty
- **THEN** `portal.db.validate_database_url()` raises `RuntimeError`

### Requirement: Health check reports MySQL
The system SHALL expose a `check_db_health()` function whose return value includes `"engine": "mysql"` when the engine is bound to a MySQL URL.

#### Scenario: Health check reports MySQL
- **WHEN** `check_db_health()` is called against a live MySQL engine
- **THEN** the returned dict contains `"engine": "mysql"` and `"status": "healthy"`

### Requirement: No raw sqlite3 import in production portal code
The system SHALL NOT import `sqlite3` (or any SQLite-specific stdlib module) from any `portal/*.py` file. Tests under `tests/` MAY use `sqlite3` directly because they exercise the test-only `TEST_DATABASE_URL` path.

#### Scenario: Grep finds no sqlite3 in portal/
- **WHEN** `grep -rn "^import sqlite3\|^from sqlite3" portal/` is run
- **THEN** the command exits with status 1 (no matches) and prints nothing

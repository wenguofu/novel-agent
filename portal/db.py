"""
Database Abstraction Layer — SQLAlchemy-based with SQLite/MySQL support.

Replaces raw sqlite3 connections with SQLAlchemy ORM for:
  - Connection pooling (even with SQLite via NullPool or QueuePool)
  - Easy MySQL migration (just change DATABASE_URL)
  - Alembic-compatible schema management
  - Transaction context managers for atomic writes
  - Unified single-DB approach (all tables in one database)

Usage:
    from db import get_session, transaction
    with transaction() as sess:
        sess.execute(...)
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# ── Engine Configuration ────────────────────────────────────────────────

# DATABASE_URL: sqlite:///path/to/content.db (default)
#               mysql+pymysql://user:pass@host:port/dbname (for MySQL)
DEFAULT_SQLITE_URL = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content.db')}"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URL)

# Engine configuration
_ENGINE_KWARGS = {
    "echo": os.environ.get("DB_ECHO", "").lower() == "true",
    "pool_pre_ping": True,  # Verify connections before use
}

if DATABASE_URL.startswith("sqlite"):
    _ENGINE_KWARGS.update({
        "connect_args": {"check_same_thread": False},
        "poolclass": NullPool,
    })
else:
    # MySQL/PostgreSQL — use connection pooling
    _ENGINE_KWARGS.update({
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "20")),
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "3600")),
    })

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, **_ENGINE_KWARGS)

        # SQLite pragmas for performance
        if DATABASE_URL.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragmas(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()

        logger.info(f"Database engine created: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session with auto-close."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def transaction() -> Generator[Session, None, None]:
    """Get a session with explicit transaction control.

    Usage:
        with transaction() as sess:
            sess.execute(text("INSERT INTO ..."))
            # auto-commits on success, rolls back on exception
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_health() -> dict:
    """Check database connectivity. Returns health status dict."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return {
            "status": "healthy",
            "database": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
            "engine": "sqlite" if DATABASE_URL.startswith("sqlite") else "mysql",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        }


def get_raw_connection():
    """Get a raw sqlite3 connection for backward compatibility.
    Only works with SQLite. Returns None for MySQL.
    """
    if not DATABASE_URL.startswith("sqlite"):
        logger.warning("Raw connection requested but not using SQLite")
        return None
    import sqlite3
    db_path = DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_unified_schema():
    """Ensure all tables (content + config + usage) exist in the primary database.

    For SQLite: merges config.db and usage.db tables into content.db.
    For MySQL: all tables already coexist in the same database.

    This is idempotent — runs CREATE TABLE IF NOT EXISTS for all models.
    """
    engine = get_engine()
    from models_orm import Base
    Base.metadata.create_all(engine)

    # For SQLite: migrate data from separate config.db and usage.db files
    if DATABASE_URL.startswith("sqlite"):
        _migrate_sqlite_side_db(engine, "config.db")
        _migrate_sqlite_side_db(engine, "usage.db")


def _migrate_sqlite_side_db(engine, side_db_name):
    """Copy data from a side SQLite DB (config.db / usage.db) into the unified DB.
    Renames source to .bak after successful migration.
    """
    import sqlite3

    db_path = DATABASE_URL.replace("sqlite:///", "")
    portal_dir = os.path.dirname(os.path.abspath(__file__))
    side_path = os.path.join(portal_dir, side_db_name)

    if not os.path.exists(side_path):
        return
    if os.path.abspath(side_path) == os.path.abspath(db_path):
        return  # Same file, nothing to migrate

    try:
        src = sqlite3.connect(side_path)
        src.row_factory = sqlite3.Row

        tables = [row[0] for row in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]

        total_rows = 0
        with engine.connect() as conn:
            for table in tables:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                if count > 0:
                    logger.info(f"Unified DB: {table} already has {count} rows, skipping")
                    continue

                rows = src.execute(f"SELECT * FROM {table}").fetchall()
                if not rows:
                    continue

                cols = [c[0] for c in src.execute(f"PRAGMA table_info({table})").fetchall()]
                col_list = ", ".join(cols)
                placeholders = ", ".join([f":{c}" for c in cols])

                for row in rows:
                    params = {c: row[c] for c in cols}
                    try:
                        conn.execute(text(
                            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
                        ), params)
                        total_rows += 1
                    except Exception:
                        pass
                conn.commit()

        src.close()
        logger.info(f"Unified DB: migrated {total_rows} rows from {side_db_name}")

        bak_path = side_path + ".bak"
        if not os.path.exists(bak_path):
            os.rename(side_path, bak_path)
            logger.info(f"Unified DB: renamed {side_db_name} → {side_db_name}.bak")
    except Exception as e:
        logger.warning(f"Unified DB migration for {side_db_name}: {e}")

"""
Database Abstraction Layer — SQLAlchemy-based, MySQL only.

Provides a single ``Engine`` and session factory for the portal,
backed by MySQL via ``DATABASE_URL`` (e.g. ``mysql+pymysql://user:pass@host:3306/db``).

The portal refuses to start without a MySQL ``DATABASE_URL`` unless
the ``TESTING=1`` environment variable is set (the test suite uses
``TESTING=1`` to opt into a permissive mode that allows the
SQLite-via-``:memory:`` path the rest of the test suite uses; the
runtime in production never sees ``TESTING=1``).

Usage:
    from db import get_session, transaction
    with transaction() as sess:
        sess.execute(...)
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# ── Engine Configuration ────────────────────────────────────────────────

# DATABASE_URL must be a MySQL URL. We do not provide a default; see
# ``validate_database_url`` for the fail-fast behavior at import time.
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def validate_database_url(url: Optional[str] = None) -> None:
    """Validate that ``url`` (or ``DATABASE_URL`` env var) is a MySQL URL.

    Raises ``RuntimeError`` if the URL is empty or does not begin with
    ``mysql``, unless ``TESTING=1`` is set in the environment (the test
    suite uses SQLite-via-``:memory:`` and opts into the permissive
    mode via ``tests/unit/conftest.py``).

    Called once at module import time below.
    """
    if os.environ.get("TESTING") == "1":
        return
    if url is None:
        url = os.environ.get("DATABASE_URL", "")
    if not url or not url.startswith("mysql"):
        raise RuntimeError(
            "DATABASE_URL must be set to a MySQL URL like "
            "'mysql+pymysql://user:pass@host:3306/novel_agent'. "
            f"Got: {url!r}. If you are running tests, set TESTING=1."
        )


# Run the validator at import time so the portal fails fast on bad config.
validate_database_url()

# Engine configuration
_ENGINE_KWARGS = {
    "echo": os.environ.get("DB_ECHO", "").lower() == "true",
    "pool_size": int(os.environ.get("DB_POOL_SIZE", "10")),
    "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "20")),
    "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "3600")),
    "pool_pre_ping": True,  # Verify connections before use
}

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the SQLAlchemy engine.

    Re-reads ``DATABASE_URL`` from the environment each call so the
    engine follows the current env (e.g. when a test fixture sets
    ``DATABASE_URL`` after the module is imported). The module-level
    global is just a default used at import time.
    """
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", DATABASE_URL)
        if not url:
            raise RuntimeError(
                "DATABASE_URL is empty. Set it to a MySQL URL like "
                "'mysql+pymysql://user:pass@host:3306/novel_agent' or, "
                "for tests, ensure TESTING=1 and the test fixture set "
                "DATABASE_URL."
            )
        _engine = create_engine(url, **_ENGINE_KWARGS)
        logger.info(
            f"Database engine created: "
            f"{url.split('@')[-1] if '@' in url else url}"
        )
    return _engine


def _patch_unlengthed_strings_for_mysql(metadata) -> None:
    """Walk every column in ``metadata``; fix three MySQL incompatibilities:

    1. Unlengthed ``String`` columns (89 of them in models_orm) become
       ``VARCHAR(255)`` so MySQL accepts the CREATE TABLE.
    2. ``Text`` columns that participate in an Index or UniqueConstraint
       are converted to ``String(255)`` — MySQL refuses to index BLOB/TEXT
       columns without an explicit key length, and giving it 255 is
       simpler than adding ``mysql_length=`` to every index.
    3. ALL other ``Text`` columns are upgraded to ``LONGTEXT`` — MySQL's
       default ``TEXT`` tops out at 65,535 bytes (≈16K utf8mb4 chars),
       and chapter ``content`` routinely exceeds that.

    Called from ``ensure_unified_schema()`` (and the migration script)
    before DDL is emitted. Skipped when ``DATABASE_URL`` is not MySQL
    (the test suite uses SQLite-via-``:memory:`` under ``TESTING=1``).
    """
    # No-op for non-MySQL engines (e.g. SQLite used in tests).
    if not DATABASE_URL.startswith("mysql"):
        return

    from sqlalchemy import String as _SAString, Text as _SAText
    from sqlalchemy.dialects.mysql import LONGTEXT
    DEFAULT_LEN = 255

    # First pass: build set of column names that are indexed
    indexed_cols = set()
    for table in metadata.tables.values():
        for idx in table.indexes:
            indexed_cols.update(idx.columns.keys())
        for uc in table.constraints:
            if hasattr(uc, "columns"):
                indexed_cols.update(c.name for c in uc.columns if c.name)

    patched_str = 0
    patched_txt_to_str = 0
    patched_txt_to_long = 0
    for table in metadata.tables.values():
        for col in table.columns:
            t = col.type
            # Order matters: ``Text`` is a subclass of ``String``, so the
            # Text check must come FIRST. Otherwise an indexed Text
            # column would silently get ``length=255`` on its existing
            # Text instance (still emitted as TEXT in DDL) instead of
            # being replaced with a real VARCHAR(255).
            if isinstance(t, _SAText) and col.name in indexed_cols:
                col.type = _SAString(DEFAULT_LEN)
                patched_txt_to_str += 1
            elif isinstance(t, _SAText):
                # Non-indexed Text → LONGTEXT (4 GB) so chapter content
                # (often >65K bytes) doesn't hit MySQL's TEXT ceiling.
                col.type = LONGTEXT()
                patched_txt_to_long += 1
            elif isinstance(t, _SAString) and getattr(t, "length", None) is None:
                t.length = DEFAULT_LEN
                patched_str += 1
    if patched_str or patched_txt_to_str or patched_txt_to_long:
        logger.info(
            f"MySQL type patches: patched {patched_str} unlengthed String "
            f"columns to VARCHAR({DEFAULT_LEN}), converted "
            f"{patched_txt_to_str} indexed Text columns to VARCHAR({DEFAULT_LEN}), "
            f"upgraded {patched_txt_to_long} non-indexed Text columns to LONGTEXT"
        )


def reset_engine(url: Optional[str] = None):
    """Reset engine + session factory singletons.

    Used by tests to honor a ``DATABASE_URL`` override. After calling,
    the next ``get_engine()`` call creates a fresh engine bound to
    ``url`` (or the current ``DATABASE_URL`` if not provided).
    """
    global _engine, _SessionLocal, DATABASE_URL
    if url is not None:
        DATABASE_URL = url
    # Dispose old engine to release file handles
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _SessionLocal = None


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
            "engine": "mysql",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        }


def ensure_unified_schema():
    """Ensure all tables exist in the MySQL database.

    Idempotent — runs ``CREATE TABLE IF NOT EXISTS`` for all models
    via ``Base.metadata.create_all``. The MySQL type patches are
    applied first so the emitted DDL uses ``VARCHAR(255)`` and
    ``LONGTEXT`` correctly.
    """
    engine = get_engine()
    from models_orm import Base
    _patch_unlengthed_strings_for_mysql(Base.metadata)
    Base.metadata.create_all(engine)

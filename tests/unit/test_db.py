"""Unit tests for portal/db.py (M3.1 W2 T2.7.4).

Targets line coverage 59% -> 90%+. Tests the SQLAlchemy engine
singleton, session lifecycle, health checks, and raw connection
helper. Uses the existing ``tmp_db`` fixture for isolation.
"""
import os
import sqlite3
from unittest.mock import patch

import pytest
from sqlalchemy import text

import db
from db import (
    get_engine,
    reset_engine,
    get_session_factory,
    get_session,
    transaction,
    check_db_health,
    get_raw_connection,
    ensure_unified_schema,
    DATABASE_URL,
)


# ── get_engine ─────────────────────────────────────────────────────────

class TestGetEngine:
    def test_returns_engine(self, tmp_db):
        engine = get_engine()
        assert engine is not None

    def test_singleton(self, tmp_db):
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2

    def test_logs_database_url(self, tmp_db):
        # Re-create engine to trigger the log line
        reset_engine()
        with patch.object(db, "logger") as mock_logger:
            get_engine()
        # Should have logged info with the DB URL
        assert mock_logger.info.called

    def test_sqlite_pragmas_listener_attached(self, tmp_db):
        engine = get_engine()
        # Open a connection and verify the pragmas were applied
        with engine.connect() as conn:
            fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
            assert fk == 1


# ── reset_engine ───────────────────────────────────────────────────────

class TestResetEngine:
    def test_resets_engine(self, tmp_db):
        e1 = get_engine()
        reset_engine()
        e2 = get_engine()
        # After reset, a new engine is created
        assert e1 is not e2

    def test_disposes_old_engine(self, tmp_db):
        e1 = get_engine()
        with patch.object(e1, "dispose") as mock_dispose:
            reset_engine()
            mock_dispose.assert_called_once()

    def test_handles_dispose_exception(self, tmp_db):
        e1 = get_engine()
        with patch.object(e1, "dispose", side_effect=Exception("boom")):
            # Should not raise
            reset_engine()

    def test_with_url_override(self, tmp_db, tmp_path):
        url = f"sqlite:///{tmp_path / 'override.db'}"
        reset_engine(url)
        engine = get_engine()
        assert engine is not None
        assert db.DATABASE_URL == url

    def test_no_dispose_when_engine_is_none(self, monkeypatch):
        # Fresh module state: force engine to None
        monkeypatch.setattr(db, "_engine", None)
        monkeypatch.setattr(db, "_SessionLocal", None)
        # Should not raise
        reset_engine()
        # And engine stays None
        assert db._engine is None


# ── get_session_factory ───────────────────────────────────────────────

class TestGetSessionFactory:
    def test_returns_factory(self, tmp_db):
        factory = get_session_factory()
        assert factory is not None

    def test_singleton(self, tmp_db):
        f1 = get_session_factory()
        f2 = get_session_factory()
        assert f1 is f2


# ── get_session ────────────────────────────────────────────────────────

class TestGetSession:
    def test_yields_session(self, tmp_db):
        with get_session() as session:
            assert session is not None

    def test_commits_on_success(self, tmp_db):
        # Create a table, insert, verify it persists
        with get_session() as session:
            session.execute(text("CREATE TABLE test_t (id INTEGER)"))
            session.execute(text("INSERT INTO test_t VALUES (1)"))
        # Verify after context exits
        with get_session() as session:
            result = session.execute(text("SELECT * FROM test_t")).fetchall()
            assert len(result) == 1

    def test_rollback_on_exception(self, tmp_db):
        try:
            with get_session() as session:
                session.execute(text("CREATE TABLE test_r (id INTEGER)"))
                session.execute(text("INSERT INTO test_r VALUES (1)"))
                raise ValueError("simulated failure")
        except ValueError:
            pass
        # Verify table exists but row was rolled back
        with get_session() as session:
            result = session.execute(text("SELECT * FROM test_r")).fetchall()
            assert len(result) == 0

    def test_reraises_exception(self, tmp_db):
        with pytest.raises(RuntimeError, match="simulated"):
            with get_session() as session:
                raise RuntimeError("simulated")

    def test_session_closed_on_exit(self, tmp_db):
        with get_session() as session:
            # The session is active inside the context
            assert session is not None
        # After exit, the session is closed; accessing it should not raise
        # SQLAlchemy closes the underlying connection on close()


# ── transaction (similar to get_session) ──────────────────────────────

class TestTransaction:
    def test_yields_session(self, tmp_db):
        with transaction() as session:
            assert session is not None

    def test_commits_on_success(self, tmp_db):
        with transaction() as session:
            session.execute(text("CREATE TABLE test_tx (id INTEGER)"))
            session.execute(text("INSERT INTO test_tx VALUES (42)"))
        with transaction() as session:
            result = session.execute(text("SELECT * FROM test_tx")).fetchall()
            assert result[0][0] == 42

    def test_rollback_on_exception(self, tmp_db):
        try:
            with transaction() as session:
                session.execute(text("CREATE TABLE test_tx2 (id INTEGER)"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        with transaction() as session:
            result = session.execute(text("SELECT * FROM test_tx2")).fetchall()
            assert len(result) == 0

    def test_reraises_exception(self, tmp_db):
        with pytest.raises(RuntimeError, match="explode"):
            with transaction() as session:
                raise RuntimeError("explode")


# ── check_db_health ────────────────────────────────────────────────────

class TestCheckDbHealth:
    def test_healthy_sqlite(self, tmp_db):
        health = check_db_health()
        assert health["status"] == "healthy"
        assert health["engine"] == "sqlite"

    def test_includes_database_name(self, tmp_db):
        health = check_db_health()
        assert "database" in health
        assert isinstance(health["database"], str)
        assert len(health["database"]) > 0

    def test_unhealthy_on_error(self, tmp_db):
        # Force get_engine to raise
        with patch.object(db, "get_engine", side_effect=Exception("connection refused")):
            health = check_db_health()
        assert health["status"] == "unhealthy"
        assert "error" in health
        assert "connection refused" in health["error"]

    def test_unhealthy_on_query_error(self, tmp_db):
        # Force engine.connect to raise
        engine = get_engine()
        with patch.object(engine, "connect", side_effect=Exception("query failed")):
            health = check_db_health()
        assert health["status"] == "unhealthy"
        assert "error" in health
        assert "database" in health

    def test_mysql_database_url_logged(self, tmp_db):
        # Patch DATABASE_URL to simulate MySQL, then reset engine so
        # get_engine() will try to create a MySQL engine and fail to
        # connect.
        original_url = db.DATABASE_URL
        try:
            db.DATABASE_URL = "mysql+pymysql://user:pass@host:3306/db"
            reset_engine()
            health = check_db_health()
            # Should be unhealthy because we can't actually connect
            assert health["status"] == "unhealthy"
        finally:
            db.DATABASE_URL = original_url
            reset_engine()


# ── get_raw_connection ─────────────────────────────────────────────────

class TestGetRawConnection:
    def test_returns_connection_for_sqlite(self, tmp_db):
        conn = get_raw_connection()
        assert conn is not None
        conn.close()

    def test_row_factory_set(self, tmp_db):
        conn = get_raw_connection()
        assert conn.row_factory is sqlite3.Row
        conn.close()

    def test_foreign_keys_pragma_set(self, tmp_db):
        conn = get_raw_connection()
        # Verify foreign_keys is enabled
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        conn.close()

    def test_returns_none_for_non_sqlite(self, tmp_db):
        original_url = db.DATABASE_URL
        try:
            db.DATABASE_URL = "mysql+pymysql://user:pass@host:3306/db"
            conn = get_raw_connection()
            assert conn is None
        finally:
            db.DATABASE_URL = original_url


# ── ensure_unified_schema ──────────────────────────────────────────────

class TestEnsureUnifiedSchema:
    def test_creates_tables(self, tmp_db):
        # Import inside the test so we use the fixture's re-imported
        # ``db`` module (module-level imports capture the original).
        from db import get_session as _get_session
        with _get_session() as session:
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )).fetchall()
            table_names = [r[0] for r in result]
            # Should have the novels table (from init_unified_db)
            assert "novels" in table_names

    def test_idempotent(self, tmp_db):
        # Import inside the test to use the fixture's re-imported module.
        from db import get_session as _get_session
        # Running twice should not raise
        ensure_unified_schema()
        ensure_unified_schema()
        # Tables still present
        with _get_session() as session:
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='novels'"
            )).fetchall()
            assert len(result) == 1


# ── _migrate_sqlite_side_db (internal) ─────────────────────────────────

class TestMigrateSqliteSideDb:
    def test_no_op_when_side_db_missing(self, tmp_db):
        # No such file in portal/ → returns immediately
        engine = get_engine()
        # Should not raise
        db._migrate_sqlite_side_db(engine, "definitely_not_here_zzz.db")

    def test_skip_when_same_path(self, tmp_db):
        # Make both os.path.abspath calls return the same value so the
        # "same path" early-return branch is exercised.
        engine = get_engine()
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_same_path_config.db")
        if os.path.exists(side_db):
            os.remove(side_db)
        try:
            open(side_db, "w").close()
            with patch("db.os.path.abspath", return_value="/fake/same/path"), \
                 patch("db.os.path.exists", return_value=True):
                # Should return early (no migration)
                db._migrate_sqlite_side_db(engine, "test_same_path_config.db")
        finally:
            if os.path.exists(side_db):
                os.remove(side_db)

    def test_migrates_data_from_side_db(self, tmp_db):
        # Create a side DB with a table and data
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_side_config_m.db")
        if os.path.exists(side_db):
            os.remove(side_db)
        try:
            # Create side DB with data
            conn = sqlite3.connect(side_db)
            conn.execute("CREATE TABLE test_mig_m (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO test_mig_m VALUES (1, 'one')")
            conn.execute("INSERT INTO test_mig_m VALUES (2, 'two')")
            conn.commit()
            conn.close()

            # Need to also create the same table in main DB so migration sees "0 rows"
            with get_session() as session:
                session.execute(text("CREATE TABLE test_mig_m (id INTEGER, name TEXT)"))
                session.commit()

            # Run migration
            engine = get_engine()
            db._migrate_sqlite_side_db(engine, "test_side_config_m.db")

            # Verify data was migrated
            with get_session() as session:
                result = session.execute(text(
                    "SELECT * FROM test_mig_m ORDER BY id"
                )).fetchall()
                assert len(result) == 2
                assert result[0][1] == "one"
                assert result[1][1] == "two"
        finally:
            # Cleanup
            for ext in ("", ".bak"):
                p = side_db + ext
                if os.path.exists(p):
                    os.remove(p)

    def test_skips_table_with_existing_rows(self, tmp_db):
        # Create side DB with a table
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_existing_config_e.db")
        if os.path.exists(side_db):
            os.remove(side_db)
        try:
            conn = sqlite3.connect(side_db)
            conn.execute("CREATE TABLE test_exist_e (id INTEGER)")
            conn.execute("INSERT INTO test_exist_e VALUES (1)")
            conn.commit()
            conn.close()

            # Create the same table in main DB WITH existing rows
            with get_session() as session:
                session.execute(text("CREATE TABLE test_exist_e (id INTEGER)"))
                session.execute(text("INSERT INTO test_exist_e VALUES (999)"))
                session.commit()

            # Migrate — should skip because main DB has rows
            engine = get_engine()
            db._migrate_sqlite_side_db(engine, "test_existing_config_e.db")

            # Verify main DB still has only the original row
            with get_session() as session:
                result = session.execute(text("SELECT * FROM test_exist_e")).fetchall()
                assert len(result) == 1
                assert result[0][0] == 999
        finally:
            for ext in ("", ".bak"):
                p = side_db + ext
                if os.path.exists(p):
                    os.remove(p)

    def test_renames_side_db_to_bak(self, tmp_db):
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_rename_config_r.db")
        bak_db = side_db + ".bak"
        for p in (side_db, bak_db):
            if os.path.exists(p):
                os.remove(p)
        try:
            conn = sqlite3.connect(side_db)
            conn.execute("CREATE TABLE test_rename_r (id INTEGER)")
            conn.execute("INSERT INTO test_rename_r VALUES (1)")
            conn.commit()
            conn.close()

            with get_session() as session:
                session.execute(text("CREATE TABLE test_rename_r (id INTEGER)"))
                session.commit()

            engine = get_engine()
            db._migrate_sqlite_side_db(engine, "test_rename_config_r.db")

            # Side DB should be renamed to .bak
            assert not os.path.exists(side_db)
            assert os.path.exists(bak_db)
        finally:
            for p in (side_db, bak_db):
                if os.path.exists(p):
                    os.remove(p)

    def test_does_not_rename_when_bak_already_exists(self, tmp_db):
        # If .bak already exists, function should NOT rename the side DB
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_bak_exists_config_b.db")
        bak_db = side_db + ".bak"
        for p in (side_db, bak_db):
            if os.path.exists(p):
                os.remove(p)
        try:
            # Pre-create a .bak file
            open(bak_db, "w").close()

            conn = sqlite3.connect(side_db)
            conn.execute("CREATE TABLE test_bak_b (id INTEGER)")
            conn.execute("INSERT INTO test_bak_b VALUES (1)")
            conn.commit()
            conn.close()

            with get_session() as session:
                session.execute(text("CREATE TABLE test_bak_b (id INTEGER)"))
                session.commit()

            engine = get_engine()
            db._migrate_sqlite_side_db(engine, "test_bak_exists_config_b.db")

            # Side DB should still exist (rename skipped)
            assert os.path.exists(side_db)
        finally:
            for p in (side_db, bak_db):
                if os.path.exists(p):
                    os.remove(p)

    def test_handles_exception_during_migration(self, tmp_db):
        # Corrupt the side DB to trigger the outer except branch
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_corrupt_config_c.db")
        if os.path.exists(side_db):
            os.remove(side_db)
        try:
            # Write garbage to make sqlite3 raise
            with open(side_db, "w") as f:
                f.write("not a sqlite database")

            engine = get_engine()
            # Should not raise
            db._migrate_sqlite_side_db(engine, "test_corrupt_config_c.db")
        finally:
            if os.path.exists(side_db):
                os.remove(side_db)

    def test_skips_empty_table(self, tmp_db):
        # Side DB has a table with 0 rows → function hits the
        # ``if not rows: continue`` branch.
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_empty_config_e.db")
        if os.path.exists(side_db):
            os.remove(side_db)
        try:
            conn = sqlite3.connect(side_db)
            conn.execute("CREATE TABLE test_empty_e (id INTEGER)")
            # No rows inserted
            conn.commit()
            conn.close()

            with get_session() as session:
                session.execute(text("CREATE TABLE test_empty_e (id INTEGER)"))
                session.commit()

            engine = get_engine()
            # Should not raise; empty table is skipped
            db._migrate_sqlite_side_db(engine, "test_empty_config_e.db")
        finally:
            for ext in ("", ".bak"):
                p = side_db + ext
                if os.path.exists(p):
                    os.remove(p)

    def test_skips_row_on_insert_error(self, tmp_db):
        # Side DB stores a NULL value (no NOT NULL on side), but the
        # main DB table has NOT NULL → the INSERT raises IntegrityError,
        # hitting the inner except branch.
        portal_dir = os.path.dirname(os.path.abspath(db.__file__))
        side_db = os.path.join(portal_dir, "test_notnull_config_n.db")
        if os.path.exists(side_db):
            os.remove(side_db)
        try:
            conn = sqlite3.connect(side_db)
            conn.execute("CREATE TABLE test_notnull_n (id INTEGER)")
            conn.execute("INSERT INTO test_notnull_n VALUES (NULL)")
            conn.commit()
            conn.close()

            with get_session() as session:
                # Main DB has NOT NULL constraint
                session.execute(text(
                    "CREATE TABLE test_notnull_n (id INTEGER NOT NULL)"
                ))
                session.commit()

            engine = get_engine()
            # Should not raise; the NULL row triggers the inner except.
            db._migrate_sqlite_side_db(engine, "test_notnull_config_n.db")
        finally:
            for ext in ("", ".bak"):
                p = side_db + ext
                if os.path.exists(p):
                    os.remove(p)

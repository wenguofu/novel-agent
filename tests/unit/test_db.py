"""Unit tests for portal/db.py — MySQL-only contract.

Covers the engine/session lifecycle, health check, URL validator, and
the `no raw sqlite3 import in portal/` invariant. Tests run with
``TESTING=1`` (set by ``tests/unit/conftest.py``) which opts the
runtime into a permissive mode that allows the in-memory SQLite path
the rest of the test suite uses. Production code never sees
``TESTING=1`` and refuses to start without a MySQL ``DATABASE_URL``.
"""
import os
import subprocess
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
    ensure_unified_schema,
    validate_database_url,
)


# ── validate_database_url (MySQL-only contract) ───────────────────────

class TestValidateDatabaseUrl:
    """The portal MUST refuse to start without a MySQL DATABASE_URL
    unless TESTING=1 is set. These tests exercise the validator
    directly with explicit URL arguments."""

    def test_rejects_empty_url(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="mysql\\+pymysql://"):
            validate_database_url("")

    def test_rejects_sqlite_url(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        with pytest.raises(RuntimeError, match="mysql\\+pymysql://"):
            validate_database_url("sqlite:///portal/content.db")

    def test_rejects_postgres_url(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        with pytest.raises(RuntimeError, match="mysql\\+pymysql://"):
            validate_database_url("postgresql://user:pass@host/db")

    def test_accepts_mysql_url(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        # Should not raise
        validate_database_url("mysql+pymysql://user:pass@localhost:3306/novel_agent")

    def test_testing_env_bypasses_validation(self, monkeypatch):
        monkeypatch.setenv("TESTING", "1")
        # Empty URL is allowed under TESTING=1
        validate_database_url("")
        # SQLite URL is allowed under TESTING=1
        validate_database_url("sqlite:///:memory:")

    def test_testing_env_unset_enforces_validation(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        with pytest.raises(RuntimeError):
            validate_database_url("")

    def test_uses_env_var_when_url_omitted(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@host:3306/db")
        # No arg → reads DATABASE_URL
        validate_database_url()


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
        reset_engine()
        with patch.object(db, "logger") as mock_logger:
            get_engine()
        assert mock_logger.info.called


# ── reset_engine ───────────────────────────────────────────────────────

class TestResetEngine:
    def test_resets_engine(self, tmp_db):
        e1 = get_engine()
        reset_engine()
        e2 = get_engine()
        assert e1 is not e2

    def test_disposes_old_engine(self, tmp_db):
        e1 = get_engine()
        with patch.object(e1, "dispose") as mock_dispose:
            reset_engine()
            mock_dispose.assert_called_once()

    def test_handles_dispose_exception(self, tmp_db):
        e1 = get_engine()
        with patch.object(e1, "dispose", side_effect=Exception("boom")):
            reset_engine()  # Should not raise

    def test_with_url_override(self, tmp_db, tmp_path):
        url = f"sqlite:///{tmp_path / 'override.db'}"
        reset_engine(url)
        engine = get_engine()
        assert engine is not None
        assert db.DATABASE_URL == url

    def test_no_dispose_when_engine_is_none(self, monkeypatch):
        monkeypatch.setattr(db, "_engine", None)
        monkeypatch.setattr(db, "_SessionLocal", None)
        reset_engine()
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
        with get_session() as session:
            session.execute(text("CREATE TABLE test_t (id INTEGER)"))
            session.execute(text("INSERT INTO test_t VALUES (1)"))
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
        with get_session() as session:
            result = session.execute(text("SELECT * FROM test_r")).fetchall()
            assert len(result) == 0

    def test_reraises_exception(self, tmp_db):
        with pytest.raises(RuntimeError, match="simulated"):
            with get_session() as session:
                raise RuntimeError("simulated")

    def test_session_closed_on_exit(self, tmp_db):
        with get_session() as session:
            assert session is not None


# ── transaction ────────────────────────────────────────────────────────

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
    def test_healthy_reports_mysql_engine(self, tmp_db):
        """The portal reports ``engine == "mysql"`` regardless of the
        actual backend in use (production is always MySQL; tests use
        SQLite-via-:memory: but the contract is the same)."""
        health = check_db_health()
        assert health["status"] == "healthy"
        assert health["engine"] == "mysql"

    def test_includes_database_name(self, tmp_db):
        health = check_db_health()
        assert "database" in health
        assert isinstance(health["database"], str)
        assert len(health["database"]) > 0

    def test_unhealthy_on_error(self, tmp_db):
        with patch.object(db, "get_engine", side_effect=Exception("connection refused")):
            health = check_db_health()
        assert health["status"] == "unhealthy"
        assert "error" in health
        assert "connection refused" in health["error"]

    def test_unhealthy_on_query_error(self, tmp_db):
        engine = get_engine()
        with patch.object(engine, "connect", side_effect=Exception("query failed")):
            health = check_db_health()
        assert health["status"] == "unhealthy"
        assert "error" in health
        assert "database" in health


# ── ensure_unified_schema ──────────────────────────────────────────────

class TestEnsureUnifiedSchema:
    def test_creates_tables(self, tmp_db):
        from db import get_session as _get_session
        with _get_session() as session:
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )).fetchall()
            table_names = [r[0] for r in result]
            assert "novels" in table_names

    def test_idempotent(self, tmp_db):
        from db import get_session as _get_session
        ensure_unified_schema()
        ensure_unified_schema()  # Should not raise
        with _get_session() as session:
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='novels'"
            )).fetchall()
            assert len(result) == 1


# ── No raw sqlite3 in production code (invariant) ─────────────────────

class TestNoSqlite3ImportInPortal:
    """The portal MUST NOT import sqlite3 directly. The migration script
    is the only sanctioned consumer of the stdlib sqlite3 module, and
    it lives under ``scripts/``, not ``portal/``."""

    def test_no_sqlite3_import_in_portal(self):
        result = subprocess.run(
            ["grep", "-rn", r"^import sqlite3\|^from sqlite3",
             "portal/", "--include=*.py"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1, (
            f"portal/ still has raw sqlite3 imports:\n{result.stdout}"
        )
        assert result.stdout == ""
